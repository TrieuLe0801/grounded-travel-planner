"""Bounded LangGraph nodes; only ``tavily_tool`` invokes the search provider."""

from __future__ import annotations

from grounded_travel_planner.agents.chat import ChatAgent
from grounded_travel_planner.agents.coordinator import CoordinatorAgent
from grounded_travel_planner.agents.planner import PlannerAgent
from grounded_travel_planner.config import RuntimeConfig
from grounded_travel_planner.contracts import (
    AgentResponse,
    IntentAction,
    ResponseStatus,
    SearchResult,
    SourceReference,
    TavilyToolRequest,
    TripRequest,
    ValidationIssue,
)
from grounded_travel_planner.graph.state import PlannerState
from grounded_travel_planner.i18n import localized
from grounded_travel_planner.policies.input_validation import validate_trip_request
from grounded_travel_planner.policies.plan_commit import validate_candidate
from grounded_travel_planner.providers import (
    PlaceSearchProvider,
    TraceSink,
)
from utils.redaction import sanitize_error


def _metadata(state: PlannerState, role: str) -> dict[str, str]:
    return {
        "thread_id": state["thread_id"],
        "turn_id": state["turn_id"],
        "agent_role": role,
    }


def _step(state: PlannerState) -> int:
    return state.get("graph_steps", 0) + 1


def _candidate_sources(state: PlannerState) -> list[SourceReference]:
    candidate = state.get("candidate")
    if candidate is None:
        return []
    return list(
        {
            str(item.url).rstrip("/"): item for item in candidate.returned_sources
        }.values()
    )


def _as_sources(
    request: TavilyToolRequest, results: list[SearchResult]
) -> list[SourceReference]:
    """Normalize provider output before either agent receives it."""

    return [
        SourceReference(
            source_id=item.source_id,
            title=item.title,
            url=item.url,
            snippet=item.snippet,
            retrieval_query=request.query,
            supports_opening_hours=item.supports_opening_hours,
        )
        for item in results[: request.max_results]
    ]


