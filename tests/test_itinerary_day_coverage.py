"""Regression coverage for complete multi-day itinerary creation."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from datetime import date, time
from typing import TypeVar

from pydantic import BaseModel

from grounded_travel_planner.agents import ChatAgent, CoordinatorAgent, PlannerAgent
from grounded_travel_planner.contracts import (
    ChatResponse,
    ChatSearchDecision,
    CoordinatorDecision,
    IntentAction,
    PlaceRecommendation,
    PlanChangeIntent,
    PlannerProposal,
    ResponseStatus,
    ScheduleEntry,
    SearchResult,
    SightseeingPlan,
    SourceReference,
    TripRequest,
)
from grounded_travel_planner.service import TravelPlannerService

T = TypeVar("T", bound=BaseModel)


class ScriptedModel:
    def __init__(self, handler: Callable[[str, type[BaseModel]], BaseModel]) -> None:
        self.handler = handler
        self.model_name = "test-model"
        self.prompts: list[str] = []

    def generate_structured(
        self,
        prompt: str,
        schema: type[T],
        *,
        metadata: Mapping[str, str] | None = None,
    ) -> T:
        del metadata
        self.prompts.append(prompt)
        return schema.model_validate(self.handler(prompt, schema))


class FakeSearch:
    def __init__(self, result: SearchResult) -> None:
        self.result = result

    def search_places(
        self, query: str, *, max_results: int, thread_id: str
    ) -> list[SearchResult]:
        del query, max_results, thread_id
        return [self.result]


def _source() -> SourceReference:
    return SourceReference(
        source_id="source_1",
        title="Hue visitor guide",
        url="https://travel.example/hue/guide",
        snippet="Visitor information for Hue sightseeing.",
        retrieval_query="Hue sightseeing",
    )


def _search_result() -> SearchResult:
    source = _source()
    return SearchResult(
        source_id=source.source_id,
        title=source.title,
        url=source.url,
        snippet=source.snippet,
    )


def _plan(days: list[int], *, plan_id: str = "candidate") -> SightseeingPlan:
    source = _source()
    entries = [
        ScheduleEntry(
            id=f"entry_{day_index}",
            day_index=day_index,
            start_time=time(9, 0),
            end_time=time(10, 0),
            place=PlaceRecommendation(
                place_id=f"place_{day_index}",
                name=f"Hue stop {day_index}",
                description="Grounded sightseeing stop.",
                source_references=[source],
            ),
        )
        for day_index in days
    ]
    return SightseeingPlan(
        plan_id=plan_id,
        destination="Hue",
        start_date=date(2026, 11, 1),
        day_count=7,
        entries=entries,
        summary="Seven-day Hue itinerary.",
    )


def _service(candidate: SightseeingPlan) -> tuple[TravelPlannerService, ScriptedModel]:
    def coordinate(_prompt: str, schema: type[BaseModel]) -> BaseModel:
        assert schema is CoordinatorDecision
        return CoordinatorDecision(
            intent=PlanChangeIntent(action=IntentAction.CREATE_TRIP),
            requires_planner=True,
        )

    def propose(_prompt: str, schema: type[BaseModel]) -> BaseModel:
        assert schema is PlannerProposal
        return PlannerProposal(plan=candidate, summary=candidate.summary)

    def answer(_prompt: str, schema: type[BaseModel]) -> BaseModel:
        if schema is ChatSearchDecision:
            return ChatSearchDecision(
                should_search=False,
                message="Đã xử lý yêu cầu.",
            )
        assert schema is ChatResponse
        return ChatResponse(message="Đã xử lý yêu cầu.")

    planner = ScriptedModel(propose)
    return (
        TravelPlannerService(
            CoordinatorAgent(ScriptedModel(coordinate)),
            PlannerAgent(planner),
            ChatAgent(ScriptedModel(answer)),
            search=FakeSearch(_search_result()),
        ),
        planner,
    )


def _request() -> TripRequest:
    return TripRequest(destination="Hue", start_date=date(2026, 11, 1), day_count=7)


def test_create_trip_rejects_missing_middle_days_and_keeps_previous_plan() -> None:
    service, planner = _service(_plan([1, 4, 5, 6, 7]))
    previous = _plan([1, 2, 3, 4, 5, 6, 7], plan_id="previous")

    response = service.handle_turn(
        thread_id="day-coverage-reject",
        message="Tạo lịch Huế 7 ngày",
        current_plan=previous,
        request=_request(),
    )

    assert response.status is ResponseStatus.REJECTED
    assert response.current_plan == previous
    assert response.repair_attempts == 1
    assert {issue.code for issue in response.validation_issues} == {
        "itinerary_day_missing"
    }
    assert [issue.message for issue in response.validation_issues] == [
        "Day 2 has no grounded itinerary stop.",
        "Day 3 has no grounded itinerary stop.",
    ]
    assert "include at least one grounded stop on every trip day" in planner.prompts[0]
    assert "itinerary_day_missing" in planner.prompts[1]


def test_create_trip_commits_when_every_day_has_a_grounded_stop() -> None:
    candidate = _plan([1, 2, 3, 4, 5, 6, 7])
    service, _planner = _service(candidate)

    response = service.handle_turn(
        thread_id="day-coverage-commit",
        message="Tạo lịch Huế 7 ngày",
        request=_request(),
    )

    assert response.status is ResponseStatus.COMMITTED
    assert response.current_plan is not None
    assert {entry.day_index for entry in response.current_plan.entries} == set(
        range(1, 8)
    )
