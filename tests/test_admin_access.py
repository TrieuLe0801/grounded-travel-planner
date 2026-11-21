"""Offline account access and administrator HTTP boundary regressions."""

from __future__ import annotations

import json
import sqlite3
from datetime import date, datetime, time, timedelta
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from grounded_travel_planner.auth import (
    AUTH_COOKIE_NAME,
    AccessChangeConflict,
    Auth0ManagementError,
    AuthError,
    AuthRepository,
    VerifiedIdentity,
)
from grounded_travel_planner.contracts import (
    PlaceRecommendation,
    ScheduleEntry,
    SightseeingPlan,
    SourceReference,
)
from grounded_travel_planner.saved_tours import SavedTourError, SavedTourRepository
from grounded_travel_planner.usage import UsageRepository, account_trace_ref
from grounded_travel_planner.web.api import create_app
from scripts.migrate_admin_accounts import find_bootstrap_user_id


def _runtime_model_settings(prompt: str = "") -> dict[str, object]:
    role = {
        "provider": "openai",
        "model": "model-test",
        "system_prompt": prompt,
        "temperature": 0.4,
        "top_p": 0.9,
        "max_output_tokens": 2048,
    }
    return {"coordinator": role, "planner": role, "chat": role}


class _Service:
    graph = object()

    def __init__(self) -> None:
        self.created = 0

    def create_session(self) -> str:
        self.created += 1
        return f"admin-test-thread-{self.created}"


class _Visuals:
    pass


class _FakeLangSmith:
    def __init__(self) -> None:
        self.runs = self
        self.items = []
        self.error = None
        self.queries = []

    def read_project(self, *, project_name):
        assert project_name == "admin-test"
        return SimpleNamespace(
            id="project-id",
            start_time=datetime.fromisoformat("2026-10-01T00:00:00+00:00"),
        )

    def query(self, **kwargs):
        self.queries.append(kwargs)

        async def rows():
            if self.error:
                raise self.error
            for item in self.items:
                yield item

        return rows()


class _FakeAuth0UserDeleter:
    def __init__(self) -> None:
        self.calls: list[tuple[tuple[str, str], ...]] = []
        self.errors: list[Exception] = []

    def delete_users(self, identities) -> None:
        self.calls.append(tuple(identities))
        if self.errors:
            raise self.errors.pop(0)


def _plan() -> SightseeingPlan:
    source = SourceReference(
        source_id="source",
        title="Fixture source",
        url="https://example.test/source",
        retrieval_query="Hue",
    )
    return SightseeingPlan(
        plan_id="admin-access-plan",
        destination="Hue",
        start_date=date(2026, 11, 1),
        day_count=1,
        entries=[
            ScheduleEntry(
                id="stop",
                day_index=1,
                start_time=time(9),
                end_time=time(10),
                place=PlaceRecommendation(
                    place_id="place",
                    name="Hue",
                    description="Fixture",
                    source_references=[source],
                    opening_hours="unverified",
                ),
            )
        ],
        summary="Fixture plan",
    )


