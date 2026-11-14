"""Offline account access and administrator HTTP boundary regressions."""

from __future__ import annotations

from datetime import date, datetime, time
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from grounded_travel_planner.auth import (
    AUTH_COOKIE_NAME,
    AccessChangeConflict,
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
from grounded_travel_planner.saved_tours import SavedTourRepository
from grounded_travel_planner.usage import UsageRepository, account_trace_ref
from grounded_travel_planner.web.api import create_app
from scripts.migrate_admin_accounts import find_bootstrap_user_id


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

    def read_project(self, *, project_name):
        assert project_name == "admin-test"
        return SimpleNamespace(id="project-id")

    def query(self, **kwargs):
        del kwargs

        async def rows():
            if self.error:
                raise self.error
            for item in self.items:
                yield item

        return rows()


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
    admin_id, _ = auth.find_or_create_user(
        VerifiedIdentity("https://id.example.test/", "admin", "admin@example.test")
    )
    member_id, _ = auth.find_or_create_user(
        VerifiedIdentity("https://id.example.test/", "member", "member@example.test")
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


def test_pending_account_needs_admin_grant_and_admin_routes_are_private(account_app):
    auth, _, admin, member, admin_id, member_id, admin_csrf, member_csrf, _ = (
        account_app
    )

    pending = member.get("/api/auth/me").json()
    assert pending["authenticated"] is True
    assert pending["access_status"] == "pending"
    assert (
        member.post("/api/session", headers={"X-CSRF-Token": member_csrf}).status_code
        == 403
    )
    assert member.get("/api/saved-tours").status_code == 403
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
    assert auth.get_user(member_id).access_status == "pending"

    granted = admin.post(
        f"/api/admin/users/{member_id}/access",
        json={"access_status": "active"},
        headers={"X-CSRF-Token": admin_csrf},
    )
    assert granted.status_code == 200
    assert granted.json()["access_status"] == "active"
    assert (
        member.post("/api/session", headers={"X-CSRF-Token": member_csrf}).status_code
        == 201
    )


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
                "https://id.example.test/", "member", "member@example.test"
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
