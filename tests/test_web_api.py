"""Offline contract tests for the JavaScript web adapter."""

from __future__ import annotations

from concurrent.futures import Future
from datetime import date, time
from threading import Event

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from grounded_travel_planner.auth import (
    AUTH_COOKIE_NAME,
    AuthRepository,
    VerifiedIdentity,
)
from grounded_travel_planner.contracts import (
    AgentResponse,
    PlaceRecommendation,
    ResponseStatus,
    ScheduleEntry,
    SightseeingPlan,
    SourceReference,
    TripRequest,
    ValidationIssue,
)
from grounded_travel_planner.ui.turn_runner import PendingTurn, TurnRunner
from grounded_travel_planner.visuals import PlaceVisual
from grounded_travel_planner.web.api import (
    SessionCapacityExceeded,
    SessionStore,
    create_app,
)
from grounded_travel_planner.web.turn_rate_limit import (
    TurnRateLimiter,
    TurnRateLimitExceeded,
)


def _plan(destination: str, revision: int = 1) -> SightseeingPlan:
    source = SourceReference(
        source_id="fixture-source",
        title=f"{destination} visitor information",
        url="https://example.test/visitor-information",
        retrieval_query=destination,
    )
    place = PlaceRecommendation(
        place_id="fixture-place",
        name=f"{destination} landmark",
        description="Offline fixture recommendation.",
        source_references=[source],
        opening_hours="unverified",
    )
    return SightseeingPlan(
        plan_id=f"plan-{destination.casefold()}",
        destination=destination,
        start_date=date(2026, 11, 1),
        day_count=2,
        entries=[
            ScheduleEntry(
                id="fixture-entry",
                day_index=1,
                start_time=time(9),
                end_time=time(10, 30),
                place=place,
            )
        ],
        summary=f"Offline plan for {destination}.",
        revision=revision,
    )


class FakeTravelPlannerService:
    """Deterministic service replacement; it never reaches model or search."""

    graph = object()

    def __init__(self) -> None:
        self.created_sessions = 0
        self.turns: list[dict[str, object]] = []
        self.block_started = Event()
        self.release_block = Event()
        self.graph_image_calls = 0
        self.graph_image = b"\x89PNG\r\n\x1a\noffline graph"

    def create_session(self) -> str:
        self.created_sessions += 1
        return f"thread-{self.created_sessions}"

    def get_graph_image(self) -> bytes:
        self.graph_image_calls += 1
        return self.graph_image

    def handle_turn(self, **kwargs: object) -> AgentResponse:
        self.turns.append(kwargs)
        message = str(kwargs["message"])
        current_plan = kwargs.get("current_plan")
        request = kwargs.get("request")
        if message == "block":
            self.block_started.set()
            assert self.release_block.wait(timeout=3)
        if message == "reject":
            return AgentResponse(
                status=ResponseStatus.REJECTED,
                message="Lịch trình trước đó đã được giữ nguyên.",
                current_plan=(
                    current_plan if isinstance(current_plan, SightseeingPlan) else None
                ),
                validation_issues=[
                    ValidationIssue(
                        code="schedule_overlap", message="Offline rejected change."
                    )
                ],
            )
        if isinstance(request, TripRequest):
            plan = _plan(request.destination)
        elif isinstance(current_plan, SightseeingPlan):
            plan = current_plan.model_copy(deep=True)
            plan.revision += 1
        else:
            plan = _plan("Fallback")
        return AgentResponse(
            status=ResponseStatus.COMMITTED,
            message="Offline committed plan.",
            current_plan=plan,
            committed=True,
            metadata={"session_summary": "summary-" + ("s" * 1300)},
        )


class FakeVisualService:
    def __init__(self) -> None:
        self.plans: list[SightseeingPlan] = []
        self.fail = False

    def resolve(self, plan: SightseeingPlan) -> dict[str, PlaceVisual]:
        self.plans.append(plan)
        if self.fail:
            raise RuntimeError("Optional image lookup unavailable")
        return {
            "fixture-entry": PlaceVisual(
                place_name=plan.entries[0].place.name,
                image_url="https://images.example.test/fixture.jpg",
                image_page_url="https://commons.example.test/File:fixture.jpg",
                image_alt="Fixture landmark image",
                image_credit="Fixture photographer",
                image_license="CC BY-SA 4.0",
            )
        }


