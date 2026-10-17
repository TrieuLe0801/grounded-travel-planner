"""Offline contract tests for the JavaScript web adapter."""

from __future__ import annotations

from datetime import date, time
from threading import Event

from fastapi.testclient import TestClient

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
from grounded_travel_planner.visuals import PlaceVisual
from grounded_travel_planner.web.api import create_app


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

    def create_session(self) -> str:
        self.created_sessions += 1
        return f"thread-{self.created_sessions}"

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


def _start(client: TestClient) -> None:
    response = client.post("/api/session")
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
    app = create_app(service, FakeVisualService())
    first = TestClient(app)
    second = TestClient(app)
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
    client = TestClient(create_app(service, FakeVisualService()))
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


def test_visuals_require_current_revision_and_expose_attribution() -> None:
    service = FakeTravelPlannerService()
    visuals = FakeVisualService()
    client = TestClient(create_app(service, visuals))
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
    client = TestClient(create_app(service, FakeVisualService()))

    response = client.get("/api/graph")
    assert response.status_code == 200
    assert response.json() == {"svg": "<svg aria-label='offline graph'/>"}
    assert service.turns == []
