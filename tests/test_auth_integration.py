"""Offline Auth0 BFF contracts with deterministic provider fixtures."""

from __future__ import annotations

import io
import json
import os
import sqlite3
import stat
import time as clock
from datetime import date, time
from types import SimpleNamespace
from urllib.parse import parse_qs, urlencode, urlparse

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient

from grounded_travel_planner.auth import (
    AUTH_COOKIE_NAME,
    AUTH_PENDING_SECONDS,
    AccountLinkRequired,
    Auth0OidcProvider,
    AuthError,
    AuthRepository,
    VerifiedIdentity,
    _identity_lock_key,
)
from grounded_travel_planner.contracts import (
    PlaceRecommendation,
    ScheduleEntry,
    SightseeingPlan,
    SourceReference,
)
from grounded_travel_planner.saved_tours import SavedTourRepository
from grounded_travel_planner.web.api import (
    SAVED_TOURS_OWNER_COOKIE_NAME,
    SessionStore,
    create_app,
)


class FakeOidcProvider:
    """Records BFF inputs without making an Auth0 or network call."""

    def __init__(self, subject: str, email: str) -> None:
        self.identity = VerifiedIdentity(
            issuer="https://tenant.example.test/",
            subject=subject,
            email=email,
            email_verified=True,
        )
        self.authorization_calls: list[dict[str, str]] = []
        self.callback_calls: list[dict[str, str]] = []
        self.password_reset_calls: list[dict[str, str]] = []

    def authorization_url(
        self,
        *,
        state: str,
        nonce: str,
        code_verifier: str,
        redirect_uri: str,
        screen_hint: str | None = None,
        connection: str | None = None,
        prompt: str | None = None,
    ) -> str:
        self.authorization_calls.append(
            {
                "state": state,
                "nonce": nonce,
                "code_verifier": code_verifier,
                "redirect_uri": redirect_uri,
                "screen_hint": screen_hint or "",
                "connection": connection or "",
                "prompt": prompt or "",
            }
        )
        parameters = {"state": state}
        if screen_hint:
            parameters["screen_hint"] = screen_hint
        if connection:
            parameters["connection"] = connection
        if prompt:
            parameters["prompt"] = prompt
        return f"https://auth0.example.test/authorize?{urlencode(parameters)}"

    def verify_callback(
        self, *, code: str, nonce: str, code_verifier: str, redirect_uri: str
    ) -> VerifiedIdentity:
        self.callback_calls.append(
            {
                "code": code,
                "nonce": nonce,
                "code_verifier": code_verifier,
                "redirect_uri": redirect_uri,
            }
        )
        return self.identity

    def logout_url(self, *, return_to: str) -> str:
        return f"https://auth0.example.test/v2/logout?returnTo={return_to}"

    def request_password_reset(self, *, email: str, connection: str) -> None:
        self.password_reset_calls.append({"email": email, "connection": connection})


class FakeService:
    graph = object()

    def create_session(self) -> str:
        return "auth-thread"


class FakeVisuals:
    pass


def _plan(destination: str) -> SightseeingPlan:
    source = SourceReference(
        source_id=f"{destination}-source",
        title=f"{destination} fixture source",
        url="https://example.test/source",
        retrieval_query=destination,
    )
    return SightseeingPlan(
        plan_id=f"auth-plan-{destination.casefold()}",
        destination=destination,
        start_date=date(2026, 11, 1),
        day_count=1,
        entries=[
            ScheduleEntry(
                id=f"{destination}-entry",
                day_index=1,
                start_time=time(9),
                end_time=time(10),
                place=PlaceRecommendation(
                    place_id=f"{destination}-place",
                    name=destination,
                    description="Offline Auth0 fixture.",
                    source_references=[source],
                    opening_hours="unverified",
                ),
            )
        ],
        summary=f"Offline {destination} plan.",
    )


def _client(
    tmp_path,
    provider: FakeOidcProvider,
    monkeypatch: pytest.MonkeyPatch,
    *,
    base_url: str = "https://planner.example.test",
) -> tuple[TestClient, AuthRepository, SavedTourRepository]:
    monkeypatch.setenv("GTP_AUTH_SESSION_SECRET", "s" * 32)
    monkeypatch.setenv("GTP_AUTH_PUBLIC_ORIGIN", "https://planner.example.test")
    monkeypatch.setenv("GTP_AUTH0_PASSWORD_CONNECTION", "Users")
    auth = AuthRepository(tmp_path / "auth.sqlite")
    auth.migrate()
    admin_id, _ = auth.find_or_create_user(
        VerifiedIdentity(
            issuer="https://tenant.example.test/",
            subject="fixture-admin",
            email="admin@example.test",
            email_verified=True,
        )
    )
    if not auth.get_user(admin_id).is_admin:
        auth.bootstrap_admin(admin_id)
    tours = SavedTourRepository(tmp_path / "saved-tours.sqlite")
    app = create_app(
        FakeService(),
        FakeVisuals(),
        saved_tour_repository=tours,
        auth_provider=provider,
        auth_repository=auth,
    )
    app.state.test_auth_repository = auth
    app.state.test_admin_id = admin_id
    return (
        TestClient(app, base_url=base_url),
        auth,
        tours,
    )


def _sign_in(client: TestClient, provider: FakeOidcProvider) -> str:
    started = client.get(
        "/api/auth/login?return_to=/?view=saved", follow_redirects=False
    )
    assert started.status_code == 307
    assert started.headers["location"].startswith("https://auth0.example.test/")
    assert "httponly" in started.headers["set-cookie"].casefold()
    assert "secure" in started.headers["set-cookie"].casefold()
    state = parse_qs(urlparse(started.headers["location"]).query)["state"][0]
    callback = client.get(
        "/api/auth/callback",
        params={"code": "offline-code", "state": state},
        follow_redirects=False,
    )
    assert callback.status_code == 303
    assert callback.headers["location"] == "/?view=saved"
    user_id, _ = client.app.state.test_auth_repository.find_or_create_user(
        provider.identity
    )
    assert (
        client.app.state.test_auth_repository.get_user(user_id).access_status
        == "active"
    )
    assert (
        provider.callback_calls[0]["nonce"] == provider.authorization_calls[0]["nonce"]
    )
    assert (
        provider.callback_calls[0]["code_verifier"]
        == provider.authorization_calls[0]["code_verifier"]
    )
    return client.get("/api/auth/me").json()["csrf_token"]