class _SignallingTurnRunner(TurnRunner):
    """Expose completion only for deterministic API regression synchronization."""

    def __init__(self) -> None:
        super().__init__(max_workers=1, max_pending_turns=1)
        self.completed = Event()

    def _release_pending_slot(self, future: Future[AgentResponse]) -> None:
        super()._release_pending_slot(future)
        self.completed.set()


class _FakeClock:
    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now


def _start(client: TestClient, headers: dict[str, str] | None = None) -> None:
    response = client.post("/api/session", headers=headers)
    assert response.status_code == 201


def _create(client: TestClient, destination: str) -> dict[str, object]:
    accepted = client.post(
        "/api/turns",
        json={
            "message": f"Create {destination}",
            "request": {
                "destination": destination,
                "start_date": "2026-11-01",
                "day_count": 2,
            },
        },
    )
    assert accepted.status_code == 202
    session = client.get("/api/session")
    assert session.status_code == 200
    return session.json()


def test_sessions_are_isolated_and_rejected_turn_keeps_prior_plan() -> None:
    service = FakeTravelPlannerService()
    app = create_app(service, FakeVisualService(), require_auth=False)
    first = TestClient(app, base_url="https://localhost")
    second = TestClient(app, base_url="https://localhost")
    _start(first)
    _start(second)

    first_state = _create(first, "Hue")
    second_state = _create(second, "Da Nang")
    assert first_state["plan"]["destination"] == "Hue"
    assert second_state["plan"]["destination"] == "Da Nang"

    assert first.post("/api/turns", json={"message": "reject"}).status_code == 202
    rejected = first.get("/api/session").json()
    assert rejected["plan"] == first_state["plan"]
    assert rejected["response"]["status"] == "rejected"
    assert rejected["response"]["validation_issues"][0]["code"] == "schedule_overlap"
    assert second.get("/api/session").json()["plan"] == second_state["plan"]


def test_pending_turn_rejects_competing_submission() -> None:
    service = FakeTravelPlannerService()
    client = TestClient(
        create_app(service, FakeVisualService(), require_auth=False),
        base_url="https://localhost",
    )
    _start(client)

    assert client.post("/api/turns", json={"message": "block"}).status_code == 202
    assert service.block_started.wait(timeout=1)
    competing = client.post("/api/turns", json={"message": "another turn"})
    assert competing.status_code == 409
    assert competing.json()["detail"] == "Một yêu cầu đang được xử lý."

    service.release_block.set()
    completed = client.get("/api/session")
    assert completed.status_code == 200
    assert completed.json()["pending"] is False


def test_global_turn_capacity_rejects_another_session_without_mutating_it() -> None:
    service = FakeTravelPlannerService()
    runner = _SignallingTurnRunner()
    app = create_app(
        service,
        FakeVisualService(),
        turn_runner=runner,
        require_auth=False,
    )
    first = TestClient(app, base_url="https://localhost")
    second = TestClient(app, base_url="https://localhost")
    _start(first)
    _start(second)

    assert first.post("/api/turns", json={"message": "block"}).status_code == 202
    assert service.block_started.wait(timeout=1)
    before = second.get("/api/session").json()

    rejected = second.post("/api/turns", json={"message": "blocked globally"})
    assert rejected.status_code == 429
    assert (
        rejected.json()["detail"]
        == "Hệ thống đang xử lý quá nhiều yêu cầu. Vui lòng thử lại sau."
    )
    assert second.get("/api/session").json() == before

    service.release_block.set()
    assert runner.completed.wait(timeout=1)
    assert first.get("/api/session").json()["pending"] is False
    assert (
        second.post(
            "/api/turns", json={"message": "accepted after release"}
        ).status_code
        == 202
    )


