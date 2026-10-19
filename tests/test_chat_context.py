"""Offline regression checks for the shared bounded Tavily tool node."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from datetime import date, time
from typing import Any, TypeVar

from pydantic import BaseModel

from grounded_travel_planner.agents import ChatAgent, CoordinatorAgent, PlannerAgent
from grounded_travel_planner.config import RuntimeConfig
from grounded_travel_planner.contracts import (
    ChatResponse,
    ChatSearchDecision,
    ConversationTurn,
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
from grounded_travel_planner.providers import ProviderError
from grounded_travel_planner.service import TravelPlannerService

T = TypeVar("T", bound=BaseModel)


class ScriptedModel:
    def __init__(self, handler: Callable[[str, type[BaseModel]], BaseModel]) -> None:
        self.handler = handler
        self.model_name = "offline-model"
        self.calls: list[tuple[str, str]] = []

    def generate_structured(
        self,
        prompt: str,
        schema: type[T],
        *,
        metadata: Mapping[str, str] | None = None,
    ) -> T:
        self.calls.append((schema.__name__, prompt))
        return schema.model_validate(self.handler(prompt, schema))


class Search:
    def __init__(self, *, fail: bool = False, empty: bool = False) -> None:
        self.fail = fail
        self.empty = empty
        self.calls: list[tuple[str, int, str]] = []

    def search_places(
        self, query: str, *, max_results: int, thread_id: str
    ) -> list[SearchResult]:
        self.calls.append((query, max_results, thread_id))
        if self.fail:
            raise ProviderError("offline search failure")
        if self.empty:
            return []
        return [
            SearchResult(
                source_id="source",
                title="Offline source",
                url="https://example.test/a",
                snippet="Offline grounded result.",
            )
        ]


class Trace:
    def __init__(self) -> None:
        self.events: list[tuple[str, dict[str, Any], str]] = []

    def record_event(
        self, name: str, payload: Mapping[str, Any], *, thread_id: str
    ) -> None:
        self.events.append((name, dict(payload), thread_id))


def _plan() -> SightseeingPlan:
    source = SourceReference(
        source_id="source",
        title="Offline source",
        url="https://example.test/a",
        retrieval_query="Hue",
    )
    return SightseeingPlan(
        plan_id="plan",
        destination="Hue",
        start_date=date(2026, 11, 1),
        day_count=1,
        entries=[
            ScheduleEntry(
                id="entry",
                day_index=1,
                start_time=time(9),
                end_time=time(10),
                place=PlaceRecommendation(
                    place_id="place",
                    name="Imperial City",
                    description="Offline.",
                    source_references=[source],
                ),
            )
        ],
    )


def _service(
    *,
    planner_action: IntentAction = IntentAction.ORDINARY_CHAT,
    chat_search: bool = False,
    search: Search | None = None,
    trace: Trace | None = None,
    candidate: SightseeingPlan | None = None,
    config: RuntimeConfig | None = None,
) -> TravelPlannerService:
    runtime = config or RuntimeConfig()

    def coordinator(_prompt: str, schema: type[BaseModel]) -> BaseModel:
        assert schema is CoordinatorDecision
        return CoordinatorDecision(
            intent=PlanChangeIntent(action=planner_action, user_message="offline"),
            requires_planner=planner_action is not IntentAction.ORDINARY_CHAT,
            session_summary="bounded handoff",
        )

    def planner(_prompt: str, schema: type[BaseModel]) -> BaseModel:
        assert schema is PlannerProposal
        return PlannerProposal(plan=candidate or _plan(), summary="grounded candidate")

    def chat(_prompt: str, schema: type[BaseModel]) -> BaseModel:
        if schema is ChatSearchDecision:
            return ChatSearchDecision(
                should_search=chat_search,
                query="private current query" if chat_search else "",
                message="Không cần tìm thêm." if not chat_search else "",
            )
        assert schema is ChatResponse
        return ChatResponse(message="Đã trả lời từ nguồn tìm kiếm.")

    search_provider = search or Search()
    return TravelPlannerService(
        CoordinatorAgent(ScriptedModel(coordinator)),
        PlannerAgent(ScriptedModel(planner), runtime),
        ChatAgent(ScriptedModel(chat), runtime),
        search=search_provider,
        trace_sink=trace,
        config=runtime,
    )


def test_only_graph_tool_node_calls_search_and_routes_owner_sources() -> None:
    search = Search()
    service = _service(
        planner_action=IntentAction.CREATE_TRIP, chat_search=True, search=search
    )

    response = service.handle_turn(
        thread_id="thread-tool",
        message="Tạo lịch Huế",
        request=TripRequest(
            destination="Hue", start_date=date(2026, 11, 1), day_count=1
        ),
    )

    assert response.status is ResponseStatus.COMMITTED
    assert [call[1] for call in search.calls] == [8, 5]
    assert not hasattr(service.planner, "_search")
    assert not hasattr(service.chat, "_search")
    assert response.source_references[0].retrieval_query == "private current query"
    assert all(
        reference.retrieval_query != "private current query"
        for entry in response.current_plan.entries
        for reference in entry.place.source_references
    )


def test_tool_events_are_redacted_and_count_failures_before_attempt() -> None:
    search = Search(fail=True)
    trace = Trace()
    service = _service(chat_search=True, search=search, trace=trace)

    response = service.handle_turn(thread_id="thread-redacted", message="Tin mới?")

    assert response.search_calls == 1
    assert response.current_plan is None
    tool_events = [
        event for event in trace.events if event[0].startswith("tool.tavily")
    ]
    assert [event[0] for event in tool_events] == [
        "tool.tavily.start",
        "tool.tavily.failure",
    ]
    assert all(event[2] == "thread-redacted" for event in tool_events)
    assert tool_events[0][1] == {
        "owner": "chat",
        "max_results": 5,
        "search_call": 1,
    }
    assert tool_events[1][1] == {"owner": "chat", "search_call": 1}
    assert "private current query" not in str(tool_events)


def test_chat_no_search_no_budget_and_empty_results_are_safe() -> None:
    current = _plan()
    unchanged = _service(chat_search=False).handle_turn(
        thread_id="thread-no-search", message="Cảm ơn", current_plan=current
    )
    assert unchanged.search_calls == 0
    assert unchanged.current_plan == current

    bounded = _service(
        chat_search=True, config=RuntimeConfig(search_call_limit=0)
    ).handle_turn(thread_id="thread-budget", message="Tin mới?", current_plan=current)
    assert bounded.search_calls == 0
    assert bounded.current_plan == current

    empty_response = _service(chat_search=True, search=Search(empty=True)).handle_turn(
        thread_id="thread-empty", message="Tin mới?", current_plan=current
    )
    assert empty_response.search_calls == 1
    assert empty_response.source_references == []
    assert empty_response.current_plan == current


def test_planner_sources_stay_grounded_and_steps_remain_bounded() -> None:
    service = _service(
        planner_action=IntentAction.CREATE_TRIP,
        chat_search=True,
        config=RuntimeConfig(graph_step_limit=8),
    )
    response = service.handle_turn(
        thread_id="thread-steps",
        message="Tạo lịch",
        request=TripRequest(
            destination="Hue", start_date=date(2026, 11, 1), day_count=1
        ),
    )

    assert response.committed is True
    assert response.repair_attempts == 0
    assert response.graph_steps <= 8
    assert response.current_plan is not None
    assert str(response.current_plan.entries[0].place.source_references[0].url) == (
        "https://example.test/a"
    )


def test_coordinator_receives_bounded_history_and_handoff_summary() -> None:
    prompts: list[str] = []

    def coordinator(prompt: str, schema: type[BaseModel]) -> BaseModel:
        assert schema is CoordinatorDecision
        prompts.append(prompt)
        return CoordinatorDecision(
            intent=PlanChangeIntent(action=IntentAction.ORDINARY_CHAT),
            requires_planner=False,
            session_summary="summary-" + ("x" * 1300),
        )

    runtime = RuntimeConfig()
    service = TravelPlannerService(
        CoordinatorAgent(ScriptedModel(coordinator)),
        PlannerAgent(
            ScriptedModel(lambda _p, _s: PlannerProposal(plan=_plan())), runtime
        ),
        ChatAgent(
            ScriptedModel(
                lambda _p, schema: (
                    ChatSearchDecision(should_search=False, message="Đã hiểu.")
                    if schema is ChatSearchDecision
                    else ChatResponse(message="Đã hiểu.")
                )
            ),
            runtime,
        ),
        search=Search(),
        config=runtime,
    )
    history = [
        ConversationTurn(role="user", content=f"old-{index}-" + ("z" * 2000))
        for index in range(12)
    ]
    history[-1] = ConversationTurn(role="assistant", content="newest history")

    response = service.handle_turn(
        thread_id="thread-context",
        message="dựa vào lịch trình đã đề xuất",
        session_summary="prior-" + ("p" * 1300),
        conversation_history=history,
    )

    assert "newest history" in prompts[0]
    assert "old-0-" not in prompts[0]
    assert len(response.metadata["session_summary"]) == 1200


def test_repair_then_chat_search_fits_eight_steps_and_isolates_sources() -> None:
    runtime = RuntimeConfig(graph_step_limit=8)
    planner_calls = 0

    def coordinator(_prompt: str, schema: type[BaseModel]) -> BaseModel:
        assert schema is CoordinatorDecision
        return CoordinatorDecision(
            intent=PlanChangeIntent(action=IntentAction.CREATE_TRIP),
            requires_planner=True,
        )

    def planner(_prompt: str, schema: type[BaseModel]) -> BaseModel:
        nonlocal planner_calls
        assert schema is PlannerProposal
        planner_calls += 1
        if planner_calls == 1:
            entry = _plan().entries[0]
            invalid = _plan().model_copy(
                update={
                    "entries": [
                        entry,
                        entry.model_copy(
                            update={"id": "overlap", "end_time": time(10)}
                        ),
                    ]
                }
            )
            return PlannerProposal(plan=invalid, summary="invalid first proposal")
        return PlannerProposal(plan=_plan(), summary="repaired plan")

    def chat(_prompt: str, schema: type[BaseModel]) -> BaseModel:
        if schema is ChatSearchDecision:
            return ChatSearchDecision(should_search=True, query="current chat query")
        assert schema is ChatResponse
        return ChatResponse(message="Nguồn Chat đã sẵn sàng.")

    service = TravelPlannerService(
        CoordinatorAgent(ScriptedModel(coordinator)),
        PlannerAgent(ScriptedModel(planner), runtime),
        ChatAgent(ScriptedModel(chat), runtime),
        search=Search(),
        config=runtime,
    )
    response = service.handle_turn(
        thread_id="thread-worst-path",
        message="Tạo lịch và thông tin hiện tại",
        request=TripRequest(
            destination="Hue", start_date=date(2026, 11, 1), day_count=1
        ),
    )

    assert response.committed is True
    assert response.repair_attempts == 1
    assert response.search_calls == 2
    assert response.graph_steps == 8
    assert response.current_plan is not None
    assert all(
        reference.retrieval_query != "current chat query"
        for entry in response.current_plan.entries
        for reference in entry.place.source_references
    )
    assert [reference.retrieval_query for reference in response.source_references] == [
        "current chat query"
    ]