def _start_google_link(client: TestClient, csrf_token: str) -> str:
    started = client.post("/api/auth/link/google", headers={"X-CSRF-Token": csrf_token})
    assert started.status_code == 200
    authorization_url = started.json()["authorization_url"]
    query = parse_qs(urlparse(authorization_url).query)
    assert query["connection"] == ["google-oauth2"]
    assert query["prompt"] == ["login"]
    return query["state"][0]


def _start_password_link(client: TestClient, csrf_token: str, mode: str) -> str:
    started = client.post(
        "/api/auth/link/password",
        params={"mode": mode},
        headers={"X-CSRF-Token": csrf_token},
    )
    assert started.status_code == 200
    query = parse_qs(urlparse(started.json()["authorization_url"]).query)
    assert query["connection"] == ["Users"]
    assert query["prompt"] == ["login"]
    assert query.get("screen_hint", [""])[0] == ("signup" if mode == "signup" else "")
    return query["state"][0]


@pytest.mark.parametrize("subject", ["auth0|password", "email|otp"])
def test_new_email_identity_cannot_create_second_app_account(
    tmp_path, subject: str
) -> None:
    auth = AuthRepository(tmp_path / "auth.sqlite")
    auth.migrate()
    google = _google_identity("person@example.test")
    primary_id, _ = auth.find_or_create_user(google)

    with pytest.raises(AccountLinkRequired):
        auth.find_or_create_user(
            VerifiedIdentity(google.issuer, subject, google.email, True)
        )

    assert [account.id for account in auth.list_users(limit=10, offset=0)] == [
        primary_id
    ]


