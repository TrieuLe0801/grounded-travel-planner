"""Offline regression coverage for Streamlit background planning turns."""

from __future__ import annotations

from dataclasses import fields
from datetime import date, time
from threading import Event

from grounded_travel_planner.contracts import (
    AgentResponse,
    ConversationTurn,
    PlaceRecommendation,
    ResponseStatus,
    ScheduleEntry,
    SightseeingPlan,
    SourceReference,
    TripRequest,
)
from grounded_travel_planner.ui.turn_runner import TurnRunner


def _plan() -> SightseeingPlan:
    source = SourceReference(
        source_id="turn-runner-source",
        title="Imperial City information",
        url="https://travel.example/imperial-city",
        retrieval_query="Imperial City Hue",
    )
    place = PlaceRecommendation(
        place_id="turn-runner-place",
        name="Imperial City",
        description="Nguồn tham khảo ngoại tuyến.",
        source_references=[source],
    )
    return SightseeingPlan(
        plan_id="turn-runner-plan",
        destination="Hue",
        start_date=date(2026, 11, 1),
        day_count=1,
        entries=[
            ScheduleEntry(
                id="turn-runner-entry",
                day_index=1,
                start_time=time(9),
                end_time=time(10, 30),
                place=place,
            )
        ],
    )


class _GatedService:
    def __init__(self) -> None:
        self.entered = Event()
        self.release = Event()
        self.calls: list[dict[str, object]] = []

    def handle_turn(self, **kwargs: object) -> AgentResponse:
        self.calls.append(kwargs)
        self.entered.set()
        assert self.release.wait(timeout=2)
        return AgentResponse(
            status=ResponseStatus.COMMITTED,
            message="Đã hoàn tất yêu cầu nền.",
            current_plan=kwargs["current_plan"],  # type: ignore[arg-type]
            committed=True,
        )


class _FailingService:
    def handle_turn(self, **kwargs: object) -> AgentResponse:
        raise RuntimeError("offline failure")


def test_turn_runner_captures_copies_and_completes_after_foreground_rerun() -> None:
    service = _GatedService()
    runner = TurnRunner(max_workers=1)
    plan = _plan()
    request = TripRequest(destination="Hue", start_date=date(2026, 11, 1), day_count=1)
    history = [
        ConversationTurn(role="user", content=f"turn-{index}-" + ("x" * 2500))
        for index in range(13)
    ]

    pending = runner.submit(
        service,  # type: ignore[arg-type]
        thread_id="thread-original",
        message="Tạo lịch trình",
        current_plan=plan,
        request=request,
        session_summary="summary-" + ("s" * 1300),
        conversation_history=history,
    )

    assert service.entered.wait(timeout=1)
    # A Streamlit rerun/page change only reads session state while the worker runs.
    foreground_snapshot = {"thread": pending.thread_id, "message": pending.message}
    assert foreground_snapshot == {
        "thread": "thread-original",
        "message": "Tạo lịch trình",
    }
    assert TurnRunner.collect(pending) is None

    plan.destination = "Đà Nẵng"
    plan.entries[0].place.name = "Địa điểm đã bị sửa ngoài luồng"
    request.destination = "Đà Nẵng"
    history[-1].content = "mutated after submission"
    service.release.set()

    response = pending.future.result(timeout=2)
    captured = service.calls[0]
    captured_plan = captured["current_plan"]
    captured_request = captured["request"]
    captured_history = captured["conversation_history"]
    assert pending.thread_id == "thread-original"
    assert pending.message == "Tạo lịch trình"
    assert pending.current_plan is not plan
    assert pending.request is not request
    assert isinstance(captured_plan, SightseeingPlan)
    assert isinstance(captured_request, TripRequest)
    assert captured_plan.destination == "Hue"
    assert captured_plan.entries[0].place.name == "Imperial City"
    assert captured_request.destination == "Hue"
    assert captured["session_summary"] == "summary-" + ("s" * 1192)
    assert isinstance(captured_history, list)
    assert len(captured_history) == 12
    assert captured_history[-1].content == "turn-12-" + ("x" * 1992)
    assert {field.name for field in fields(pending)}.isdisjoint(
        {"session_summary", "conversation_history"}
    )
    assert response.status is ResponseStatus.COMMITTED
    assert TurnRunner.collect(pending) == response


def test_turn_runner_exception_returns_vietnamese_provider_error_and_prior_plan() -> (
    None
):
    runner = TurnRunner(max_workers=1)
    prior_plan = _plan()
    pending = runner.submit(
        _FailingService(),  # type: ignore[arg-type]
        thread_id="thread-failure",
        message="Hãy thay đổi lịch",
        current_plan=prior_plan,
    )

    response = pending.future.result(timeout=2)

    assert response.status is ResponseStatus.PROVIDER_ERROR
    assert response.message == (
        "Chưa thể hoàn tất yêu cầu; lịch trình trước đó vẫn được giữ nguyên."
    )
    assert response.current_plan == prior_plan
    assert response.current_plan is not prior_plan
    assert response.validation_issues[0].code == "background_turn_failure"