@pytest.fixture
def account_app(tmp_path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("GTP_AUTH_SESSION_SECRET", "s" * 32)
    auth_path = tmp_path / "auth.sqlite"
    auth = AuthRepository(auth_path)
    auth.migrate()
    langsmith = _FakeLangSmith()
    usage = UsageRepository(client=langsmith, project_name="admin-test")
    tours = SavedTourRepository(tmp_path / "saved-tours.sqlite")
    app = create_app(
        _Service(),
        _Visuals(),
        saved_tour_repository=tours,
        auth_repository=auth,
        usage_repository=usage,
    )
    app.state.auth0_user_deleter = _FakeAuth0UserDeleter()
    admin_id, _ = auth.find_or_create_user(
        VerifiedIdentity(
            "https://id.example.test/", "admin", "admin@example.test", True
        )
    )
    member_id, _ = auth.find_or_create_user(
        VerifiedIdentity(
            "https://id.example.test/", "member", "member@example.test", True
        )
    )
    auth.bootstrap_admin(admin_id)
    admin_token, admin_csrf = auth.issue_session(admin_id, "admin@example.test")
    member_token, member_csrf = auth.issue_session(member_id, "member@example.test")
    admin = TestClient(app, base_url="https://localhost")
    member = TestClient(app, base_url="https://localhost")
    admin.cookies.set(AUTH_COOKIE_NAME, admin_token)
    member.cookies.set(AUTH_COOKIE_NAME, member_token)
    return (
        auth,
        tours,
        admin,
        member,
        admin_id,
        member_id,
        admin_csrf,
        member_csrf,
        langsmith,
    )


def test_new_account_is_active_without_admin_grant_and_admin_routes_are_private(
    account_app,
):
    auth, _, admin, member, admin_id, member_id, _, member_csrf, _ = account_app

    account = member.get("/api/auth/me").json()
    assert account["authenticated"] is True
    assert account["access_status"] == "active"
    assert (
        member.post("/api/session", headers={"X-CSRF-Token": member_csrf}).status_code
        == 201
    )
    assert member.get("/api/saved-tours").status_code == 200
    assert member.get("/api/admin/users").status_code == 403
    assert (
        member.post(
            f"/api/admin/users/{admin_id}/access",
            json={"access_status": "blocked"},
            headers={"X-CSRF-Token": member_csrf},
        ).status_code
        == 403
    )

    page = admin.get("/api/admin/users", params={"limit": 1})
    assert page.status_code == 200
    assert len(page.json()["items"]) == 1
    assert page.json()["has_more"] is True
    assert page.json()["next_cursor"] is not None
    missing_csrf = admin.post(
        f"/api/admin/users/{member_id}/access", json={"access_status": "active"}
    )
    assert missing_csrf.status_code == 403
    assert auth.get_user(member_id).access_status == "active"


def test_block_revokes_sessions_and_regrant_keeps_account_and_archive(account_app):
    auth, tours, admin, member, admin_id, member_id, admin_csrf, member_csrf, _ = (
        account_app
    )
    auth.set_access(member_id, active=True, actor_user_id=admin_id)
    assert (
        member.post("/api/session", headers={"X-CSRF-Token": member_csrf}).status_code
        == 201
    )
    saved = tours.save_for_user(member_id, _plan())
    assert member.get("/api/saved-tours").json()["items"][0]["id"] == saved.id

    blocked = admin.post(
        f"/api/admin/users/{member_id}/access",
        json={"access_status": "blocked"},
        headers={"X-CSRF-Token": admin_csrf},
    )
    assert blocked.status_code == 200
    assert member.get("/api/auth/me").json() == {"authenticated": False}
    assert member.get("/api/session").status_code == 401
    assert member.get("/api/saved-tours").status_code == 401
    assert member.post(
        "/api/turns",
        json={"message": "Create Hue"},
        headers={"X-CSRF-Token": member_csrf},
    ).status_code in {401, 403}

    assert (
        admin.post(
            f"/api/admin/users/{member_id}/access",
            json={"access_status": "active"},
            headers={"X-CSRF-Token": admin_csrf},
        ).status_code
        == 200
    )
    assert member.get("/api/auth/me").json() == {"authenticated": False}
    assert (
        auth.find_or_create_user(
            VerifiedIdentity(
                "https://id.example.test/", "member", "member@example.test", True
            )
        )[0]
        == member_id
    )
    new_token, new_csrf = auth.issue_session(member_id, "member@example.test")
    member.cookies.set(AUTH_COOKIE_NAME, new_token)
    assert (
        member.post("/api/session", headers={"X-CSRF-Token": new_csrf}).status_code
        == 201
    )
    assert member.get("/api/saved-tours").json()["items"][0]["id"] == saved.id


def test_last_admin_cannot_block_self(account_app):
    auth, _, admin, _, admin_id, _, admin_csrf, _, _ = account_app

    denied = admin.post(
        f"/api/admin/users/{admin_id}/access",
        json={"access_status": "blocked"},
        headers={"X-CSRF-Token": admin_csrf},
    )
    assert denied.status_code == 409
    assert auth.get_user(admin_id).access_status == "active"
    with pytest.raises(AccessChangeConflict):
        auth.bootstrap_admin(admin_id)


def test_admin_usage_page_shows_account_totals_and_unknown_cost(account_app):
    _, _, admin, member, _, member_id, _, _, langsmith = account_app
    langsmith.items.append(
        SimpleNamespace(
            metadata={
                "account_ref": account_trace_ref(member_id),
                "ls_provider": "openai",
                "ls_model_name": "unpriced",
                "agent_role": "chat",
            },
            run_type="LLM",
            name="unpriced",
            start_time=datetime.fromisoformat("2026-11-01T12:00:00+00:00"),
            prompt_tokens=32,
            completion_tokens=11,
            total_cost=None,
            price_model_id=None,
        )
    )

    assert member.get("/api/admin/users").status_code == 403
    page = admin.get("/api/admin/users", params={"limit": 50})
    assert page.status_code == 200
    assert page.json()["usage_available"] is True
    assert all(
        query["max_start_time"] - query["min_start_time"] <= timedelta(days=400)
        for query in langsmith.queries
    )
    row = next(item for item in page.json()["items"] if item["id"] == member_id)
    assert row["input_tokens"] == 32
    assert row["output_tokens"] == 11
    assert row["estimated_cost_usd"] is None
    assert row["unpriced_calls"] == 1
    detail = admin.get(f"/api/admin/users/{member_id}/usage")
    assert detail.status_code == 200
    assert detail.json()["by_model"][0]["model"] == "unpriced"
    assert detail.json()["input_tokens"] == 32
    assert member.get(f"/api/admin/users/{member_id}/usage").status_code == 403
    outside = admin.get(
        f"/api/admin/users/{member_id}/usage",
        params={"start": "2100-01-01"},
    )
    assert outside.status_code == 200
    assert outside.json()["input_tokens"] == 0


def test_admin_usage_includes_confirmed_former_account_alias(account_app, tmp_path):
    auth, _, admin, _, _, member_id, _, _, langsmith = account_app
    former_id = "removed-member-account"
    with sqlite3.connect(tmp_path / "auth.sqlite") as connection:
        connection.execute(
            """INSERT INTO account_usage_aliases
            (former_user_id, canonical_user_id) VALUES (?, ?)""",
            (former_id, member_id),
        )
    assert auth.get_user(former_id) is None
    for account_id, prompt, completion, cost, model in (
        (member_id, 10, 2, 0.01, "current-model"),
        (former_id, 40, 8, 0.02, "former-model"),
    ):
        langsmith.items.append(
            SimpleNamespace(
                metadata={
                    "account_ref": account_trace_ref(account_id),
                    "ls_provider": "openai",
                    "ls_model_name": model,
                    "agent_role": "chat",
                },
                run_type="llm",
                name=model,
                start_time=datetime.fromisoformat("2026-11-01T12:00:00+00:00"),
                prompt_tokens=prompt,
                completion_tokens=completion,
                total_cost=cost,
                price_model_id="price-id",
            )
        )

    page = admin.get("/api/admin/users")
    row = next(item for item in page.json()["items"] if item["id"] == member_id)
    assert row["input_tokens"] == 50
    assert row["output_tokens"] == 10
    assert row["estimated_cost_usd"] == pytest.approx(0.03)
    detail = admin.get(f"/api/admin/users/{member_id}/usage")
    assert detail.status_code == 200
    assert detail.json()["input_tokens"] == 50
    assert {item["model"] for item in detail.json()["by_model"]} == {
        "current-model",
        "former-model",
    }

    with sqlite3.connect(tmp_path / "auth.sqlite") as connection:
        connection.execute("DROP TABLE account_usage_aliases")
    unavailable = admin.get("/api/admin/users")
    assert unavailable.json()["usage_available"] is False
    assert row["id"] in {item["id"] for item in unavailable.json()["items"]}
    assert admin.get(f"/api/admin/users/{member_id}/usage").status_code == 503


def test_langsmith_outage_does_not_block_account_access_management(account_app):
    auth, _, admin, _, _, member_id, admin_csrf, _, langsmith = account_app
    langsmith.error = RuntimeError("provider failure")

    page = admin.get("/api/admin/users")
    assert page.status_code == 200
    assert page.json()["usage_available"] is False
    assert all(item["input_tokens"] is None for item in page.json()["items"])
    assert all(item["output_tokens"] is None for item in page.json()["items"])
    assert admin.get(f"/api/admin/users/{member_id}/usage").status_code == 503

    granted = admin.post(
        f"/api/admin/users/{member_id}/access",
        json={"access_status": "active"},
        headers={"X-CSRF-Token": admin_csrf},
    )
    assert granted.status_code == 200
    assert auth.get_user(member_id).access_status == "active"


def test_bootstrap_email_resolves_one_existing_account_across_pages():
    accounts = [SimpleNamespace(id=str(index), email=None) for index in range(100)]
    accounts.append(SimpleNamespace(id="chosen", email="admin@example.test"))

    class Accounts:
        def list_users(self, limit=100, offset=0):
            return accounts[offset : offset + limit]

    repository = Accounts()
    assert find_bootstrap_user_id(repository, " ADMIN@example.test ") == "chosen"
    accounts.append(SimpleNamespace(id="duplicate", email="ADMIN@example.test"))
    with pytest.raises(AuthError, match="exactly one"):
        find_bootstrap_user_id(repository, "admin@example.test")
    with pytest.raises(AuthError, match="exactly one"):
        find_bootstrap_user_id(repository, "missing@example.test")


def test_admin_deletes_all_auth0_identities_tours_and_account_data(account_app):
    auth, tours, admin, member, admin_id, member_id, admin_csrf, _, _ = account_app
    member_user = auth.get_user(member_id)
    assert member_user is not None
    auth.link_google_identity(
        VerifiedIdentity(
            "https://id.example.test/",
            "google-oauth2|linked-member",
            member_user.email,
            True,
        ),
        member_id,
    )
    tours.save_for_user(member_id, _plan())
    tours.save_for_user(admin_id, _plan())
    with sqlite3.connect(auth._database_path) as connection:
        connection.execute(
            "INSERT INTO account_usage_aliases VALUES (?, ?)",
            ("former-member-id", member_id),
        )
        connection.execute(
            "INSERT INTO account_usage_aliases VALUES (?, ?)",
            (member_id, admin_id),
        )

    result = admin.post(
        f"/api/admin/users/{member_id}/delete",
        headers={"X-CSRF-Token": admin_csrf},
    )

    assert result.status_code == 204
    deleted_subjects = {
        subject for _, subject in admin.app.state.auth0_user_deleter.calls[-1]
    }
    assert deleted_subjects == {"member", "google-oauth2|linked-member"}
    account = auth.get_user(member_id)
    assert account is not None
    assert (account.email, account.access_status, account.is_admin) == (
        None,
        "deleted",
        False,
    )
    assert member.get("/api/auth/me").json() == {"authenticated": False}
    assert member_id not in {user.id for user in auth.list_users()}
    assert tours.list_for_user(member_id).items == []
    assert len(tours.list_for_user(admin_id).items) == 1
    with sqlite3.connect(auth._database_path) as connection:
        assert (
            connection.execute(
                "SELECT COUNT(*) FROM auth_identities WHERE user_id = ?", (member_id,)
            ).fetchone()[0]
            == 0
        )
        assert (
            connection.execute(
                "SELECT COUNT(*) FROM auth_sessions WHERE user_id = ?", (member_id,)
            ).fetchone()[0]
            == 0
        )
        assert (
            connection.execute(
                """SELECT COUNT(*) FROM account_usage_aliases
            WHERE former_user_id = ? OR canonical_user_id = ?""",
                (member_id, member_id),
            ).fetchone()[0]
            == 0
        )
        actions = {
            row[0]
            for row in connection.execute(
                "SELECT action FROM account_access_events WHERE user_id = ?",
                (member_id,),
            )
        }
    assert {"deletion_started", "deleted"} <= actions


def test_auth0_delete_error_preserves_local_account_and_session(account_app):
    auth, tours, admin, member, _, member_id, admin_csrf, _, _ = account_app
    tours.save_for_user(member_id, _plan())
    deleter = admin.app.state.auth0_user_deleter
    deleter.errors.append(Auth0ManagementError("provider unavailable"))

    result = admin.post(
        f"/api/admin/users/{member_id}/delete",
        headers={"X-CSRF-Token": admin_csrf},
    )

    assert result.status_code == 502
    account = auth.get_user(member_id)
    assert account is not None
    assert (account.email, account.access_status) == (
        "member@example.test",
        "active",
    )
    assert member.get("/api/auth/me").json()["authenticated"] is True
    assert len(tours.list_for_user(member_id).items) == 1
    assert admin.get("/api/admin/users").status_code == 200


def test_account_deletion_retries_after_auth0_and_local_partial_failures(
    account_app, monkeypatch: pytest.MonkeyPatch
):
    auth, tours, admin, member, _, member_id, admin_csrf, _, _ = account_app
    member_user = auth.get_user(member_id)
    assert member_user is not None
    auth.link_google_identity(
        VerifiedIdentity(
            "https://id.example.test/",
            "google-oauth2|retry-member",
            member_user.email,
            True,
        ),
        member_id,
    )
    deleter = admin.app.state.auth0_user_deleter
    deleter.errors.append(Auth0ManagementError("partial provider failure"))
    path = f"/api/admin/users/{member_id}/delete"

    auth0_failure = admin.post(path, headers={"X-CSRF-Token": admin_csrf})
    assert auth0_failure.status_code == 502
    assert auth.get_user(member_id).access_status == "active"
    assert member.get("/api/auth/me").json()["authenticated"] is True
    assert len(deleter.calls) == 1

    original_delete_all = tours.delete_all_for_user
    calls = 0

    def fail_once(user_id: str) -> int:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise SavedTourError("temporary archive failure")
        return original_delete_all(user_id)

    monkeypatch.setattr(tours, "delete_all_for_user", fail_once)
    local_failure = admin.post(path, headers={"X-CSRF-Token": admin_csrf})
    assert local_failure.status_code == 503
    assert auth.get_user(member_id).access_status == "deleting"
    assert member.get("/api/auth/me").json() == {"authenticated": False}
    assert admin.get("/api/admin/users").json()["items"]
    assert any(
        user["id"] == member_id and user["access_status"] == "deleting"
        for user in admin.get("/api/admin/users").json()["items"]
    )

    completed = admin.post(path, headers={"X-CSRF-Token": admin_csrf})
    assert completed.status_code == 204
    assert auth.get_user(member_id).access_status == "deleted"
    assert len(deleter.calls) == 3
    assert len(deleter.calls[-1]) == 2


def test_admin_delete_requires_csrf_and_rejects_self_delete(account_app):
    _, _, admin, member, admin_id, member_id, admin_csrf, member_csrf, _ = account_app
    assert (
        member.post(
            f"/api/admin/users/{member_id}/delete",
            headers={"X-CSRF-Token": member_csrf},
        ).status_code
        == 403
    )
    assert admin.post(f"/api/admin/users/{member_id}/delete").status_code == 403
    result = admin.post(
        f"/api/admin/users/{admin_id}/delete",
        headers={"X-CSRF-Token": admin_csrf},
    )
    assert result.status_code == 409
    assert admin.app.state.auth0_user_deleter.calls == []


def test_admin_runtime_model_settings_are_private_validated_and_audited(account_app):
    auth, _, admin, member, admin_id, _, admin_csrf, member_csrf, _ = account_app
    auth.migrate_runtime_model_settings()
    original = _runtime_model_settings()
    auth.update_runtime_model_settings(json.dumps(original), "[]", admin_id)

    assert admin.get("/api/admin/model-settings").status_code == 200
    assert member.get("/api/admin/model-settings").status_code == 403
    assert admin.put("/api/admin/model-settings", json=original).status_code == 403
    assert (
        member.put(
            "/api/admin/model-settings",
            json=original,
            headers={"X-CSRF-Token": member_csrf},
        ).status_code
        == 403
    )

    settings = _runtime_model_settings("Prefer concise, sourced proposals.")
    settings["planner"] = {
        **settings["planner"],
        "model": "planner-v2",
        "temperature": 0.2,
    }
    saved = admin.put(
        "/api/admin/model-settings",
        json=settings,
        headers={"X-CSRF-Token": admin_csrf},
    )
    assert saved.status_code == 200
    assert saved.json()["revision"] == 2
    assert saved.json()["settings"] == settings
    assert json.loads(auth.get_runtime_model_settings()[0]) == settings

    with auth._connection() as connection:
        events = connection.execute(
            "SELECT actor_user_id, changed_fields_json FROM runtime_model_settings_events"
        ).fetchall()
    assert events[-1]["actor_user_id"] == admin_id
    changed_fields = json.loads(events[-1]["changed_fields_json"])
    assert "planner.model" in changed_fields
    assert "planner.system_prompt" in changed_fields
    assert "Prefer concise, sourced proposals." not in events[-1]["changed_fields_json"]

    secret_payload = json.loads(json.dumps(settings))
    secret_payload["chat"]["api_key"] = "should-be-rejected"
    invalid = admin.put(
        "/api/admin/model-settings",
        json=secret_payload,
        headers={"X-CSRF-Token": admin_csrf},
    )
    assert invalid.status_code == 422
    assert json.loads(auth.get_runtime_model_settings()[0]) == settings


def test_admin_model_settings_requires_explicit_database_migration(account_app):
    _, _, admin, _, _, _, _, _, _ = account_app

    response = admin.get("/api/admin/model-settings")

    assert response.status_code == 503
    assert "scripts/migrate_runtime_model_settings.py" in response.json()["detail"]


def test_runtime_model_settings_update_rolls_back_if_audit_insert_fails(account_app):
    auth, _, admin, _, admin_id, _, admin_csrf, _, _ = account_app
    auth.migrate_runtime_model_settings()
    original = _runtime_model_settings()
    auth.update_runtime_model_settings(json.dumps(original), "[]", admin_id)
    with auth._connection() as connection:
        connection.execute("""CREATE TRIGGER reject_runtime_model_audit
            BEFORE INSERT ON runtime_model_settings_events
            BEGIN SELECT RAISE(ABORT, 'audit write rejected'); END""")

    changed = _runtime_model_settings("new instruction")
    response = admin.put(
        "/api/admin/model-settings",
        json=changed,
        headers={"X-CSRF-Token": admin_csrf},
    )
    assert response.status_code == 503
    stored, revision = auth.get_runtime_model_settings()
    assert json.loads(stored) == original
    assert revision == 1