def test_google_first_password_signup_then_link_preserves_account_and_tour(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    google = _google_identity("person@example.test")
    provider = FakeOidcProvider(google.subject, google.email)
    client, auth, tours = _client(tmp_path, provider, monkeypatch)
    csrf = _sign_in(client, provider)
    original_token = client.cookies.get(AUTH_COOKIE_NAME)
    primary_id = auth.authenticated(original_token).user_id
    saved = tours.save_for_user(primary_id, _plan("Hue"))
    assert client.get("/api/auth/me").json()["login_methods"] == ["google"]

    signup_state = _start_password_link(client, csrf, "signup")
    provider.identity = VerifiedIdentity(
        google.issuer, "auth0|password", google.email, False
    )
    unverified = client.get(
        "/api/auth/callback",
        params={"code": "signup-code", "state": signup_state},
        follow_redirects=False,
    )
    assert unverified.status_code == 303
    assert (
        unverified.headers["location"] == "/?view=profile&auth_error=email_unverified"
    )
    assert client.cookies.get(AUTH_COOKIE_NAME) == original_token
    assert auth.login_methods(primary_id) == ["google"]

    link_state = _start_password_link(client, csrf, "link")
    provider.identity = VerifiedIdentity(
        google.issuer, "auth0|password", google.email, True
    )
    linked = client.get(
        "/api/auth/callback",
        params={"code": "password-code", "state": link_state},
        follow_redirects=False,
    )
    assert linked.status_code == 303
    assert linked.headers["location"] == "/?view=profile&auth_link=password"
    assert client.cookies.get(AUTH_COOKIE_NAME) == original_token
    assert client.get("/api/auth/me").json()["login_methods"] == ["google", "password"]
    assert tours.list_for_user(primary_id).items[0].id == saved.id
    assert len(auth.list_users(limit=10, offset=0)) == 2  # admin and owner

    client.cookies.clear()
    _sign_in(client, provider)
    assert (
        auth.authenticated(client.cookies.get(AUTH_COOKIE_NAME)).user_id == primary_id
    )
    assert client.get("/api/saved-tours").json()["items"][0]["id"] == saved.id


def test_password_link_rejects_wrong_identity_and_stale_original_session(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    google = _google_identity("person@example.test")
    provider = FakeOidcProvider(google.subject, google.email)
    client, auth, _ = _client(tmp_path, provider, monkeypatch)
    csrf = _sign_in(client, provider)
    primary_id = auth.authenticated(client.cookies.get(AUTH_COOKIE_NAME)).user_id
    assert client.post("/api/auth/link/password?mode=link").status_code == 403

    state = _start_password_link(client, csrf, "link")
    provider.identity = VerifiedIdentity(
        google.issuer, "auth0|other", "other@example.test", True
    )
    failed = client.get(
        "/api/auth/callback",
        params={"code": "password-code", "state": state},
        follow_redirects=False,
    )
    assert failed.headers["location"] == "/?auth_error=link_failed"
    assert auth.login_methods(primary_id) == ["google"]

    with sqlite3.connect(tmp_path / "auth.sqlite") as connection:
        connection.execute(
            "UPDATE auth_sessions SET created_at = '2000-01-01T00:00:00+00:00'"
        )
    stale = client.post(
        "/api/auth/link/password?mode=link", headers={"X-CSRF-Token": csrf}
    )
    assert stale.status_code == 409


def test_password_link_rejects_identity_owned_by_another_account_with_tour(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    google = _google_identity("person@example.test")
    provider = FakeOidcProvider(google.subject, google.email)
    client, auth, tours = _client(tmp_path, provider, monkeypatch)
    csrf = _sign_in(client, provider)
    original_token = client.cookies.get(AUTH_COOKIE_NAME)
    primary_id = auth.authenticated(original_token).user_id
    secondary_id = "legacy-password-account"
    password_subject = "auth0|legacy-password"
    with sqlite3.connect(tmp_path / "auth.sqlite") as connection:
        connection.execute(
            "INSERT INTO app_users (id, email, created_at) VALUES (?, ?, ?)",
            (secondary_id, google.email, "2026-11-01T00:00:00+00:00"),
        )
        connection.execute(
            "INSERT INTO auth_identities (issuer, subject, user_id) VALUES (?, ?, ?)",
            (google.issuer, password_subject, secondary_id),
        )
    saved = tours.save_for_user(secondary_id, _plan("Da Nang"))
    state = _start_password_link(client, csrf, "link")
    provider.identity = VerifiedIdentity(
        google.issuer, password_subject, google.email, True
    )

    callback = client.get(
        "/api/auth/callback",
        params={"code": "password-code", "state": state},
        follow_redirects=False,
    )

    assert callback.status_code == 303
    assert callback.headers["location"] == "/?auth_error=link_failed"
    assert client.cookies.get(AUTH_COOKIE_NAME) == original_token
    assert auth.login_methods(primary_id) == ["google"]
    assert auth.login_methods(secondary_id) == ["password"]
    assert tours.list_for_user(secondary_id).items[0].id == saved.id
    assert tours.list_for_user(primary_id).items == []


def test_password_reset_requires_linked_method_and_rate_limits(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    provider = FakeOidcProvider("auth0|password", "person@example.test")
    client, _, _ = _client(tmp_path, provider, monkeypatch)
    csrf = _sign_in(client, provider)

    assert client.post("/api/auth/password/reset").status_code == 403
    sent = client.post("/api/auth/password/reset", headers={"X-CSRF-Token": csrf})
    assert sent.status_code == 200
    assert sent.json() == {"sent": True}
    assert provider.password_reset_calls == [
        {"email": "person@example.test", "connection": "Users"}
    ]
    repeated = client.post("/api/auth/password/reset", headers={"X-CSRF-Token": csrf})
    assert repeated.status_code == 429
    assert repeated.headers["Retry-After"]
    assert len(provider.password_reset_calls) == 1


def test_google_only_account_cannot_request_database_password_reset(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    google = _google_identity("person@example.test")
    provider = FakeOidcProvider(google.subject, google.email)
    client, _, _ = _client(tmp_path, provider, monkeypatch)
    csrf = _sign_in(client, provider)

    response = client.post("/api/auth/password/reset", headers={"X-CSRF-Token": csrf})

    assert response.status_code == 409
    assert provider.password_reset_calls == []


def _google_identity(
    email: str, subject: str = "google-oauth2|new"
) -> VerifiedIdentity:
    return VerifiedIdentity(
        issuer="https://tenant.example.test/",
        subject=subject,
        email=email,
        email_verified=True,
    )


def test_google_same_email_does_not_link_on_normal_login(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    provider = FakeOidcProvider("auth0|primary", "person@example.test")
    client, auth, _ = _client(tmp_path, provider, monkeypatch)
    _sign_in(client, provider)
    primary_id = auth.authenticated(client.cookies.get(AUTH_COOKIE_NAME)).user_id
    provider.identity = _google_identity("person@example.test")

    started = client.get("/api/auth/login", follow_redirects=False)
    state = parse_qs(urlparse(started.headers["location"]).query)["state"][0]
    callback = client.get(
        "/api/auth/callback",
        params={"code": "google-code", "state": state},
        follow_redirects=False,
    )

    assert callback.status_code == 303
    assert callback.headers["location"] == "/?auth_error=link_required"
    with sqlite3.connect(tmp_path / "auth.sqlite") as connection:
        linked = connection.execute(
            "SELECT user_id FROM auth_identities WHERE subject = ?",
            (provider.identity.subject,),
        ).fetchone()
    assert linked is None
    assert auth.get_user(primary_id) is not None
    assert len(auth.list_users(limit=10, offset=0)) == 2


def test_explicit_google_link_preserves_primary_account_and_saved_tours(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    provider = FakeOidcProvider("auth0|primary", "person@example.test")
    client, auth, tours = _client(tmp_path, provider, monkeypatch)
    csrf = _sign_in(client, provider)
    original_token = client.cookies.get(AUTH_COOKIE_NAME)
    primary_id = auth.authenticated(original_token).user_id
    saved = tours.save_for_user(primary_id, _plan("Hue"))
    state = _start_google_link(client, csrf)
    assert provider.authorization_calls[-1]["connection"] == "google-oauth2"
    assert provider.authorization_calls[-1]["prompt"] == "login"
    provider.identity = _google_identity("person@example.test")

    callback = client.get(
        "/api/auth/callback",
        params={"code": "google-code", "state": state},
        follow_redirects=False,
    )

    assert callback.status_code == 303
    assert callback.headers["location"] == "/?auth_link=linked"
    assert client.cookies.get(AUTH_COOKIE_NAME) == original_token
    assert auth.authenticated(original_token).user_id == primary_id
    with sqlite3.connect(tmp_path / "auth.sqlite") as connection:
        linked = connection.execute(
            "SELECT user_id FROM auth_identities WHERE subject = ?",
            (provider.identity.subject,),
        ).fetchone()
    assert linked == (primary_id,)
    assert tours.list_for_user(primary_id).items[0].id == saved.id
    assert len(auth.list_users(limit=10, offset=0)) == 2

    client.cookies.clear()
    started = client.get("/api/auth/login", follow_redirects=False)
    login_state = parse_qs(urlparse(started.headers["location"]).query)["state"][0]
    signed_in = client.get(
        "/api/auth/callback",
        params={"code": "new-google-code", "state": login_state},
        follow_redirects=False,
    )
    assert signed_in.status_code == 303
    assert (
        auth.authenticated(client.cookies.get(AUTH_COOKIE_NAME)).user_id == primary_id
    )
    assert client.get("/api/saved-tours").json()["items"][0]["id"] == saved.id


def test_google_link_requires_csrf_and_recent_primary_login(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    provider = FakeOidcProvider("auth0|primary", "person@example.test")
    client, _, _ = _client(tmp_path, provider, monkeypatch)
    csrf = _sign_in(client, provider)
    before = len(provider.authorization_calls)

    assert client.post("/api/auth/link/google").status_code == 403
    assert (
        client.post(
            "/api/auth/link/google", headers={"X-CSRF-Token": csrf + "wrong"}
        ).status_code
        == 403
    )
    assert len(provider.authorization_calls) == before

    with sqlite3.connect(tmp_path / "auth.sqlite") as connection:
        connection.execute(
            "UPDATE auth_sessions SET created_at = '2000-01-01T00:00:00+00:00'"
        )
    stale = client.post("/api/auth/link/google", headers={"X-CSRF-Token": csrf})
    assert stale.status_code == 409
    assert len(provider.authorization_calls) == before


@pytest.mark.parametrize("case", ["wrong_provider", "wrong_email", "unverified"])
def test_google_link_rejects_wrong_or_unverified_identity(
    tmp_path, monkeypatch: pytest.MonkeyPatch, case: str
) -> None:
    provider = FakeOidcProvider("auth0|primary", "person@example.test")
    client, auth, _ = _client(tmp_path, provider, monkeypatch)
    csrf = _sign_in(client, provider)
    primary_token = client.cookies.get(AUTH_COOKIE_NAME)
    primary_id = auth.authenticated(primary_token).user_id
    state = _start_google_link(client, csrf)
    if case == "wrong_provider":
        provider.identity = _google_identity("person@example.test", "auth0|other")
    elif case == "wrong_email":
        provider.identity = _google_identity("other@example.test")
    else:
        provider.identity = VerifiedIdentity(
            issuer="https://tenant.example.test/",
            subject="google-oauth2|new",
            email="person@example.test",
            email_verified=False,
        )

    callback = client.get(
        "/api/auth/callback",
        params={"code": "google-code", "state": state},
        follow_redirects=False,
    )

    assert callback.status_code == 303
    expected_error = "email_unverified" if case == "unverified" else "link_failed"
    expected_location = (
        f"/?view=profile&auth_error={expected_error}"
        if case == "unverified"
        else f"/?auth_error={expected_error}"
    )
    assert callback.headers["location"] == expected_location
    assert auth.authenticated(primary_token).user_id == primary_id
    with sqlite3.connect(tmp_path / "auth.sqlite") as connection:
        linked = connection.execute(
            "SELECT user_id FROM auth_identities WHERE subject = ?",
            (provider.identity.subject,),
        ).fetchone()
    assert linked is None


def test_blocked_primary_cannot_start_google_link(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    provider = FakeOidcProvider("auth0|primary", "person@example.test")
    client, auth, _ = _client(tmp_path, provider, monkeypatch)
    csrf = _sign_in(client, provider)
    user_id = auth.authenticated(client.cookies.get(AUTH_COOKIE_NAME)).user_id
    before = len(provider.authorization_calls)

    auth.set_access(user_id, active=False, actor_user_id=client.app.state.test_admin_id)
    blocked = client.post("/api/auth/link/google", headers={"X-CSRF-Token": csrf})

    assert blocked.status_code in {401, 403}
    assert len(provider.authorization_calls) == before


@pytest.mark.parametrize("has_tour", [False, True])
def test_google_link_rejects_existing_separate_account_without_data_loss(
    tmp_path, monkeypatch: pytest.MonkeyPatch, has_tour: bool
) -> None:
    provider = FakeOidcProvider("auth0|primary", "person@example.test")
    client, auth, tours = _client(tmp_path, provider, monkeypatch)
    google = _google_identity("person@example.test", "google-oauth2|existing")
    csrf = _sign_in(client, provider)
    primary_id = auth.authenticated(client.cookies.get(AUTH_COOKIE_NAME)).user_id
    # Simulate a duplicate identity created before the new email-conflict gate.
    secondary_id = "legacy-google-account"
    with sqlite3.connect(tmp_path / "auth.sqlite") as connection:
        connection.execute(
            "INSERT INTO app_users (id, email, created_at) VALUES (?, ?, ?)",
            (secondary_id, google.email, "2026-11-01T00:00:00+00:00"),
        )
        connection.execute(
            "INSERT INTO auth_identities (issuer, subject, user_id) VALUES (?, ?, ?)",
            (google.issuer, google.subject, secondary_id),
        )
    secondary_token, _ = auth.issue_session(secondary_id, google.email)
    saved = tours.save_for_user(secondary_id, _plan("Da Nang")) if has_tour else None
    state = _start_google_link(client, csrf)
    provider.identity = google

    callback = client.get(
        "/api/auth/callback",
        params={"code": "google-code", "state": state},
        follow_redirects=False,
    )

    assert callback.status_code == 303
    assert callback.headers["location"] == "/?auth_error=link_failed"
    assert auth.get_user(primary_id) is not None
    assert auth.get_user(secondary_id) is not None
    assert auth.authenticated(secondary_token).user_id == secondary_id
    with sqlite3.connect(tmp_path / "auth.sqlite") as connection:
        linked = connection.execute(
            "SELECT user_id FROM auth_identities WHERE subject = ?", (google.subject,)
        ).fetchone()
    assert linked == (secondary_id,)
    if saved is not None:
        assert tours.list_for_user(secondary_id).items[0].id == saved.id
        assert tours.list_for_user(primary_id).items == []


def test_google_link_state_cannot_be_forged_or_replayed(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    provider = FakeOidcProvider("auth0|primary", "person@example.test")
    client, auth, _ = _client(tmp_path, provider, monkeypatch)
    csrf = _sign_in(client, provider)
    state = _start_google_link(client, csrf)
    provider.identity = _google_identity("person@example.test")
    before = len(provider.callback_calls)

    forged = client.get(
        "/api/auth/callback",
        params={"code": "google-code", "state": state + "forged"},
        follow_redirects=False,
    )
    assert forged.status_code == 400
    assert len(provider.callback_calls) == before

    linked = client.get(
        "/api/auth/callback",
        params={"code": "google-code", "state": state},
        follow_redirects=False,
    )
    assert linked.status_code == 303
    assert linked.headers["location"] == "/?auth_link=linked"
    replayed = client.get(
        "/api/auth/callback",
        params={"code": "google-code", "state": state},
        follow_redirects=False,
    )
    assert replayed.status_code == 400
    with sqlite3.connect(tmp_path / "auth.sqlite") as connection:
        events = connection.execute(
            "SELECT action FROM account_access_events WHERE action = 'link_google_identity'"
        ).fetchall()
    assert events == [("link_google_identity",)]
    assert len(auth.list_users(limit=10, offset=0)) == 2


def test_google_link_rejects_expired_pending_state_and_revoked_primary_session(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    provider = FakeOidcProvider("auth0|primary", "person@example.test")
    client, auth, _ = _client(tmp_path, provider, monkeypatch)
    csrf = _sign_in(client, provider)
    state = _start_google_link(client, csrf)
    provider.identity = _google_identity("person@example.test")
    before = len(provider.callback_calls)

    with monkeypatch.context() as patch:
        patch.setattr(
            "grounded_travel_planner.auth._now", lambda: 2**31 + AUTH_PENDING_SECONDS
        )
        expired = client.get(
            "/api/auth/callback",
            params={"code": "google-code", "state": state},
            follow_redirects=False,
        )
    assert expired.status_code == 303
    assert expired.headers["location"] != "/?auth_link=linked"
    assert len(provider.callback_calls) == before
    state = _start_google_link(client, csrf)
    token = client.cookies.get(AUTH_COOKIE_NAME)
    auth.revoke(token)
    revoked = client.get(
        "/api/auth/callback",
        params={"code": "google-code", "state": state},
        follow_redirects=False,
    )
    assert revoked.status_code == 303
    assert revoked.headers["location"] == "/?auth_error=link_failed"
    with sqlite3.connect(tmp_path / "auth.sqlite") as connection:
        linked = connection.execute(
            "SELECT user_id FROM auth_identities WHERE subject = ?",
            (provider.identity.subject,),
        ).fetchone()
    assert linked is None


@pytest.mark.parametrize(
    ("intent", "expected_hint", "expected_connection", "expected_prompt"),
    [
        ("login", "", "", ""),
        ("google", "", "google-oauth2", ""),
        ("email", "", "Users", ""),
        ("signup", "signup", "Users", "login"),
        ("otp", "", "email", ""),
    ],
)
def test_auth_login_intent_controls_signup_screen_hint(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
    intent: str,
    expected_hint: str,
    expected_connection: str,
    expected_prompt: str,
) -> None:
    provider = FakeOidcProvider("auth0|signup-test", "signup@example.test")
    client, _, _ = _client(tmp_path, provider, monkeypatch)

    response = client.get(
        "/api/auth/login", params={"intent": intent}, follow_redirects=False
    )

    assert response.status_code == 307
    query = parse_qs(urlparse(response.headers["location"]).query)
    assert query.get("screen_hint", [""])[0] == expected_hint
    assert provider.authorization_calls[0]["screen_hint"] == expected_hint
    assert provider.authorization_calls[0]["connection"] == expected_connection
    assert provider.authorization_calls[0]["prompt"] == expected_prompt


def test_existing_account_login_forces_fresh_auth0_prompt(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    provider = FakeOidcProvider("auth0|primary", "person@example.test")
    client, _, _ = _client(tmp_path, provider, monkeypatch)

    response = client.get(
        "/api/auth/login", params={"intent": "existing"}, follow_redirects=False
    )

    assert response.status_code == 307
    assert provider.authorization_calls[0]["prompt"] == "login"
    assert parse_qs(urlparse(response.headers["location"]).query)["prompt"] == ["login"]


def test_email_login_requires_a_configured_password_connection(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    provider = FakeOidcProvider("auth0|password", "person@example.test")
    client, _, _ = _client(tmp_path, provider, monkeypatch)
    monkeypatch.delenv("GTP_AUTH0_PASSWORD_CONNECTION")

    response = client.get("/api/auth/login?intent=email", follow_redirects=False)

    assert response.status_code == 503
    assert provider.authorization_calls == []


def test_unverified_email_cannot_create_an_app_account_or_session(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    provider = FakeOidcProvider("auth0|unverified", "new@example.test")
    provider.identity = VerifiedIdentity(
        issuer=provider.identity.issuer,
        subject=provider.identity.subject,
        email=provider.identity.email,
        email_verified=False,
    )
    client, auth, _ = _client(tmp_path, provider, monkeypatch)
    started = client.get("/api/auth/login", follow_redirects=False)
    state = parse_qs(urlparse(started.headers["location"]).query)["state"][0]

    callback = client.get(
        "/api/auth/callback",
        params={"code": "offline-code", "state": state},
        follow_redirects=False,
    )

    assert callback.status_code == 303
    assert callback.headers["location"] == "/?auth_error=email_unverified"
    assert "gtp_auth=" not in callback.headers["set-cookie"]
    assert client.get("/api/auth/me").json()["authenticated"] is False
    assert len(auth.list_users(limit=10, offset=0)) == 1  # fixture admin only


def test_verified_login_activates_an_existing_pending_identity(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    provider = FakeOidcProvider("auth0|pending", "pending@example.test")
    client, auth, _ = _client(tmp_path, provider, monkeypatch)
    user_id, _ = auth.find_or_create_user(provider.identity)
    with sqlite3.connect(tmp_path / "auth.sqlite") as connection:
        connection.execute(
            "UPDATE app_users SET access_status = 'pending' WHERE id = ?", (user_id,)
        )

    _sign_in(client, provider)

    assert auth.get_user(user_id).access_status == "active"
    assert client.get("/api/auth/me").json()["access_status"] == "active"
    assert len(auth.list_users(limit=10, offset=0)) == 2
    with sqlite3.connect(tmp_path / "auth.sqlite") as connection:
        actions = connection.execute(
            "SELECT action FROM account_access_events WHERE user_id = ?", (user_id,)
        ).fetchall()
    assert actions == [("verified_login",)]


def test_auth_repository_rejects_unverified_identity(tmp_path) -> None:
    auth = AuthRepository(tmp_path / "auth.sqlite")
    auth.migrate()

    with pytest.raises(AuthError, match="Email is not verified"):
        auth.find_or_create_user(
            VerifiedIdentity(
                "https://tenant.example.test/", "auth0|unverified", "new@example.test"
            )
        )
    assert auth.list_users(limit=10, offset=0) == []


def test_verified_login_does_not_reactivate_blocked_account(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    provider = FakeOidcProvider("auth0|blocked", "blocked@example.test")
    client, auth, _ = _client(tmp_path, provider, monkeypatch)
    user_id, _ = auth.find_or_create_user(provider.identity)
    auth.set_access(user_id, active=False, actor_user_id=client.app.state.test_admin_id)
    started = client.get("/api/auth/login", follow_redirects=False)
    state = parse_qs(urlparse(started.headers["location"]).query)["state"][0]

    callback = client.get(
        "/api/auth/callback",
        params={"code": "offline-code", "state": state},
        follow_redirects=False,
    )

    assert callback.status_code == 303
    assert callback.headers["location"] == "/?auth_error=login_failed"
    assert auth.get_user(user_id).access_status == "blocked"
    assert client.get("/api/auth/me").json()["authenticated"] is False


def test_admin_migration_keeps_existing_accounts_active(tmp_path) -> None:
    database = tmp_path / "legacy-auth.sqlite"
    with sqlite3.connect(database) as connection:
        connection.execute(
            "CREATE TABLE app_users (id TEXT PRIMARY KEY, email TEXT, created_at TEXT NOT NULL)"
        )
        connection.execute(
            "INSERT INTO app_users (id, email, created_at) VALUES (?, ?, ?)",
            ("existing-user", "existing@example.test", "2026-11-01T00:00:00+00:00"),
        )
    auth = AuthRepository(database)
    auth.migrate_admin()
    auth.migrate_admin()
    assert auth.get_user("existing-user").access_status == "active"
    assert auth.get_user("existing-user").is_admin is False
    with sqlite3.connect(database) as connection:
        connection.execute(
            """INSERT INTO account_usage_aliases
            (former_user_id, canonical_user_id) VALUES (?, ?)""",
            ("removed-user", "existing-user"),
        )
    assert auth.usage_aliases_for_users(["existing-user"]) == {
        "existing-user": ["removed-user"]
    }


def test_auth0_uses_the_configured_public_origin_for_callback_and_logout(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    provider = FakeOidcProvider("auth0|migration", "migration@example.test")
    origin = "https://citedtrip.app"
    client, _, _ = _client(tmp_path, provider, monkeypatch, base_url=origin)
    monkeypatch.setenv("GTP_AUTH_PUBLIC_ORIGIN", origin)

    csrf = _sign_in(client, provider)

    expected_callback = f"{origin}/api/auth/callback"
    assert provider.authorization_calls[0]["redirect_uri"] == expected_callback
    assert provider.callback_calls[0]["redirect_uri"] == expected_callback

    logout = client.post("/api/auth/logout", headers={"X-CSRF-Token": csrf})
    assert logout.status_code == 200
    assert f"returnTo={origin}/" in logout.json()["logout_url"]


def test_auth0_rejects_login_from_unconfigured_host(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    provider = FakeOidcProvider("auth0|migration", "migration@example.test")
    client, _, _ = _client(tmp_path, provider, monkeypatch)
    monkeypatch.setenv("GTP_AUTH_PUBLIC_ORIGIN", "https://citedtrip.app")

    response = client.get(
        "/api/auth/login",
        headers={"Host": "attacker.example.test"},
        follow_redirects=False,
    )

    assert response.status_code == 503
    assert provider.authorization_calls == []


@pytest.mark.parametrize(
    "issuer",
    [
        "http://tenant.example.test",
        "https://",
        "https://tenant.example.test/path",
        "https://tenant.example.test?query=value",
        "https://user@tenant.example.test",
    ],
)
def test_auth0_provider_rejects_non_https_origins(issuer: str) -> None:
    with pytest.raises(AuthError, match="valid HTTPS origin"):
        Auth0OidcProvider(
            issuer=issuer, client_id="client-id", client_secret="test-secret"
        )


def test_auth0_provider_environment_requires_an_https_origin(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("GTP_AUTH0_ISSUER", "http://tenant.example.test")
    monkeypatch.setenv("GTP_AUTH0_CLIENT_ID", "client-id")
    monkeypatch.setenv("GTP_AUTH0_CLIENT_SECRET", "test-secret")

    with pytest.raises(AuthError, match="valid HTTPS origin"):
        Auth0OidcProvider.from_environment()


def test_auth0_password_reset_uses_the_fixed_database_connection(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provider = Auth0OidcProvider(
        issuer="https://tenant.example.test",
        client_id="client-id",
        client_secret="test-secret",
    )
    calls = []

    class EmptyResponse:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

    def fake_urlopen(request, timeout):
        calls.append((request, timeout))
        return EmptyResponse()

    monkeypatch.setattr("grounded_travel_planner.auth.urlopen", fake_urlopen)
    provider.request_password_reset(email="person@example.test", connection="Users")

    assert len(calls) == 1
    request, timeout = calls[0]
    assert (
        request.full_url == "https://tenant.example.test/dbconnections/change_password"
    )
    assert request.get_method() == "POST"
    assert timeout == 10
    assert json.loads(request.data) == {
        "client_id": "client-id",
        "email": "person@example.test",
        "connection": "Users",
    }
    assert "test-secret" not in request.data.decode()


@pytest.mark.skipif(os.name != "posix", reason="POSIX permissions are required")
def test_auth_sqlite_files_are_private_before_opening(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    database_directory = tmp_path / "auth-storage"
    database_directory.mkdir()
    os.chmod(database_directory, 0o755)
    database_path = database_directory / "auth.sqlite"
    with sqlite3.connect(database_path):
        pass
    sidecars = [
        database_path.with_name(database_path.name + suffix)
        for suffix in ("-wal", "-shm", "-journal")
    ]
    for path in [database_path, *sidecars]:
        path.touch()
        os.chmod(path, 0o644)

    import grounded_travel_planner.auth as auth_module

    original_connect = auth_module.sqlite3.connect

    def assert_private_connect(*args, **kwargs):
        assert stat.S_IMODE(database_directory.stat().st_mode) == 0o755
        for path in [database_path, *sidecars]:
            assert stat.S_IMODE(path.stat().st_mode) == 0o600
        return original_connect(*args, **kwargs)

    monkeypatch.setattr(auth_module.sqlite3, "connect", assert_private_connect)
    AuthRepository(database_path).migrate()


@pytest.mark.skipif(os.name != "posix", reason="POSIX permissions are required")
def test_auth_sqlite_creates_missing_storage_directories_privately(tmp_path) -> None:
    storage_directory = tmp_path / "private" / "auth"
    AuthRepository(storage_directory / "auth.sqlite").migrate()

    assert stat.S_IMODE((tmp_path / "private").stat().st_mode) == 0o700
    assert stat.S_IMODE(storage_directory.stat().st_mode) == 0o700


def test_auth_callback_validates_state_and_expiry_before_creating_session(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    provider = FakeOidcProvider("auth0|a", "a@example.test")
    client, _, _ = _client(tmp_path, provider, monkeypatch)
    client.get("/api/auth/login", follow_redirects=False)
    state = provider.authorization_calls[0]["state"]

    mismatch = client.get(
        "/api/auth/callback",
        params={"code": "offline-code", "state": state + "bad"},
        follow_redirects=False,
    )
    assert mismatch.status_code == 400
    assert client.cookies.get(AUTH_COOKIE_NAME) is None
    assert provider.callback_calls == []

    client.cookies.clear()
    client.get("/api/auth/login", follow_redirects=False)
    monkeypatch.setattr(
        "grounded_travel_planner.auth._now",
        lambda: 2**31 + AUTH_PENDING_SECONDS,
    )
    expired = client.get(
        "/api/auth/callback",
        params={
            "code": "offline-code",
            "state": provider.authorization_calls[-1]["state"],
        },
        follow_redirects=False,
    )
    assert expired.status_code == 303
    assert client.cookies.get(AUTH_COOKIE_NAME) is None
    assert len(provider.callback_calls) == 0


def test_live_planner_endpoints_require_a_verified_account(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    provider = FakeOidcProvider("auth0|a", "a@example.test")
    client, _, _ = _client(tmp_path, provider, monkeypatch)

    assert client.post("/api/session").status_code == 401
    assert client.get("/api/session").status_code == 401
    assert client.post("/api/session/reset").status_code == 401
    assert (
        client.put("/api/session/language", json={"language": "en"}).status_code == 401
    )
    assert client.post("/api/turns", json={"message": "plan"}).status_code == 401
    assert client.get("/api/visuals?revision=1").status_code == 401


def test_authenticated_planner_mutations_require_csrf_before_state_changes(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    provider = FakeOidcProvider("auth0|a", "a@example.test")
    client, _, _ = _client(tmp_path, provider, monkeypatch)
    csrf = _sign_in(client, provider)
    original_session = client.cookies.get("gtp_session")
    assert original_session

    assert client.post("/api/session").status_code == 403
    assert client.post("/api/session/reset").status_code == 403
    assert client.cookies.get("gtp_session") == original_session

    before_language = client.get("/api/session").json()["language"]
    assert (
        client.put("/api/session/language", json={"language": "en"}).status_code == 403
    )
    assert client.get("/api/session").json()["language"] == before_language

    turn = {"message": "Create an offline plan"}
    assert client.post("/api/turns", json=turn).status_code == 403
    invalid_headers = {"X-CSRF-Token": csrf + "invalid"}
    assert client.post("/api/session/reset", headers=invalid_headers).status_code == 403
    assert (
        client.put(
            "/api/session/language",
            json={"language": "en"},
            headers=invalid_headers,
        ).status_code
        == 403
    )
    assert (
        client.post("/api/turns", json=turn, headers=invalid_headers).status_code == 403
    )
    unchanged = client.get("/api/session").json()
    assert unchanged["pending"] is False
    assert unchanged["conversation"] == []

    headers = {"X-CSRF-Token": csrf}
    assert client.post("/api/session", headers=headers).status_code == 201
    assert client.post("/api/session/reset", headers=headers).status_code == 200
    assert (
        client.put(
            "/api/session/language",
            json={"language": "en"},
            headers=headers,
        ).status_code
        == 200
    )
    assert client.post("/api/turns", json=turn, headers=headers).status_code == 202


def test_live_session_isolated_by_authenticated_account(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    first_provider = FakeOidcProvider("auth0|first", "first@example.test")
    first, _, _ = _client(tmp_path, first_provider, monkeypatch)
    _sign_in(first, first_provider)
    first_session = first.cookies.get("gtp_session")
    assert first_session

    second_provider = FakeOidcProvider("auth0|second", "second@example.test")
    second, _, _ = _client(tmp_path, second_provider, monkeypatch)
    csrf = _sign_in(second, second_provider)
    second.cookies.set(
        "gtp_session", first_session, domain="planner.example.test", path="/"
    )
    assert second.get("/api/session").status_code == 401
    headers = {"X-CSRF-Token": csrf}
    assert second.post("/api/session/reset", headers=headers).status_code == 401
    assert (
        second.post("/api/turns", json={"message": "plan"}, headers=headers).status_code
        == 401
    )


def test_login_binds_an_existing_unowned_browser_session(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("GTP_AUTH_SESSION_SECRET", "s" * 32)
    monkeypatch.setenv("GTP_AUTH_PUBLIC_ORIGIN", "https://planner.example.test")
    provider = FakeOidcProvider("auth0|a", "a@example.test")
    auth = AuthRepository(tmp_path / "auth.sqlite")
    auth.migrate()
    admin_id, _ = auth.find_or_create_user(
        VerifiedIdentity(
            issuer="https://tenant.example.test/",
            subject="fixture-admin",
            email="admin@example.test",
            email_verified=True,
        )
    )
    auth.bootstrap_admin(admin_id)
    sessions = SessionStore()
    session_id, _ = sessions.create(FakeService())
    app = create_app(
        FakeService(),
        FakeVisuals(),
        saved_tour_repository=SavedTourRepository(tmp_path / "saved-tours.sqlite"),
        auth_provider=provider,
        auth_repository=auth,
        session_store=sessions,
    )
    app.state.test_auth_repository = auth
    app.state.test_admin_id = admin_id
    client = TestClient(
        app,
        base_url="https://planner.example.test",
    )
    client.cookies.set(
        "gtp_session", session_id, domain="planner.example.test", path="/"
    )

    _sign_in(client, provider)

    assert client.cookies.get("gtp_session") == session_id
    assert client.get("/api/session").status_code == 200


def test_login_rotates_other_account_session_and_logout_removes_it(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    provider = FakeOidcProvider("auth0|first", "first@example.test")
    client, _, _ = _client(tmp_path, provider, monkeypatch)
    csrf = _sign_in(client, provider)
    first_session = client.cookies.get("gtp_session")
    assert first_session

    provider.identity = VerifiedIdentity(
        issuer="https://tenant.example.test/",
        subject="auth0|second",
        email="second@example.test",
        email_verified=True,
    )
    started = client.get("/api/auth/login", follow_redirects=False)
    state = parse_qs(urlparse(started.headers["location"]).query)["state"][0]
    callback = client.get(
        "/api/auth/callback",
        params={"code": "offline-code", "state": state},
        follow_redirects=False,
    )
    assert callback.status_code == 303
    second_session = client.cookies.get("gtp_session")
    assert second_session and second_session != first_session

    logout = client.post(
        "/api/auth/logout",
        headers={"X-CSRF-Token": client.get("/api/auth/me").json()["csrf_token"]},
    )
    assert logout.status_code == 200
    assert 'gtp_session=""' in logout.headers["set-cookie"]
    assert client.get("/api/session").status_code == 401
    assert csrf


def test_identity_advisory_lock_key_is_unambiguous_postgres_text() -> None:
    left = _identity_lock_key(VerifiedIdentity("issuer", "subject"))
    right = _identity_lock_key(VerifiedIdentity("issuer-s", "ubject"))
    assert left != right
    assert "\x00" not in left
    assert "\x00" not in right


def test_authenticated_archive_requires_csrf_and_hides_other_account_rows(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    first_provider = FakeOidcProvider("auth0|first", "first@example.test")
    first, first_auth, tours = _client(tmp_path, first_provider, monkeypatch)
    first_csrf = _sign_in(first, first_provider)
    first_token = first.cookies.get(AUTH_COOKIE_NAME)
    assert first_token
    first_user = first_auth.authenticated(first_token)
    assert first_user is not None
    first_csrf = first_user.csrf_token
    saved = tours.save_for_user(first_user.user_id, _plan("Hue"))

    second_provider = FakeOidcProvider("auth0|second", "second@example.test")
    second, _, _ = _client(tmp_path, second_provider, monkeypatch)
    _sign_in(second, second_provider)

    assert second.get("/api/saved-tours").json()["items"] == []
    assert second.get(f"/api/saved-tours/{saved.id}").status_code == 404
    assert second.delete(f"/api/saved-tours/{saved.id}").status_code == 403
    assert first.delete(f"/api/saved-tours/{saved.id}").status_code == 403
    assert (
        first.delete(
            f"/api/saved-tours/{saved.id}", headers={"X-CSRF-Token": "wrong"}
        ).status_code
        == 403
    )
    assert (
        first.delete(
            f"/api/saved-tours/{saved.id}", headers={"X-CSRF-Token": first_csrf}
        ).status_code
        == 204
    )


def test_archive_rejects_missing_authentication(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    provider = FakeOidcProvider("auth0|anonymous", "anonymous@example.test")
    client, _, _ = _client(tmp_path, provider, monkeypatch)
    assert client.get("/api/saved-tours").status_code == 401
    assert client.get(f"/api/saved-tours/{'a' * 32}").status_code == 401
    assert client.post("/api/saved-tours").status_code == 401
    assert client.delete(f"/api/saved-tours/{'a' * 32}").status_code == 401


def test_logout_requires_csrf_and_legacy_claim_needs_original_cookie(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    provider = FakeOidcProvider("auth0|claim", "claim@example.test")
    client, auth, tours = _client(tmp_path, provider, monkeypatch)
    csrf = _sign_in(client, provider)
    user = auth.authenticated(client.cookies.get(AUTH_COOKIE_NAME))
    assert user is not None
    csrf = user.csrf_token
    legacy_token = "legacy-browser-token"
    legacy = tours.save(legacy_token, _plan("Hoi An"))

    assert client.post("/api/saved-tours/claim").status_code == 403
    client.cookies.set(SAVED_TOURS_OWNER_COOKIE_NAME, legacy_token)
    claimed = client.post("/api/saved-tours/claim", headers={"X-CSRF-Token": csrf})
    assert claimed.status_code == 200
    assert claimed.json()["claimed_count"] == 1
    assert tours.get(legacy_token, legacy.id) is None
    assert tours.get_for_user(user.user_id, legacy.id) is not None

    assert client.post("/api/auth/logout").status_code == 403
    logged_out = client.post("/api/auth/logout", headers={"X-CSRF-Token": csrf})
    assert logged_out.status_code == 200
    assert logged_out.json() == {
        "logout_url": "https://auth0.example.test/v2/logout?returnTo=https://planner.example.test/"
    }
    assert 'gtp_auth=""' in logged_out.headers["set-cookie"]
    assert client.get("/api/auth/me").json() == {"authenticated": False}


def test_new_login_revokes_previous_account_session(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    provider = FakeOidcProvider("auth0|rotate", "rotate@example.test")
    client, auth, _ = _client(tmp_path, provider, monkeypatch)
    _sign_in(client, provider)
    previous_token = client.cookies.get(AUTH_COOKIE_NAME)
    assert auth.authenticated(previous_token) is not None

    _sign_in(client, provider)
    assert client.cookies.get(AUTH_COOKIE_NAME) != previous_token
    assert auth.authenticated(previous_token) is None


@pytest.mark.parametrize(
    "invalid",
    [
        "valid",
        "issuer",
        "audience",
        "nonce",
        "expired",
        "email_unverified",
        "email_missing",
    ],
)
def test_auth0_id_token_validates_identity_and_email_verification(
    invalid: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    provider = Auth0OidcProvider(
        issuer="https://tenant.example.test/",
        client_id="client-id",
        client_secret="test-secret",
    )
    claims = {
        "iss": "https://tenant.example.test/",
        "sub": "email|subject",
        "aud": "client-id",
        "iat": int(clock.time()),
        "exp": int(clock.time()) + 300,
        "nonce": "expected-nonce",
        "email": "verified@example.test",
        "email_verified": True,
    }
    changed = {
        "issuer": ("iss", "https://other.example.test/"),
        "audience": ("aud", "other-client"),
        "nonce": ("nonce", "wrong-nonce"),
        "expired": ("exp", int(clock.time()) - 1),
        "email_unverified": ("email_verified", False),
    }
    if invalid == "email_missing":
        claims.pop("email_verified")
    elif invalid != "valid":
        key, value = changed[invalid]
        claims[key] = value
    token = jwt.encode(
        claims, private_key, algorithm="RS256", headers={"kid": "test-key"}
    )
    monkeypatch.setattr(
        "grounded_travel_planner.auth.urlopen",
        lambda request, timeout: io.BytesIO(json.dumps({"id_token": token}).encode()),
    )
    monkeypatch.setattr(
        "grounded_travel_planner.auth.PyJWKClient",
        lambda url: SimpleNamespace(
            get_signing_key_from_jwt=lambda encoded: SimpleNamespace(
                key=private_key.public_key()
            )
        ),
    )

    def verify():
        return provider.verify_callback(
            code="test-code",
            nonce="expected-nonce",
            code_verifier="test-verifier",
            redirect_uri="https://planner.example.test/api/auth/callback",
        )

    if invalid == "valid":
        assert verify().email_verified is True
    elif invalid in {"email_unverified", "email_missing"}:
        assert verify().email_verified is False
    else:
        with pytest.raises(AuthError):
            verify()
