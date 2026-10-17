"""Node factory for the bounded Coordinator/Planner graph."""

from __future__ import annotations

from grounded_travel_planner.agents.chat import ChatAgent
from grounded_travel_planner.agents.coordinator import CoordinatorAgent
from grounded_travel_planner.agents.planner import PlannerAgent
from grounded_travel_planner.config import RuntimeConfig
from grounded_travel_planner.contracts import (
    AgentResponse,
    IntentAction,
    ResponseStatus,
    SourceReference,
    TripRequest,
    ValidationIssue,
)
from grounded_travel_planner.graph.state import PlannerState
from grounded_travel_planner.policies.input_validation import validate_trip_request
from grounded_travel_planner.policies.plan_commit import validate_candidate
from grounded_travel_planner.providers import ProviderError, TraceSink
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
    """Retain provider-returned sources, never untrusted candidate references."""

    candidate = state.get("candidate")
    if candidate is None:
        return []
    unique: dict[str, SourceReference] = {}
    for source in candidate.returned_sources:
        unique[str(source.url).rstrip("/")] = source
    return list(unique.values())


class GraphNodes:
    """Deterministic policy nodes around the injected runtime agents."""

    def __init__(
        self,
        coordinator: CoordinatorAgent,
        planner: PlannerAgent,
        chat: ChatAgent,
        trace_sink: TraceSink,
        config: RuntimeConfig,
    ) -> None:
        self.coordinator = coordinator
        self.planner = planner
        self.chat = chat
        self.trace_sink = trace_sink
        self.config = config

    def coordinator_route(self, state: PlannerState) -> dict:
        step = _step(state)
        metadata = _metadata(state, self.coordinator.role)
        try:
            decision = self.coordinator.classify(
                state["message"],
                request=state.get("request"),
                current_plan=state.get("current_plan"),
                metadata=metadata,
            )
            self.trace_sink.record_event(
                "coordinator.route",
                {"intent": decision.intent.action.value},
                thread_id=state["thread_id"],
            )
            return {
                "decision": decision,
                "response_hint": decision.response_hint,
                "graph_steps": step,
                "validation_issues": [],
            }
        except Exception as error:  # noqa: BLE001 - preserve state at model boundary
            issue = ValidationIssue(
                code="coordinator_model_failure",
                message=f"Coordinator failed safely: {sanitize_error(error)}",
            )
            return {
                "graph_steps": step,
                "validation_issues": [issue],
                "response_hint": "Chưa thể hiểu yêu cầu này.",
            }

    def validate_input(self, state: PlannerState) -> dict:
        step = _step(state)
        request = state.get("request")
        current_plan = state.get("current_plan")
        decision = state.get("decision")
        if (
            decision is not None
            and decision.intent.action is IntentAction.EXTEND_TRIP
            and current_plan is not None
        ):
            target = decision.intent.day_count
            if target is None and decision.intent.day_count_delta is not None:
                target = current_plan.day_count + decision.intent.day_count_delta
            if target is None:
                issues = [
                    ValidationIssue(
                        code="trip_extension_target_required",
                        message="Trip extension needs a target day count or increment.",
                    )
                ]
            elif target <= current_plan.day_count:
                issues = [
                    ValidationIssue(
                        code="trip_extension_must_increase",
                        message="Trip extension must increase the current day count.",
                    )
                ]
            elif target > 7:
                issues = [
                    ValidationIssue(
                        code="day_count_out_of_range",
                        message="Day count must be between 1 and 7.",
                    )
                ]
            else:
                request = TripRequest(
                    destination=current_plan.destination,
                    start_date=current_plan.start_date,
                    day_count=target,
                )
                issues = validate_trip_request(request)
        elif request is None and current_plan is not None:
            plan = current_plan
            request = TripRequest(
                destination=plan.destination,
                start_date=plan.start_date,
                day_count=plan.day_count,
            )
            issues = validate_trip_request(request)
        else:
            issues = validate_trip_request(request)
        self.trace_sink.record_event(
            "validation.input",
            {"issue_codes": [issue.code for issue in issues]},
            thread_id=state["thread_id"],
        )
        return {
            "request": request,
            "validation_issues": issues,
            "graph_steps": step,
        }

    def planner_delegate(self, state: PlannerState) -> dict:
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
        metadata = _metadata(state, self.planner.role)
        repair_issues = state.get("repair_issues") or []
        expected_search_calls = int(
            self.planner.requires_search(
                decision.intent,
                is_repair=bool(repair_issues),
            )
        )
        search_calls = state.get("search_calls", 0) + expected_search_calls
        if search_calls > self.config.search_call_limit:
            return {
                "graph_steps": step,
                "search_calls": state.get("search_calls", 0),
                "validation_issues": [
                    ValidationIssue(
                        code="search_call_limit",
                        message="The bounded search-call limit was reached.",
                    )
                ],
            }
        try:
            result = self.planner.propose(
                intent=decision.intent,
                request=request,
                current_plan=state.get("current_plan"),
                thread_id=state["thread_id"],
                metadata=metadata,
                repair_issues=repair_issues or None,
                retained_sources=(_candidate_sources(state) if repair_issues else None),
            )
            if result.search_calls != expected_search_calls:
                raise ProviderError("Search call accounting mismatch")
            self.trace_sink.record_event(
                "planner.propose",
                {
                    "intent": decision.intent.action.value,
                    "search_calls": result.search_calls,
                    "repair": bool(repair_issues),
                },
                thread_id=state["thread_id"],
            )
            return {
                "candidate": result.candidate,
                "search_calls": search_calls,
                "graph_steps": step,
                "validation_issues": [],
                "repair_issues": [],
            }
        except Exception as error:  # noqa: BLE001 - preserve state at provider boundary
            issue = ValidationIssue(
                code=(
                    "search_provider_failure"
                    if isinstance(error, ProviderError)
                    else "planner_model_failure"
                ),
                message=f"Planner failed safely: {sanitize_error(error)}",
            )
            return {
                "graph_steps": step,
                "search_calls": search_calls,
                "validation_issues": [issue],
                "response_hint": "Lịch trình trước đó đã được giữ nguyên.",
            }

    def validate_candidate(self, state: PlannerState) -> dict:
        step = _step(state)
        decision = state.get("decision")
        issues = validate_candidate(
            state.get("candidate"),
            state.get("request"),
            intent=decision.intent if decision else None,
            current_plan=state.get("current_plan"),
        )
        self.trace_sink.record_event(
            "validation.candidate",
            {"issue_codes": [issue.code for issue in issues]},
            thread_id=state["thread_id"],
        )
        return {"validation_issues": issues, "graph_steps": step}

    def prepare_repair(self, state: PlannerState) -> dict:
        return {
            "repair_attempts": state.get("repair_attempts", 0) + 1,
            "repair_issues": list(state.get("validation_issues", [])),
            "graph_steps": _step(state),
        }

    def chat_respond(self, state: PlannerState) -> dict:
        step = _step(state)
        issues = list(state.get("validation_issues", []))
        decision = state.get("decision")
        candidate = state.get("candidate")
        mutates = bool(decision and decision.intent.mutates_plan)
        committed = bool(mutates and not issues and candidate and candidate.plan)
        current_plan = (
            candidate.plan if committed and candidate else state.get("current_plan")
        )
        if committed:
            status = ResponseStatus.COMMITTED
        elif issues:
            status = (
                ResponseStatus.PROVIDER_ERROR
                if any("failure" in issue.code for issue in issues)
                else ResponseStatus.REJECTED
            )
        elif decision and decision.intent.action is IntentAction.ORDINARY_CHAT:
            status = ResponseStatus.UNCHANGED
        else:
            status = ResponseStatus.NEEDS_INPUT

        metadata = _metadata(state, self.chat.role)
        try:
            message = self.chat.respond(
                message=state["message"],
                intent=decision.intent if decision else None,
                candidate=candidate if committed else None,
                committed=committed,
                current_plan=current_plan,
                issues=issues,
                response_hint=state.get("response_hint", ""),
                metadata=metadata,
            )
        except Exception:  # noqa: BLE001 - deterministic explanation fallback
            if committed:
                message = "Lịch trình tham quan đã được cập nhật sau khi kiểm tra."
            elif issues:
                message = (
                    "Chưa thể áp dụng thay đổi; lịch trình trước đó đã được giữ nguyên."
                )
            else:
                message = "Bạn muốn thay đổi điều gì trong lịch trình?"
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
            metadata={
                "thread_id": state["thread_id"],
                "turn_id": state["turn_id"],
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
