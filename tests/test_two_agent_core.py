from __future__ import annotations

from collections.abc import Callable, Mapping
from datetime import date, time
from typing import Any, TypeVar

import pytest
from pydantic import BaseModel

from grounded_travel_planner.adapters.model import ChatOpenAIStructuredModel
from grounded_travel_planner.adapters.search import TavilyPlaceSearchProvider
from grounded_travel_planner.agents import CoordinatorAgent, PlannerAgent
from grounded_travel_planner.config import DEFAULT_MODEL_NAME, RuntimeConfig
from grounded_travel_planner.contracts import (
    CoordinatorDecision,
    CoordinatorExplanation,
    IntentAction,
    PlaceRecommendation,
    PlanCandidate,
    PlanChangeIntent,
    ResponseStatus,
    ScheduleEntry,
    SearchResult,
    SightseeingPlan,
    SourceReference,
    TripRequest,
    ValidationIssue,
)
from grounded_travel_planner.policies.change_validation import (
    validate_requested_change,
)
from grounded_travel_planner.policies.plan_commit import validate_candidate
from grounded_travel_planner.providers import ProviderError
from grounded_travel_planner.service import TravelPlannerService

T = TypeVar("T", bound=BaseModel)


class ScriptedModel:
    def __init__(
        self,
        handler: Callable[[str, type[BaseModel]], BaseModel],
        model_name: str = DEFAULT_MODEL_NAME,
    ) -> None:
        self.handler = handler
        self.model_name = model_name
        self.calls: list[str] = []

    def generate_structured(
        self,
        prompt: str,
        schema: type[T],
        *,
        metadata: Mapping[str, str] | None = None,
    ) -> T:
        self.calls.append(schema.__name__)
        return schema.model_validate(self.handler(prompt, schema))


class FakeSearch:
    def __init__(self, results: list[SearchResult]) -> None:
        self.results = results
        self.calls: list[tuple[str, int, str]] = []

    def search_places(
        self,
        query: str,
        *,
        max_results: int,
        thread_id: str,
    ) -> list[SearchResult]:
        self.calls.append((query, max_results, thread_id))
        return self.results


class RecordingTrace:
    def __init__(self) -> None:
        self.events: list[tuple[str, dict[str, Any], str]] = []

    def record_event(
        self,
        name: str,
        payload: Mapping[str, Any],
        *,
        thread_id: str,
    ) -> None:
        self.events.append((name, dict(payload), thread_id))


def source(
    *,
    title: str = "Imperial City Hue visitor guide",
    url: str = "https://travel.example/hue/imperial-city",
    supports_hours: bool = False,
    snippet: str = "Imperial City Hue sightseeing information and visitor details",
) -> SourceReference:
    return SourceReference(
        source_id="source_1",
        title=title,
        url=url,
        snippet=snippet,
        retrieval_query="Imperial City Hue sightseeing",
        supports_opening_hours=supports_hours,
    )


def search_result() -> SearchResult:
    item = source()
    return SearchResult(
        source_id=item.source_id,
        title=item.title,
        url=item.url,
        snippet=item.snippet,
        score=0.95,
    )


def plan(
    *,
    source_reference: SourceReference | None = None,
    overlapping: bool = False,
    opening_hours: str | None = "unverified",
    opening_hours_verified: bool = False,
) -> SightseeingPlan:
    evidence = source_reference or source()
    place = PlaceRecommendation(
        place_id="place_1",
        name="Imperial City",
        description="Historic Hue citadel; description grounded by the source.",
        source_references=[evidence],
        visit_minutes_estimate=90,
        travel_minutes_estimate=20,
        opening_hours=opening_hours,
        opening_hours_verified=opening_hours_verified,
    )
    entries = [
        ScheduleEntry(
            id="entry_1",
            day_index=1,
            start_time=time(9, 0),
            end_time=time(10, 30),
            place=place,
        )
    ]
    if overlapping:
        entries.append(
            ScheduleEntry(
                id="entry_2",
                day_index=1,
                start_time=time(10, 0),
                end_time=time(11, 0),
                place=place.model_copy(update={"place_id": "place_2"}),
            )
        )
    return SightseeingPlan(
        plan_id="plan_existing",
        destination="Hue",
        start_date=date(2026, 11, 1),
        day_count=2,
        entries=entries,
        summary="Estimated city sightseeing plan.",
        revision=1,
    )


