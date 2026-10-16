"""Stateless service facade for session-owned sightseeing plans."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

from grounded_travel_planner.adapters import (
    ChatOpenAIStructuredModel,
    LangSmithTraceSink,
    NoOpTraceSink,
    TavilyPlaceSearchProvider,
)
from grounded_travel_planner.agents import CoordinatorAgent, PlannerAgent
from grounded_travel_planner.config import RuntimeConfig
from grounded_travel_planner.contracts import (
    AgentResponse,
    ResponseStatus,
    SightseeingPlan,
    TripRequest,
    ValidationIssue,
)
from grounded_travel_planner.graph import build_two_agent_graph
from grounded_travel_planner.providers import TraceSink
from utils.ids import new_id
from utils.redaction import sanitize_error


class TravelPlannerService:
    """Invoke one bounded graph turn without owning cross-session application state."""

    def __init__(
        self,
        coordinator: CoordinatorAgent,
        planner: PlannerAgent,
        *,
        trace_sink: TraceSink | None = None,
        config: RuntimeConfig | None = None,
    ) -> None:
        self.config = config or RuntimeConfig()
        self.trace_sink = trace_sink or NoOpTraceSink()
        self.coordinator = coordinator
        self.planner = planner
        self.graph = build_two_agent_graph(
            coordinator,
            planner,
            self.trace_sink,
            self.config,
        )

    @classmethod
    def from_environment(
        cls,
        config: RuntimeConfig | None = None,
    ) -> TravelPlannerService:
        """Build live adapters lazily; keys never enter graph state or prompts."""

        load_dotenv()
        runtime_config = config or RuntimeConfig()
        coordinator_model = ChatOpenAIStructuredModel(runtime_config.model_name)
        planner_model = ChatOpenAIStructuredModel(runtime_config.model_name)
        search = TavilyPlaceSearchProvider()
        tracing_enabled = os.getenv("LANGSMITH_TRACING", "").casefold() in {
            "1",
            "true",
            "yes",
        }
        trace_sink: TraceSink = (
            LangSmithTraceSink(os.getenv("LANGSMITH_PROJECT"))
            if tracing_enabled and os.getenv("LANGSMITH_API_KEY")
            else NoOpTraceSink()
        )
        return cls(
            CoordinatorAgent(coordinator_model),
            PlannerAgent(planner_model, search, runtime_config),
            trace_sink=trace_sink,
            config=runtime_config,
        )

    def create_session(self) -> str:
        return new_id("thread")

    def get_graph_image(
        self, parent_path: str | os.PathLike[str] | None = None
    ) -> bytes:
        """Render the compiled workflow as PNG without invoking a graph turn.

        When ``parent_path`` is provided, LangGraph also writes ``flow.png`` to
        that directory. The returned bytes are suitable for direct UI display.
        """

        output_file_path = (
            str(Path(parent_path) / "flow.png") if parent_path is not None else None
        )
        image = self.graph.get_graph().draw_mermaid_png(
            output_file_path=output_file_path
        )
        if not image.startswith(b"\x89PNG\r\n\x1a\n"):
            raise ValueError("LangGraph did not return a valid PNG image.")
        return image

    def handle_turn(
        self,
        *,
        thread_id: str,
        message: str,
        current_plan: SightseeingPlan | None = None,
        request: TripRequest | None = None,
    ) -> AgentResponse:
        """Return the committed plan or the untouched previous plan."""

        if not thread_id.strip():
            raise ValueError("thread_id must not be blank")
        turn_id = new_id("turn")
        safe_current = current_plan.model_copy(deep=True) if current_plan else None
        self.trace_sink.record_event(
            "turn.start",
            {"turn_id": turn_id, "has_current_plan": current_plan is not None},
            thread_id=thread_id,
        )
        initial_state = {
            "thread_id": thread_id,
            "turn_id": turn_id,
            "message": message[:4000],
            "request": request,
            "current_plan": safe_current,
            "graph_steps": 0,
            "search_calls": 0,
            "repair_attempts": 0,
            "committed": False,
            "validation_issues": [],
        }
        try:
            result = self.graph.invoke(
                initial_state,
                config={
                    "recursion_limit": self.config.graph_step_limit + 2,
                    "metadata": {"thread_id": thread_id, "turn_id": turn_id},
                },
            )
            response = result.get("response")
            if isinstance(response, AgentResponse):
                return response
            return AgentResponse(
                status=ResponseStatus.PROVIDER_ERROR,
                message="Chưa nhận được phản hồi hợp lệ cho yêu cầu này.",
                current_plan=safe_current,
                validation_issues=[
                    ValidationIssue(
                        code="missing_graph_response",
                        message="The bounded graph did not return a response.",
                    )
                ],
                metadata={"thread_id": thread_id, "turn_id": turn_id},
            )
        except Exception as error:  # noqa: BLE001 - preserve canonical plan
            return AgentResponse(
                status=ResponseStatus.PROVIDER_ERROR,
                message="Chưa thể hoàn tất yêu cầu; lịch trình cũ đã được giữ nguyên.",
                current_plan=safe_current,
                validation_issues=[
                    ValidationIssue(
                        code="bounded_graph_failure",
                        message=sanitize_error(error),
                    )
                ],
                metadata={"thread_id": thread_id, "turn_id": turn_id},
            )
