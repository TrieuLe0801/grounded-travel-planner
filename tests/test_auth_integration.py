"""Offline Auth0 BFF contracts with deterministic provider fixtures."""

from __future__ import annotations

import io
import json
import time as clock
from datetime import date, time
from types import SimpleNamespace
from urllib.parse import parse_qs, urlparse

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient

from grounded_travel_planner.auth import (
    AUTH_COOKIE_NAME,
    AUTH_PENDING_SECONDS,
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
    create_app,
)


class FakeOidcProvider:
    """Records BFF inputs without making an Auth0 or network call."""

    def __init__(self, subject: str, email: str) -> None:
        self.identity = VerifiedIdentity(
            issuer="https://tenant.example.test/", subject=subject, email=email
        )
        self.authorization_calls: list[dict[str, str]] = []
        self.callback_calls: list[dict[str, str]] = []

    def authorization_url(
        self, *, state: str, nonce: str, code_verifier: str, redirect_uri: str
    ) -> str:
        self.authorization_calls.append(
            {
                "state": state,
                "nonce": nonce,
                "code_verifier": code_verifier,
                "redirect_uri": redirect_uri,
            }
        )
        return f"https://auth0.example.test/authorize?state={state}"

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


class FakeService:
    graph = object()


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
    tmp_path, provider: FakeOidcProvider, monkeypatch: pytest.MonkeyPatch
) -> tuple[TestClient, AuthRepository, SavedTourRepository]:
    monkeypatch.setenv("GTP_AUTH_SESSION_SECRET", "s" * 32)
    monkeypatch.setenv("GTP_AUTH_PUBLIC_ORIGIN", "https://planner.example.test")
    auth = AuthRepository(tmp_path / "auth.sqlite")
    auth.migrate()
    tours = SavedTourRepository(tmp_path / "saved-tours.sqlite")
    return (
        TestClient(
            create_app(
                FakeService(),
                FakeVisuals(),
                saved_tour_repository=tours,
                auth_provider=provider,
                auth_repository=auth,
            ),
            base_url="https://planner.example.test",
        ),
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
    assert (
        provider.callback_calls[0]["nonce"] == provider.authorization_calls[0]["nonce"]
    )
    assert (
        provider.callback_calls[0]["code_verifier"]
        == provider.authorization_calls[0]["code_verifier"]
    )
    return client.get("/api/auth/me").json()["csrf_token"]


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


@pytest.mark.parametrize("invalid", ["valid", "issuer", "audience", "nonce", "expired"])
def test_auth0_id_token_rejects_invalid_identity_claims(
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
    }
    changed = {
        "issuer": ("iss", "https://other.example.test/"),
        "audience": ("aud", "other-client"),
        "nonce": ("nonce", "wrong-nonce"),
        "expired": ("exp", int(clock.time()) - 1),
    }
    if invalid != "valid":
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
        assert verify().subject == "email|subject"
    else:
        with pytest.raises(AuthError):
            verify()