class GraphNodes:
    def __init__(
        self,
        coordinator: CoordinatorAgent,
        planner: PlannerAgent,
        chat: ChatAgent,
        search: PlaceSearchProvider,
        trace_sink: TraceSink,
        config: RuntimeConfig,
    ) -> None:
        self.coordinator = coordinator
        self.planner = planner
        self.chat = chat
        self.search = search
        self.trace_sink = trace_sink
        self.config = config

    def coordinator_route(self, state: PlannerState) -> dict:
        """Classify, summarize and validate input in one bounded graph step."""

        step = _step(state)
        try:
            decision = self.coordinator.classify(
                state["message"],
                request=state.get("request"),
                current_plan=state.get("current_plan"),
                session_summary=state.get("session_summary", ""),
                conversation_history=state.get("conversation_history", []),
                metadata=_metadata(state, self.coordinator.role),
                language=state.get("language", "vi"),
            )
            if decision.requires_planner:
                request, issues = self._validated_request(state, decision.intent)
            else:
                request, issues = state.get("request"), []
            self.trace_sink.record_event(
                "coordinator.route",
                {"intent": decision.intent.action.value},
                thread_id=state["thread_id"],
            )
            return {
                "decision": decision,
                "request": request,
                "response_hint": decision.response_hint,
                "session_summary": (
                    decision.session_summary or state.get("session_summary", "")
                )[:1200],
                "validation_issues": issues,
                "graph_steps": step,
            }
        except Exception as error:  # noqa: BLE001
            return {
                "graph_steps": step,
                "validation_issues": [
                    ValidationIssue(
                        code="coordinator_model_failure",
                        message=f"Coordinator failed safely: {sanitize_error(error)}",
                    )
                ],
                "response_hint": "Chưa thể hiểu yêu cầu này.",
            }

    def _validated_request(
        self, state: PlannerState, intent: object
    ) -> tuple[TripRequest | None, list[ValidationIssue]]:
        request = state.get("request")
        current_plan = state.get("current_plan")
        action = getattr(intent, "action", None)
        resizing_trip = action in {
            IntentAction.EXTEND_TRIP,
            IntentAction.SHORTEN_TRIP,
        }
        if resizing_trip and current_plan is None:
            return request, [
                ValidationIssue(
                    code="trip_resize_requires_current_plan",
                    message="A current itinerary is required to change trip length.",
                )
            ]
        if resizing_trip and current_plan is not None:
            target = getattr(intent, "day_count", None)
            delta = getattr(intent, "day_count_delta", None)
            if target is None and isinstance(delta, int):
                if action is IntentAction.EXTEND_TRIP:
                    target = current_plan.day_count + delta
                else:
                    target = current_plan.day_count - delta
            if target is None:
                return None, [
                    ValidationIssue(
                        code=(
                            "trip_extension_target_required"
                            if action is IntentAction.EXTEND_TRIP
                            else "trip_shortening_target_required"
                        ),
                        message=(
                            "Trip length change needs a target day count or "
                            "increment."
                        ),
                    )
                ]
            if not 1 <= target <= 7:
                return None, [
                    ValidationIssue(
                        code="day_count_out_of_range",
                        message="Day count must be between 1 and 7.",
                    )
                ]
            if action is IntentAction.EXTEND_TRIP and target <= current_plan.day_count:
                return None, [
                    ValidationIssue(
                        code="trip_extension_must_increase",
                        message="Trip extension must increase the current day count.",
                    )
                ]
            if action is IntentAction.SHORTEN_TRIP and target >= current_plan.day_count:
                return None, [
                    ValidationIssue(
                        code="trip_shortening_must_decrease",
                        message="Trip shortening must decrease the current day count.",
                    )
                ]
            request = TripRequest(
                destination=current_plan.destination,
                start_date=current_plan.start_date,
                day_count=target,
            )
        elif request is None and current_plan is not None:
            request = TripRequest(
                destination=current_plan.destination,
                start_date=current_plan.start_date,
                day_count=current_plan.day_count,
            )
        requested_day = getattr(intent, "day_index", None)
        if (
            getattr(intent, "action", None) is IntentAction.CHANGE_DAY
            and request is not None
            and isinstance(requested_day, int)
            and requested_day > request.day_count
        ):
            return request, [
                ValidationIssue(
                    code="requested_day_out_of_range",
                    message="The requested day is outside the selected trip days.",
                )
            ]
        return request, validate_trip_request(request)

    def planner_prepare(self, state: PlannerState) -> dict:
        step = _step(state)
        decision = state["decision"]
        request = state.get("request")
        if request is None:
            return {
                "graph_steps": step,
                "validation_issues": [
                    ValidationIssue(
                        code="trip_request_required",
                        message="A valid trip request is required before planning.",
                    )
                ],
            }
        return {
            "graph_steps": step,
            "search_request": self.planner.tool_request(decision.intent, request),
        }

    def tavily_tool(self, state: PlannerState) -> dict:
        """The sole provider boundary for bounded Planner and Chat Tavily calls."""

        step = _step(state)
        request = state.get("search_request")
        if request is None:
            return {"graph_steps": step}
        if (
            request.owner not in {"planner", "chat"}
            or not request.query.strip()
            or not 1 <= request.max_results <= 8
        ):
            return {
                "graph_steps": step,
                "search_request": None,
                "validation_issues": [
                    ValidationIssue(
                        code="invalid_search_request",
                        message="The bounded search request was invalid.",
                    )
                ],
            }
        calls = state.get("search_calls", 0)
        if calls >= self.config.search_call_limit:
            return {
                "graph_steps": step,
                "search_request": None,
                "validation_issues": [
                    ValidationIssue(
                        code="search_call_limit",
                        message="The bounded search-call limit was reached.",
                    )
                ],
            }
        calls += 1
        self.trace_sink.record_event(
            "tool.tavily.start",
            {
                "owner": request.owner,
                "max_results": request.max_results,
                "search_call": calls,
            },
            thread_id=state["thread_id"],
        )
        try:
            sources = _as_sources(
                request,
                self.search.search_places(
                    request.query,
                    max_results=request.max_results,
                    thread_id=state["thread_id"],
                ),
            )
            self.trace_sink.record_event(
                "tool.tavily.success",
                {
                    "owner": request.owner,
                    "result_count": len(sources),
                    "search_call": calls,
                },
                thread_id=state["thread_id"],
            )
            update: dict[str, object] = {
                "graph_steps": step,
                "search_calls": calls,
                "search_request": None,
                "last_search_owner": request.owner,
            }
            update[f"{request.owner}_search_sources"] = sources
            return update
        except Exception as error:  # noqa: BLE001
            self.trace_sink.record_event(
                "tool.tavily.failure",
                {"owner": request.owner, "search_call": calls},
                thread_id=state["thread_id"],
            )
            update = {
                "graph_steps": step,
                "search_calls": calls,
                "search_request": None,
                "last_search_owner": request.owner,
            }
            if request.owner == "planner":
                update["validation_issues"] = [
                    ValidationIssue(
                        code="search_provider_failure",
                        message=f"Planner research failed safely: {sanitize_error(error)}",
                    )
                ]
            else:
                update["chat_search_failed"] = True
            return update

    def planner_delegate(self, state: PlannerState) -> dict:
        step = _step(state)
        try:
            candidate = self.planner.propose(
                intent=state["decision"].intent,
                request=state["request"],
                current_plan=state.get("current_plan"),
                metadata=_metadata(state, self.planner.role),
                session_summary=state.get("session_summary", ""),
                retained_sources=state.get("planner_search_sources"),
                language=state.get("language", "vi"),
            )
            self.trace_sink.record_event(
                "planner.propose",
                {"intent": state["decision"].intent.action.value, "repair": False},
                thread_id=state["thread_id"],
            )
            return {
                "candidate": candidate,
                "validation_issues": [],
                "graph_steps": step,
            }
        except Exception as error:  # noqa: BLE001
            return {
                "graph_steps": step,
                "validation_issues": [
                    ValidationIssue(
                        code="planner_model_failure",
                        message=f"Planner failed safely: {sanitize_error(error)}",
                    )
                ],
                "response_hint": "Lịch trình trước đó đã được giữ nguyên.",
            }

    def validate_candidate(self, state: PlannerState) -> dict:
        """Validate once, then perform at most one repair through Planner in-node."""

        step = _step(state)
        issues = validate_candidate(
            state.get("candidate"),
            state.get("request"),
            intent=state.get("decision").intent if state.get("decision") else None,
            current_plan=state.get("current_plan"),
        )
        repair_attempts = state.get("repair_attempts", 0)
        candidate = state.get("candidate")
        if (
            issues
            and repair_attempts < self.config.repair_attempt_limit
            and candidate is not None
        ):
            repair_attempts += 1
            try:
                candidate = self.planner.propose(
                    intent=state["decision"].intent,
                    request=state["request"],
                    current_plan=state.get("current_plan"),
                    metadata=_metadata(state, self.planner.role),
                    session_summary=state.get("session_summary", ""),
                    repair_issues=issues,
                    retained_sources=_candidate_sources(state),
                    language=state.get("language", "vi"),
                )
                issues = validate_candidate(
                    candidate,
                    state.get("request"),
                    intent=state["decision"].intent,
                    current_plan=state.get("current_plan"),
                )
            except Exception as error:  # noqa: BLE001
                issues = [
                    ValidationIssue(
                        code="planner_model_failure",
                        message=f"Planner repair failed safely: {sanitize_error(error)}",
                    )
                ]
        self.trace_sink.record_event(
            "validation.candidate",
            {
                "issue_codes": [issue.code for issue in issues],
                "repair_attempts": repair_attempts,
            },
            thread_id=state["thread_id"],
        )
        return {
            "candidate": candidate,
            "validation_issues": issues,
            "repair_attempts": repair_attempts,
            "graph_steps": step,
        }

    def chat_respond(self, state: PlannerState) -> dict:
        """Decide, optionally route through the tool, then finalize on re-entry."""

        step = _step(state)
        decision = state.get("decision")
        issues = list(state.get("validation_issues", []))
        candidate = state.get("candidate")
        mutates = bool(decision and decision.intent.mutates_plan)
        committed = bool(mutates and not issues and candidate and candidate.plan)
        current_plan = (
            candidate.plan if committed and candidate else state.get("current_plan")
        )
        chat_decision = state.get("chat_decision")
        if chat_decision is None:
            try:
                chat_decision = self.chat.decide_search(
                    message=state["message"],
                    intent=decision.intent if decision else None,
                    candidate=candidate if committed else None,
                    committed=committed,
                    current_plan=current_plan,
                    issues=issues,
                    response_hint=state.get("response_hint", ""),
                    session_summary=state.get("session_summary", ""),
                    metadata=_metadata(state, self.chat.role),
                    language=state.get("language", "vi"),
                )
                request = self.chat.tool_request(chat_decision)
                if (
                    request is not None
                    and state.get("search_calls", 0) < self.config.search_call_limit
                    and step + 2 <= self.config.graph_step_limit
                ):
                    return {
                        "chat_decision": chat_decision,
                        "search_request": request,
                        "graph_steps": step,
                    }
                if request is not None:
                    chat_decision = chat_decision.model_copy(
                        update={"should_search": False, "query": ""}
                    )
            except Exception:  # noqa: BLE001 - stable user-safe fallback
                chat_decision = None
        if chat_decision is None:
            message = localized("background_failure", state.get("language", "vi"))
            sources: list[SourceReference] = []
        else:
            try:
                response_message = self.chat.respond(
                    decision=chat_decision,
                    message=state["message"],
                    intent=decision.intent if decision else None,
                    candidate=candidate if committed else None,
                    committed=committed,
                    current_plan=current_plan,
                    issues=issues,
                    response_hint=state.get("response_hint", ""),
                    session_summary=state.get("session_summary", ""),
                    sources=state.get("chat_search_sources", []),
                    search_failed=state.get("chat_search_failed", False),
                    metadata=_metadata(state, self.chat.role),
                    language=state.get("language", "vi"),
                )
                message = response_message.message
                sources = list(state.get("chat_search_sources", []))
            except Exception:  # noqa: BLE001 - stable user-safe fallback
                message, sources = (
                    localized("background_failure", state.get("language", "vi")),
                    [],
                )
        status = (
            ResponseStatus.COMMITTED
            if committed
            else (
                ResponseStatus.PROVIDER_ERROR
                if any("failure" in issue.code for issue in issues)
                else ResponseStatus.REJECTED if issues else ResponseStatus.UNCHANGED
            )
        )
        response = AgentResponse(
            status=status,
            message=message,
            current_plan=current_plan,
            committed=committed,
            intent=decision.intent if decision else None,
            validation_issues=issues,
            graph_steps=step,
            search_calls=state.get("search_calls", 0),
            repair_attempts=state.get("repair_attempts", 0),
            source_references=sources,
            metadata={
                "thread_id": state["thread_id"],
                "turn_id": state["turn_id"],
                "session_summary": state.get("session_summary", "")[:1200],
                "coordinator_model": self.coordinator.model_name,
                "planner_model": self.planner.model_name,
                "chat_role": self.chat.role,
                "chat_model": self.chat.model_name,
            },
        )
        self.trace_sink.record_event(
            "chat.respond",
            {"status": status.value, "committed": committed},
            thread_id=state["thread_id"],
        )
        return {
            "current_plan": current_plan,
            "committed": committed,
            "graph_steps": step,
            "response": response,
        }