def two_place_plan() -> SightseeingPlan:
    first = plan()
    museum_source = source(
        title="Hue Museum visitor information",
        url="https://travel.example/hue/museum",
        snippet="Hue Museum visitor information and exhibits.",
    )
    museum = PlaceRecommendation(
        place_id="place_museum",
        name="Hue Museum",
        description="A sourced museum recommendation.",
        source_references=[museum_source],
        visit_minutes_estimate=60,
        travel_minutes_estimate=15,
        opening_hours="unverified",
    )
    second = ScheduleEntry(
        id="entry_museum",
        day_index=1,
        start_time=time(11, 0),
        end_time=time(12, 0),
        place=museum,
    )
    return first.model_copy(update={"entries": [first.entries[0], second]})


def coordinator_model(action: IntentAction) -> ScriptedModel:
    def handler(prompt: str, schema: type[BaseModel]) -> BaseModel:
        if schema is CoordinatorDecision:
            return CoordinatorDecision(
                intent=PlanChangeIntent(action=action, user_message="test"),
                requires_planner=action is not IntentAction.ORDINARY_CHAT,
                response_hint="Ready to help.",
            )
        if schema is CoordinatorExplanation:
            return CoordinatorExplanation(message="Coordinator explanation.")
        raise AssertionError(schema)

    return ScriptedModel(handler)


def planner_model(candidate_plan: SightseeingPlan) -> ScriptedModel:
    def handler(prompt: str, schema: type[BaseModel]) -> BaseModel:
        assert schema is PlanCandidate
        return PlanCandidate(plan=candidate_plan, summary="candidate")

    return ScriptedModel(handler)


def service_for(
    action: IntentAction,
    candidate_plan: SightseeingPlan,
    *,
    search: FakeSearch | None = None,
    trace: RecordingTrace | None = None,
) -> tuple[TravelPlannerService, ScriptedModel, ScriptedModel, FakeSearch]:
    coordinator_llm = coordinator_model(action)
    planner_llm = planner_model(candidate_plan)
    fake_search = search or FakeSearch([search_result()])
    config = RuntimeConfig()
    service = TravelPlannerService(
        CoordinatorAgent(coordinator_llm),
        PlannerAgent(planner_llm, fake_search, config),
        trace_sink=trace,
        config=config,
    )
    return service, coordinator_llm, planner_llm, fake_search


def test_two_runtime_roles_use_exact_requested_model() -> None:
    service, _, _, _ = service_for(IntentAction.CREATE_TRIP, plan())

    assert service.coordinator.role == "coordinator"
    assert service.planner.role == "planner"
    assert service.coordinator.model_name == "gpt-5.5"
    assert service.planner.model_name == "gpt-5.5"
    assert not hasattr(service.coordinator, "propose")
    assert not hasattr(service.planner, "commit")
    assert ChatOpenAIStructuredModel().model_name == "gpt-5.5"