def test_turn_rate_limiter_expires_principal_window() -> None:
    clock = _FakeClock()
    limiter = TurnRateLimiter(per_principal_limit=1, clock=clock)

    accepted = limiter.reserve("session:one")
    assert not isinstance(accepted, TurnRateLimitExceeded)
    rejected = limiter.reserve("session:one")
    assert isinstance(rejected, TurnRateLimitExceeded)
    assert rejected.scope == "principal"
    assert rejected.retry_after_seconds == 3600

    clock.now = 3600
    assert not isinstance(limiter.reserve("session:one"), TurnRateLimitExceeded)


def test_turn_rate_limiter_reads_optional_global_limit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("GTP_TURN_LIMIT_PER_HOUR", "3")
    monkeypatch.setenv("GTP_TURN_GLOBAL_LIMIT_PER_HOUR", "1")
    limiter = TurnRateLimiter.from_environment()

    assert not isinstance(limiter.reserve("session:one"), TurnRateLimitExceeded)
    global_rejection = limiter.reserve("session:two")
    assert isinstance(global_rejection, TurnRateLimitExceeded)
    assert global_rejection.scope == "global"


def test_turn_rate_limiter_prunes_expired_principals_before_capacity_check() -> None:
    clock = _FakeClock()
    limiter = TurnRateLimiter(
        per_principal_limit=1,
        max_principals=2,
        window_seconds=60,
        clock=clock,
    )
    assert not isinstance(limiter.reserve("session:one"), TurnRateLimitExceeded)
    assert not isinstance(limiter.reserve("session:two"), TurnRateLimitExceeded)

    full = limiter.reserve("session:three")
    assert isinstance(full, TurnRateLimitExceeded)
    assert full.scope == "principal_capacity"
    assert full.retry_after_seconds == 60

    clock.now = 60
    assert not isinstance(limiter.reserve("session:three"), TurnRateLimitExceeded)


def test_turn_quota_isolated_by_anonymous_session_and_does_not_mutate_rejection() -> (
    None
):
    service = FakeTravelPlannerService()
    limiter = TurnRateLimiter(per_principal_limit=1)
    app = create_app(
        service,
        FakeVisualService(),
        turn_rate_limiter=limiter,
        require_auth=False,
    )
    first = TestClient(app, base_url="https://localhost")
    second = TestClient(app, base_url="https://localhost")
    _start(first)
    _start(second)

    assert first.post("/api/turns", json={"message": "first"}).status_code == 202
    assert first.get("/api/session").status_code == 200
    before = first.get("/api/session").json()

    rejected = first.post("/api/turns", json={"message": "too many"})
    assert rejected.status_code == 429
    assert rejected.headers["retry-after"] == "3600"
    assert first.get("/api/session").json() == before
    assert (
        second.post("/api/turns", json={"message": "separate session"}).status_code
        == 202
    )


