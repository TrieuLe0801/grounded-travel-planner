from datetime import date, time

from pydantic import BaseModel

from grounded_travel_planner.agents import ChatAgent, CoordinatorAgent, PlannerAgent
from grounded_travel_planner.config import RuntimeConfig
from grounded_travel_planner.contracts import (
    ChatResponse,
    ChatSearchDecision,
    CoordinatorDecision,
    IntentAction,
    PlaceRecommendation,
    PlanChangeIntent,
    ScheduleEntry,
    SightseeingPlan,
    SourceReference,
)
from grounded_travel_planner.service import TravelPlannerService


class ScriptedModel:
    model_name = "offline-test-model"

    def __init__(self, handler) -> None:
        self.handler = handler
        self.calls: list[str] = []
        self.prompts: list[str] = []

    def generate_structured(self, prompt, schema, *, metadata=None):
        self.calls.append(schema.__name__)
        self.prompts.append(prompt)
        result = self.handler(prompt, schema)
        return schema.model_validate(result)


class NoSearch:
    def search_places(self, query, *, max_results: int, thread_id: str):
        raise AssertionError("shortening an existing itinerary does not search")


def three_day_plan() -> SightseeingPlan:
    entries = []
    for day in range(1, 4):
        source = SourceReference(
            source_id=f"source-{day}",
            title=f"Official guide {day}",
            url=f"https://travel.example/place-{day}",
            snippet=f"Trusted source snippet {day}",
            provider=f"provider-{day}",
            retrieval_query=f"original query {day}",
        )
        place = PlaceRecommendation(
            place_id=f"place-{day}",
            name=f"Museum {day}",
            description=f"Grounded description {day}.",
            source_references=[source],
        )
        entries.append(
            ScheduleEntry(
                id=f"entry-{day}",
                day_index=day,
                start_time=time(9),
                end_time=time(10),
                place=place,
            )
        )
    return SightseeingPlan(
        plan_id="plan-current",
        destination="Hue",
        start_date=date(2026, 11, 1),
        day_count=3,
        entries=entries,
        summary="Three days in Hue.",
        revision=4,
    )


def test_shortening_commits_retained_entries_with_original_source_data() -> None:
    current = three_day_plan()
    coordinator = ScriptedModel(
        lambda prompt, schema: CoordinatorDecision(
            intent=PlanChangeIntent(
                action=IntentAction.SHORTEN_TRIP,
                day_count_delta=1,
            ),
            requires_planner=True,
        )
    )

    def propose(prompt: str, schema: type[BaseModel]):
        raise AssertionError("shortening is a deterministic Planner operation")

    planner = ScriptedModel(propose)
    chat = ScriptedModel(
        lambda prompt, schema: (
            ChatSearchDecision(
                should_search=False,
                message="Lịch trình đã được rút còn hai ngày.",
            )
            if schema is ChatSearchDecision
            else ChatResponse(message="Lịch trình đã được cập nhật.")
        )
    )
    service = TravelPlannerService(
        CoordinatorAgent(coordinator),
        PlannerAgent(planner),
        ChatAgent(chat),
        search=NoSearch(),
        config=RuntimeConfig(),
    )

    response = service.handle_turn(
        thread_id="thread-shorten-trip-regression",
        message="Bớt một ngày",
        current_plan=current,
    )

    assert response.committed is True, response.validation_issues
    assert response.current_plan is not None
    assert response.current_plan.day_count == 2
    assert [entry.id for entry in response.current_plan.entries] == [
        "entry-1",
        "entry-2",
    ]
    assert response.current_plan.entries == current.entries[:2]
    assert response.current_plan.revision == 5
    assert response.search_calls == 0
    assert response.repair_attempts == 0
    assert coordinator.calls == ["CoordinatorDecision"]
    assert planner.calls == []