def test_openai_adapter_uses_function_calling_for_pydantic_schema(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    observed: dict[str, object] = {}

    class FakeChatOpenAI:
        def __init__(self, *, model: str) -> None:
            observed["model"] = model

        def with_structured_output(self, schema, *, method: str):
            observed["schema"] = schema
            observed["method"] = method
            return self

        def invoke(self, messages, config):
            observed["metadata"] = config["metadata"]
            return CoordinatorExplanation(message="ok")

    monkeypatch.setattr("langchain_openai.ChatOpenAI", FakeChatOpenAI)
    adapter = ChatOpenAIStructuredModel()

    result = adapter.generate_structured(
        "explain",
        CoordinatorExplanation,
        metadata={"thread_id": "thread-adapter"},
    )

    assert result.message == "ok"
    assert observed == {
        "model": "gpt-5.5",
        "schema": CoordinatorExplanation,
        "method": "function_calling",
        "metadata": {"thread_id": "thread-adapter"},
    }


def test_ordinary_chat_does_not_search_or_mutate_plan() -> None:
    existing = plan()
    original = existing.model_copy(deep=True)
    service, _, planner_llm, search = service_for(
        IntentAction.ORDINARY_CHAT,
        plan(),
    )

    response = service.handle_turn(
        thread_id="thread-a",
        message="Thanks, that looks good.",
        current_plan=existing,
    )

    assert response.status is ResponseStatus.UNCHANGED
    assert response.committed is False
    assert response.current_plan == original
    assert existing == original
    assert search.calls == []
    assert planner_llm.calls == []
    assert response.graph_steps == 2


def test_vietnamese_chat_uses_localized_fallback_when_explanation_fails() -> None:
    prompts: list[str] = []

    def coordinator_handler(prompt: str, schema: type[BaseModel]) -> BaseModel:
        prompts.append(prompt)
        if schema is CoordinatorDecision:
            return CoordinatorDecision(
                intent=PlanChangeIntent(action=IntentAction.ORDINARY_CHAT),
                response_hint="English hint must not reach the user",
            )
        raise RuntimeError("simulated explanation failure")

    search = FakeSearch([])
    config = RuntimeConfig()
    service = TravelPlannerService(
        CoordinatorAgent(ScriptedModel(coordinator_handler)),
        PlannerAgent(
            ScriptedModel(lambda prompt, schema: PlanCandidate()), search, config
        ),
        config=config,
    )
    current = plan()

    response = service.handle_turn(
        thread_id="thread-vietnamese-chat",
        message="Cảm ơn, lịch trình này ổn rồi.",
        current_plan=current,
    )

    assert response.status is ResponseStatus.UNCHANGED
    assert response.current_plan == current
    assert response.message == "Bạn muốn thay đổi điều gì trong lịch trình?"
    assert search.calls == []
    assert "Understand Vietnamese requests" in prompts[0]
    assert "Respond entirely in natural Vietnamese" in prompts[1]


def test_valid_create_searches_once_and_commits_grounded_plan() -> None:
    trace = RecordingTrace()
    service, _, _, search = service_for(
        IntentAction.CREATE_TRIP,
        plan(),
        trace=trace,
    )
    request = TripRequest(
        destination="Hue",
        start_date=date(2026, 11, 1),
        day_count=2,
    )

    response = service.handle_turn(
        thread_id="thread-live",
        message="Create a two-day Hue plan.",
        request=request,
    )

    assert response.status is ResponseStatus.COMMITTED
    assert response.committed is True
    assert response.current_plan is not None
    assert str(response.current_plan.entries[0].place.source_references[0].url) == (
        "https://travel.example/hue/imperial-city"
    )
    assert len(search.calls) == 1
    assert response.search_calls == 1
    assert response.graph_steps <= 8
    assert response.repair_attempts <= 1
    assert trace.events
    assert {event[2] for event in trace.events} == {"thread-live"}
    assert {event[0] for event in trace.events} >= {
        "turn.start",
        "coordinator.classify",
        "planner.propose",
        "validation.input",
        "validation.candidate",
        "turn.finalize",
    }


def test_invalid_input_stops_before_planner_and_search() -> None:
    invalid = TripRequest.model_construct(
        destination="",
        start_date=date(2026, 11, 1),
        day_count=8,
    )
    service, _, planner_llm, search = service_for(
        IntentAction.CREATE_TRIP,
        plan(),
    )

    response = service.handle_turn(
        thread_id="thread-invalid",
        message="Create a plan.",
        request=invalid,
    )

    assert response.committed is False
    assert response.current_plan is None
    assert {issue.code for issue in response.validation_issues} == {
        "destination_required",
        "day_count_out_of_range",
    }
    assert planner_llm.calls == []
    assert search.calls == []


def test_invalid_candidate_repairs_once_and_preserves_previous_plan() -> None:
    existing = plan()
    service, _, planner_llm, search = service_for(
        IntentAction.CHANGE_TIME,
        plan(overlapping=True),
    )

    response = service.handle_turn(
        thread_id="thread-edit",
        message="Move the second place earlier.",
        current_plan=existing,
    )

    assert response.status is ResponseStatus.REJECTED
    assert response.committed is False
    assert response.current_plan == existing
    assert "schedule_overlap" in {issue.code for issue in response.validation_issues}
    assert response.repair_attempts == 1
    assert response.graph_steps == 8
    assert planner_llm.calls.count("PlanCandidate") == 2
    assert search.calls == []


def test_source_and_opening_hours_claims_are_rejected() -> None:
    returned = source()
    fabricated = source(
        title="Unrelated restaurant page",
        url="https://unrelated.example/page",
        snippet="A restaurant in another country with no matching attraction.",
    )
    candidate = PlanCandidate(
        plan=plan(
            source_reference=fabricated,
            opening_hours="09:00-17:00",
            opening_hours_verified=True,
        ),
        returned_source_urls={str(returned.url)},
    )
    request = TripRequest(
        destination="Hue",
        start_date=date(2026, 11, 1),
        day_count=2,
    )

    codes = {issue.code for issue in validate_candidate(candidate, request)}

    assert "source_not_returned" in codes
    assert "source_place_mismatch" in codes
    assert "opening_hours_unsubstantiated" in codes


def test_repair_does_not_treat_fabricated_candidate_sources_as_returned() -> None:
    fabricated = source(
        title="Fabricated source",
        url="https://fabricated.example/hue/imperial-city",
        snippet="Fabricated Imperial City information.",
    )
    candidate_plan = plan(source_reference=fabricated)
    planner_prompts: list[str] = []

    def planner_handler(prompt: str, schema: type[BaseModel]) -> BaseModel:
        assert schema is PlanCandidate
        planner_prompts.append(prompt)
        return PlanCandidate(plan=candidate_plan, summary="candidate")

    config = RuntimeConfig()
    service = TravelPlannerService(
        CoordinatorAgent(coordinator_model(IntentAction.CREATE_TRIP)),
        PlannerAgent(
            ScriptedModel(planner_handler),
            FakeSearch([search_result()]),
            config,
        ),
        config=config,
    )

    response = service.handle_turn(
        thread_id="thread-source-repair",
        message="Create a Hue plan.",
        request=TripRequest(
            destination="Hue",
            start_date=date(2026, 11, 1),
            day_count=2,
        ),
    )

    assert response.status is ResponseStatus.REJECTED
    assert response.committed is False
    assert response.repair_attempts == 1
    assert "source_not_returned" in {issue.code for issue in response.validation_issues}
    assert len(planner_prompts) == 2
    assert str(fabricated.url) not in planner_prompts[1]


def test_known_opening_hours_conflict_is_rejected() -> None:
    hours_source = source(supports_hours=True)
    conflict_plan = plan(
        source_reference=hours_source,
        opening_hours="10:00-17:00",
        opening_hours_verified=True,
    )
    candidate = PlanCandidate(
        plan=conflict_plan,
        returned_source_urls={str(hours_source.url)},
    )
    request = TripRequest(
        destination="Hue",
        start_date=date(2026, 11, 1),
        day_count=2,
    )

    codes = {issue.code for issue in validate_candidate(candidate, request)}

    assert "opening_hours_conflict" in codes


def test_unverified_opening_hours_are_normalized_and_do_not_block_commit() -> None:
    candidate_plan = plan(
        opening_hours="08:00-17:00",
        opening_hours_verified=False,
    )

    def planner_handler(prompt: str, schema: type[BaseModel]) -> BaseModel:
        assert schema is PlanCandidate
        return PlanCandidate(
            plan=candidate_plan,
            issues=[
                ValidationIssue(
                    code="opening_hours_unverified",
                    message="Returned sources do not substantiate opening hours.",
                )
            ],
        )

    config = RuntimeConfig()
    service = TravelPlannerService(
        CoordinatorAgent(coordinator_model(IntentAction.CREATE_TRIP)),
        PlannerAgent(
            ScriptedModel(planner_handler),
            FakeSearch([search_result()]),
            config,
        ),
        config=config,
    )

    response = service.handle_turn(
        thread_id="thread-unverified-hours",
        message="Create a sourced Hue plan.",
        request=TripRequest(
            destination="Hue",
            start_date=date(2026, 11, 1),
            day_count=2,
        ),
    )

    assert response.status is ResponseStatus.COMMITTED
    assert response.validation_issues == []
    assert response.current_plan is not None
    place_result = response.current_plan.entries[0].place
    assert place_result.opening_hours == "unverified"
    assert place_result.opening_hours_verified is False


def test_sessions_do_not_share_plan_state() -> None:
    plan_a = plan()
    plan_b = plan().model_copy(update={"plan_id": "plan_b", "destination": "Hoi An"})
    service, _, _, _ = service_for(IntentAction.ORDINARY_CHAT, plan())

    response_a = service.handle_turn(
        thread_id="thread-a",
        message="hello",
        current_plan=plan_a,
    )
    response_b = service.handle_turn(
        thread_id="thread-b",
        message="hello",
        current_plan=plan_b,
    )

    assert response_a.current_plan == plan_a
    assert response_b.current_plan == plan_b
    assert response_a.current_plan != response_b.current_plan


def test_model_failure_is_sanitized_and_preserves_plan() -> None:
    secret = "sk-supersecret123456789"

    def broken(prompt: str, schema: type[BaseModel]) -> BaseModel:
        if schema is CoordinatorDecision:
            raise RuntimeError(f"provider rejected {secret}")
        raise AssertionError(schema)

    existing = plan()
    config = RuntimeConfig()
    coordinator = CoordinatorAgent(ScriptedModel(broken))
    planner_llm = planner_model(plan())
    service = TravelPlannerService(
        coordinator,
        PlannerAgent(planner_llm, FakeSearch([search_result()]), config),
        config=config,
    )

    response = service.handle_turn(
        thread_id="thread-secret",
        message="change the plan",
        current_plan=existing,
    )

    assert response.current_plan == existing
    assert response.committed is False
    assert secret not in response.model_dump_json()
    assert "[REDACTED]" in response.model_dump_json()
    assert planner_llm.calls == []


def test_tavily_missing_key_fails_before_network(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("TAVILY_API_KEY", raising=False)
    provider = TavilyPlaceSearchProvider()

    with pytest.raises(ProviderError, match="not configured"):
        provider.search_places("Hue sightseeing", max_results=3, thread_id="t")


def test_tavily_normalizes_bounds_and_skips_malformed_results(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    long_content = "Opening hours 09:00-17:00. " + ("Hue visitor details " * 100)

    class FakeTavilyClient:
        def __init__(self, *, api_key: str) -> None:
            assert api_key == "fake-tavily-key"

        def search(self, **kwargs):
            assert kwargs["max_results"] == 3
            return {
                "results": [
                    {
                        "title": "Imperial City Hue" * 30,
                        "url": "https://travel.example/hue/imperial-city/",
                        "content": long_content,
                        "score": 0.9,
                    },
                    {"title": "bad", "url": "javascript:alert(1)"},
                ]
            }

    monkeypatch.setenv("TAVILY_API_KEY", "fake-tavily-key")
    monkeypatch.setattr("tavily.TavilyClient", FakeTavilyClient)
    provider = TavilyPlaceSearchProvider()

    results = provider.search_places(
        "Hue sightseeing",
        max_results=3,
        thread_id="thread-provider",
    )

    assert len(results) == 1
    assert len(results[0].title) == 240
    assert results[0].snippet is not None
    assert len(results[0].snippet) == 1000
    assert results[0].supports_opening_hours is True
    assert str(results[0].url) == "https://travel.example/hue/imperial-city"


def test_all_supported_edit_intents_are_verified_deterministically() -> None:
    current = two_place_plan()
    first, second = current.entries
    pagoda_source = source(
        title="Thien Mu Pagoda Hue visitor guide",
        url="https://travel.example/hue/thien-mu-pagoda",
        snippet="Thien Mu Pagoda Hue visitor information.",
    )
    pagoda = PlaceRecommendation(
        place_id="place_pagoda",
        name="Thien Mu Pagoda",
        description="A sourced pagoda recommendation.",
        source_references=[pagoda_source],
        opening_hours="unverified",
    )
    added_entry = ScheduleEntry(
        id="entry_pagoda",
        day_index=2,
        start_time=time(9),
        end_time=time(10, 30),
        place=pagoda,
    )
    replacement = first.model_copy(
        update={"place": pagoda.model_copy(update={"place_id": first.place.place_id})}
    )
    moved_day = first.model_copy(update={"day_index": 2})
    moved_time = first.model_copy(
        update={"start_time": time(13), "end_time": time(14, 30)}
    )
    moved_after_second = first.model_copy(
        update={"start_time": time(13), "end_time": time(14, 30)}
    )
    cases = [
        (
            PlanChangeIntent(
                action=IntentAction.ADD_PLACE,
                place_name="Thien Mu Pagoda",
            ),
            current.model_copy(update={"entries": [first, second, added_entry]}),
        ),
        (
            PlanChangeIntent(
                action=IntentAction.REMOVE_PLACE,
                entry_id=first.id,
            ),
            current.model_copy(update={"entries": [second]}),
        ),
        (
            PlanChangeIntent(
                action=IntentAction.REPLACE_PLACE,
                place_name=first.place.name,
                replacement_place_name=pagoda.name,
            ),
            current.model_copy(update={"entries": [replacement, second]}),
        ),
        (
            PlanChangeIntent(
                action=IntentAction.REORDER_PLACES,
                from_index=0,
                to_index=1,
            ),
            current.model_copy(update={"entries": [moved_after_second, second]}),
        ),
        (
            PlanChangeIntent(
                action=IntentAction.CHANGE_DAY,
                entry_id=first.id,
                day_index=2,
            ),
            current.model_copy(update={"entries": [moved_day, second]}),
        ),
        (
            PlanChangeIntent(
                action=IntentAction.CHANGE_TIME,
                entry_id=first.id,
                start_time=time(13),
                end_time=time(14, 30),
            ),
            current.model_copy(update={"entries": [moved_time, second]}),
        ),
    ]

    for intent, candidate in cases:
        assert (
            validate_requested_change(intent, current, candidate) == []
        ), intent.action

    ignored = PlanChangeIntent(
        action=IntentAction.CHANGE_TIME,
        entry_id=first.id,
        start_time=time(13),
    )
    assert validate_requested_change(ignored, current, current)[0].code == (
        "requested_change_not_applied"
    )


def test_reorder_uses_chronological_visible_indices() -> None:
    current = two_place_plan()
    late_entry, early_entry = current.entries
    current = current.model_copy(
        update={
            "entries": [
                late_entry.model_copy(
                    update={"start_time": time(13), "end_time": time(14, 30)}
                ),
                early_entry,
            ]
        }
    )
    moved_early = current.entries[1].model_copy(
        update={"start_time": time(15), "end_time": time(16)}
    )
    successful_candidate = current.model_copy(
        update={"entries": [current.entries[0], moved_early]}
    )
    intent = PlanChangeIntent(
        action=IntentAction.REORDER_PLACES,
        from_index=0,
        to_index=1,
    )

    assert validate_requested_change(intent, current, successful_candidate) == []


def test_reorder_rejects_list_only_change_when_visible_order_is_unchanged() -> None:
    current = two_place_plan()
    late_entry, early_entry = current.entries
    current = current.model_copy(
        update={
            "entries": [
                late_entry.model_copy(
                    update={"start_time": time(13), "end_time": time(14, 30)}
                ),
                early_entry,
            ]
        }
    )
    list_only_candidate = current.model_copy(
        update={"entries": [current.entries[1], current.entries[0]]}
    )
    intent = PlanChangeIntent(
        action=IntentAction.REORDER_PLACES,
        from_index=0,
        to_index=1,
    )

    issues = validate_requested_change(intent, current, list_only_candidate)

    assert issues[0].code == "requested_change_not_applied"
    assert issues[0].message == "Candidate did not change the visible itinerary order."


def test_reorder_rejects_added_or_removed_stops() -> None:
    current = two_place_plan()
    first, second = current.entries
    replacement = second.model_copy(update={"id": "entry_replacement"})
    candidate = current.model_copy(
        update={
            "entries": [
                replacement.model_copy(
                    update={"start_time": time(8), "end_time": time(8, 30)}
                ),
                first,
            ]
        }
    )
    intent = PlanChangeIntent(
        action=IntentAction.REORDER_PLACES,
        from_index=0,
        to_index=1,
    )

    issues = validate_requested_change(intent, current, candidate)

    assert (
        issues[0].message == "Candidate must preserve the same stops when reordering."
    )


def test_reorder_rejects_when_requested_stop_does_not_change_visible_position() -> None:
    current = two_place_plan()
    first, second = current.entries
    third = second.model_copy(
        update={
            "id": "entry_third",
            "start_time": time(13),
            "end_time": time(14),
        }
    )
    current = current.model_copy(update={"entries": [first, second, third]})
    candidate = current.model_copy(
        update={
            "entries": [
                first,
                second.model_copy(
                    update={"start_time": time(15), "end_time": time(16)}
                ),
                third,
            ]
        }
    )
    intent = PlanChangeIntent(
        action=IntentAction.REORDER_PLACES,
        from_index=0,
        to_index=0,
    )

    issues = validate_requested_change(intent, current, candidate)

    assert issues[0].message == (
        "Candidate did not move the requested stop in visible itinerary."
    )


def test_non_reorder_edits_require_an_existing_target_and_a_real_change() -> None:
    current = plan()
    entry = current.entries[0]
    replacement = entry.model_copy(
        update={"place": entry.place.model_copy(update={"name": "Hue Museum"})}
    )
    replaced_candidate = current.model_copy(update={"entries": [replacement]})

    remove_issues = validate_requested_change(
        PlanChangeIntent(action=IntentAction.REMOVE_PLACE, place_name="Unknown"),
        current,
        current,
    )
    replace_issues = validate_requested_change(
        PlanChangeIntent(
            action=IntentAction.REPLACE_PLACE,
            place_name="Unknown",
            replacement_place_name="Hue Museum",
        ),
        current,
        replaced_candidate,
    )
    day_issues = validate_requested_change(
        PlanChangeIntent(
            action=IntentAction.CHANGE_DAY,
            entry_id=entry.id,
            day_index=entry.day_index,
        ),
        current,
        current,
    )
    time_issues = validate_requested_change(
        PlanChangeIntent(
            action=IntentAction.CHANGE_TIME,
            entry_id=entry.id,
            start_time=entry.start_time,
            end_time=entry.end_time,
        ),
        current,
        current,
    )

    assert remove_issues[0].message == (
        "The requested removal target is not in the current plan."
    )
    assert replace_issues[0].message == (
        "The requested replacement target is not in the current plan."
    )
    assert day_issues[0].message == "Candidate did not change the requested day."
    assert time_issues[0].message == "Candidate did not change the requested time."


def test_add_place_keeps_existing_sources_and_adds_live_search_source() -> None:
    current = plan()
    new_source = SourceReference(
        source_id="source_pagoda",
        title="Thien Mu Pagoda Hue visitor guide",
        url="https://travel.example/hue/thien-mu-pagoda",
        snippet="Thien Mu Pagoda Hue visitor information.",
        retrieval_query="Thien Mu Pagoda Hue sightseeing",
    )
    pagoda = PlaceRecommendation(
        place_id="place_pagoda",
        name="Thien Mu Pagoda",
        description="A sourced pagoda recommendation.",
        source_references=[new_source],
        opening_hours="unverified",
    )
    candidate_plan = current.model_copy(
        update={
            "entries": [
                current.entries[0],
                ScheduleEntry(
                    id="entry_pagoda",
                    day_index=2,
                    start_time=time(9),
                    end_time=time(10, 30),
                    place=pagoda,
                ),
            ]
        }
    )

    def coordinator_handler(prompt: str, schema: type[BaseModel]) -> BaseModel:
        if schema is CoordinatorDecision:
            return CoordinatorDecision(
                intent=PlanChangeIntent(
                    action=IntentAction.ADD_PLACE,
                    place_name="Thien Mu Pagoda",
                ),
                requires_planner=True,
            )
        return CoordinatorExplanation(message="Added the place.")

    live_result = SearchResult(
        source_id=new_source.source_id,
        title=new_source.title,
        url=new_source.url,
        snippet=new_source.snippet,
        score=0.9,
    )
    config = RuntimeConfig()
    search = FakeSearch([live_result])
    service = TravelPlannerService(
        CoordinatorAgent(ScriptedModel(coordinator_handler)),
        PlannerAgent(planner_model(candidate_plan), search, config),
        config=config,
    )

    response = service.handle_turn(
        thread_id="thread-add",
        message="Add Thien Mu Pagoda.",
        current_plan=current,
    )

    assert response.status is ResponseStatus.COMMITTED
    assert response.search_calls == 1
    assert response.current_plan is not None
    urls = {
        str(reference.url)
        for entry in response.current_plan.entries
        for reference in entry.place.source_references
    }
    assert urls == {
        "https://travel.example/hue/imperial-city",
        "https://travel.example/hue/thien-mu-pagoda",
    }


def test_add_place_accepts_vietnamese_name_variant_but_not_another_place() -> None:
    current = plan()
    original = current.entries[0]
    new_entry = original.model_copy(
        update={
            "id": "entry_lo_lo_chai",
            "day_index": 2,
            "place": original.place.model_copy(
                update={"place_id": "place_lo_lo_chai", "name": "Lo Lo Chai Village"}
            ),
        }
    )
    intent = PlanChangeIntent(
        action=IntentAction.ADD_PLACE,
        place_name="L\u00f4 L\u00f4 Ch\u1ea3i",
    )
    candidate = current.model_copy(update={"entries": [original, new_entry]})

    assert validate_requested_change(intent, current, candidate) == []

    regenerated_id = original.model_copy(update={"id": "regenerated_old_stop"})
    same_places_with_new_id = current.model_copy(
        update={"entries": [regenerated_id, new_entry]}
    )
    assert validate_requested_change(intent, current, same_places_with_new_id) == []

    wrong_place = new_entry.model_copy(
        update={
            "place": new_entry.place.model_copy(update={"name": "Lo Lo Chai Market"})
        }
    )
    wrong_candidate = current.model_copy(update={"entries": [original, wrong_place]})
    assert validate_requested_change(intent, current, wrong_candidate)[0].code == (
        "requested_change_not_applied"
    )

    lost_existing_stop = current.model_copy(
        update={"entries": [new_entry, wrong_place]}
    )
    assert validate_requested_change(intent, current, lost_existing_stop)[0].code == (
        "requested_change_not_applied"
    )