def test_turn_quota_shares_verified_account_across_sessions(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("GTP_AUTH_SESSION_SECRET", "s" * 32)
    auth = AuthRepository(tmp_path / "auth.sqlite")
    auth.migrate()
    user_id, email = auth.find_or_create_user(
        VerifiedIdentity("https://tenant.example.test/", "auth0|shared")
    )
    auth.bootstrap_admin(user_id)
    token, csrf = auth.issue_session(user_id, email)
    service = FakeTravelPlannerService()
    app = create_app(
        service,
        FakeVisualService(),
        auth_repository=auth,
        turn_rate_limiter=TurnRateLimiter(per_principal_limit=1),
    )
    first = TestClient(app, base_url="https://localhost")
    second = TestClient(app, base_url="https://localhost")
    first.cookies.set(AUTH_COOKIE_NAME, token)
    second.cookies.set(AUTH_COOKIE_NAME, token)
    headers = {"X-CSRF-Token": csrf}
    _start(first, headers)
    _start(second, headers)

    assert (
        first.post(
            "/api/turns", json={"message": "account first"}, headers=headers
        ).status_code
        == 202
    )
    assert first.get("/api/session").status_code == 200
    rejected = second.post(
        "/api/turns", json={"message": "account second"}, headers=headers
    )
    assert rejected.status_code == 429
    assert (
        rejected.json()["detail"]
        == "Bạn đã dùng hết lượt lập lịch trong giờ này. Vui lòng thử lại sau."
    )


def test_global_turn_quota_rejects_before_session_mutation() -> None:
    service = FakeTravelPlannerService()
    app = create_app(
        service,
        FakeVisualService(),
        turn_rate_limiter=TurnRateLimiter(per_principal_limit=10, global_limit=1),
        require_auth=False,
    )
    first = TestClient(app, base_url="https://localhost")
    second = TestClient(app, base_url="https://localhost")
    _start(first)
    _start(second)

    assert first.post("/api/turns", json={"message": "first"}).status_code == 202
    assert first.get("/api/session").status_code == 200
    before = second.get("/api/session").json()
    rejected = second.post("/api/turns", json={"message": "global"})
    assert rejected.status_code == 429
    assert rejected.headers["retry-after"] == "3600"
    assert second.get("/api/session").json() == before


def test_turn_quota_principal_capacity_returns_service_limit_message() -> None:
    service = FakeTravelPlannerService()
    limiter = TurnRateLimiter(per_principal_limit=10, max_principals=1)
    app = create_app(
        service, FakeVisualService(), turn_rate_limiter=limiter, require_auth=False
    )
    first = TestClient(app, base_url="https://localhost")
    second = TestClient(app, base_url="https://localhost")
    _start(first)
    _start(second)

    assert first.post("/api/turns", json={"message": "first"}).status_code == 202
    assert first.get("/api/session").status_code == 200
    before = second.get("/api/session").json()
    rejected = second.post("/api/turns", json={"message": "principal cap"})

    assert rejected.status_code == 429
    assert rejected.headers["retry-after"] == "3600"
    assert rejected.json()["detail"] == (
        "Hệ thống đã đạt giới hạn lượt lập lịch tạm thời. Vui lòng thử lại sau."
    )
    assert second.get("/api/session").json() == before


def test_session_store_caps_idle_sessions_and_reset_replaces_its_predecessor() -> None:
    service = FakeTravelPlannerService()
    clock = _FakeClock()
    store = SessionStore(max_sessions=2, idle_seconds=60, clock=clock)
    first_id, first = store.create(service)  # type: ignore[arg-type]
    second_id, _ = store.create(service)  # type: ignore[arg-type]

    with pytest.raises(SessionCapacityExceeded):
        store.create(service)  # type: ignore[arg-type]
    assert store.session_count == 2

    with first.lock:
        first.language = "en"
    replacement_id, replacement = store.replace(
        first_id, service  # type: ignore[arg-type]
    )
    assert replacement_id != first_id
    assert replacement.language == "en"
    assert store.session_count == 2
    with pytest.raises(HTTPException) as removed:
        store.get(first_id)
    assert removed.value.status_code == 401

    next_replacement_id, next_replacement = store.replace(
        replacement_id, service  # type: ignore[arg-type]
    )
    assert next_replacement_id != replacement_id
    assert next_replacement.language == "en"
    assert store.session_count == 2

    clock.now = 61
    with pytest.raises(HTTPException) as expired:
        store.get(second_id)
    assert expired.value.status_code == 401
    assert store.session_count == 0
    store.create(service)  # type: ignore[arg-type]
    assert store.session_count == 1


def test_session_endpoint_returns_503_when_store_is_at_capacity() -> None:
    service = FakeTravelPlannerService()
    store = SessionStore(max_sessions=1)
    client = TestClient(
        create_app(
            service, FakeVisualService(), session_store=store, require_auth=False
        ),
        base_url="https://localhost",
    )

    assert client.post("/api/session").status_code == 201
    exhausted = client.post("/api/session")
    assert exhausted.status_code == 503
    assert (
        exhausted.json()["detail"]
        == "Hệ thống đang có quá nhiều phiên hoạt động. Vui lòng thử lại sau."
    )
    assert store.session_count == 1


def test_idle_expiry_keeps_running_turn_but_releases_uncollected_completion() -> None:
    service = FakeTravelPlannerService()
    clock = _FakeClock()
    store = SessionStore(max_sessions=2, idle_seconds=60, clock=clock)
    _, running_session = store.create(service)  # type: ignore[arg-type]
    _, completed_session = store.create(service)  # type: ignore[arg-type]
    running_future: Future[AgentResponse] = Future()
    completed_future: Future[AgentResponse] = Future()
    completed_future.set_result(
        AgentResponse(status=ResponseStatus.REJECTED, message="Done")
    )
    for session, future in (
        (running_session, running_future),
        (completed_session, completed_future),
    ):
        session.pending = PendingTurn(
            token="test-token",
            thread_id=session.thread_id,
            message="test",
            current_plan=None,
            request=None,
            future=future,
        )

    clock.now = 61
    assert store.session_count == 1
    running_future.set_result(
        AgentResponse(status=ResponseStatus.REJECTED, message="Done")
    )
    assert store.session_count == 0


def test_api_bounds_conversation_summary_and_reset_session() -> None:
    service = FakeTravelPlannerService()
    client = TestClient(
        create_app(service, FakeVisualService(), require_auth=False),
        base_url="https://localhost",
    )
    _start(client)

    for index in range(7):
        accepted = client.post("/api/turns", json={"message": f"turn-{index}"})
        assert accepted.status_code == 202
        assert client.get("/api/session").status_code == 200

    state = client.get("/api/session").json()
    assert len(state["conversation"]) == 12
    assert state["conversation"][0]["content"] == "turn-1"
    assert [turn["role"] for turn in state["conversation"]] == [
        "user",
        "assistant",
    ] * 6
    assert len(str(service.turns[-1]["session_summary"])) == 1200

    before_reset = client.post("/api/session/reset")
    assert before_reset.status_code == 200
    assert before_reset.json()["conversation"] == []
    assert before_reset.json()["plan"] is None
    assert before_reset.json()["thread_id"] == "thread-2"


def test_visuals_require_current_revision_and_expose_attribution() -> None:
    service = FakeTravelPlannerService()
    visuals = FakeVisualService()
    client = TestClient(
        create_app(service, visuals, require_auth=False), base_url="https://localhost"
    )
    _start(client)
    state = _create(client, "Hue")
    revision = state["plan"]["revision"]

    response = client.get(f"/api/visuals?revision={revision}")
    assert response.status_code == 200
    payload = response.json()
    assert payload["revision"] == revision
    assert payload["visuals_by_entry"]["fixture-entry"] == {
        "image_url": "https://images.example.test/fixture.jpg",
        "image_page_url": "https://commons.example.test/File:fixture.jpg",
        "image_alt": "Fixture landmark image",
        "image_credit": "Fixture photographer",
        "image_license": "CC BY-SA 4.0",
    }
    assert visuals.plans[0].revision == revision

    stale = client.get(f"/api/visuals?revision={revision + 1}")
    assert stale.status_code == 409
    assert stale.json()["detail"] == "Lịch trình đã thay đổi."

    visuals.fail = True
    unavailable = client.get(f"/api/visuals?revision={revision}")
    assert unavailable.status_code == 200
    assert unavailable.json()["visuals_by_entry"] == {}


def test_graph_endpoint_is_read_only(monkeypatch) -> None:
    service = FakeTravelPlannerService()
    monkeypatch.setattr(
        "grounded_travel_planner.web.api.compiled_graph_svg",
        lambda graph: "<svg aria-label='offline graph'/>",
    )
    client = TestClient(
        create_app(service, FakeVisualService()), base_url="https://localhost"
    )

    response = client.get("/api/graph")
    assert response.status_code == 200
    assert response.json() == {"svg": "<svg aria-label='offline graph'/>"}
    assert service.turns == []


def test_graph_image_endpoint_returns_local_svg_without_a_turn(monkeypatch) -> None:
    service = FakeTravelPlannerService()
    monkeypatch.setattr(
        "grounded_travel_planner.web.api.compiled_graph_svg",
        lambda graph: "<svg aria-label='local graph'/>",
    )
    client = TestClient(
        create_app(service, FakeVisualService()), base_url="https://localhost"
    )

    response = client.get("/api/graph/image")

    assert response.status_code == 200
    assert response.headers["content-type"] == "image/svg+xml"
    assert response.text == "<svg aria-label='local graph'/>"
    assert service.graph_image_calls == 0
    assert service.turns == []
