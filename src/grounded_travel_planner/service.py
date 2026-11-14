"""Stateless service facade for session-owned sightseeing plans."""

from __future__ import annotations

import os

from dotenv import load_dotenv

from grounded_travel_planner.adapters import (
    ChatOpenAIStructuredModel,
    LangSmithTraceSink,
    NoOpTraceSink,
    OllamaStructuredChatModel,
    OpenAIWithOllamaFallbackStructuredModel,
    TavilyPlaceSearchProvider,
)
from grounded_travel_planner.agents import ChatAgent, CoordinatorAgent, PlannerAgent
from grounded_travel_planner.config import ModelProvider, RuntimeConfig
from grounded_travel_planner.contracts import (
    AgentResponse,
    ConversationTurn,
    ResponseStatus,
    SightseeingPlan,
    TripRequest,
    ValidationIssue,
)
from grounded_travel_planner.conversation import bounded_history, bounded_summary
from grounded_travel_planner.graph import build_travel_planner_graph
from grounded_travel_planner.i18n import Language, localized
from grounded_travel_planner.providers import PlaceSearchProvider, TraceSink
from grounded_travel_planner.usage import current_account_trace_ref
from utils.ids import new_id
from utils.redaction import sanitize_error


def _required_model_name(value: str | None, environment_name: str) -> str:
    if value is None or not value.strip():
        raise ValueError(f"{environment_name} must be configured")
    return value.strip()


class TravelPlannerService:
    """Invoke one bounded graph turn without owning cross-session application state."""

    def __init__(
        self,
        coordinator: CoordinatorAgent,
        planner: PlannerAgent,
        chat: ChatAgent,
        *,
        search: PlaceSearchProvider,
        trace_sink: TraceSink | None = None,
        config: RuntimeConfig | None = None,
    ) -> None:
        self.config = config or RuntimeConfig()
        self.trace_sink = trace_sink or NoOpTraceSink()
        self.coordinator = coordinator
        self.planner = planner
        self.chat = chat
        self.graph = build_travel_planner_graph(
            coordinator,
            planner,
            chat,
            search,
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
        runtime_config = config or RuntimeConfig.from_environment()
        coordinator_name = _required_model_name(
            runtime_config.model_name, "GTP_COORDINATOR_MODEL"
        )
        planner_name = _required_model_name(
            runtime_config.planner_model_name, "GTP_PLANNER_MODEL"
        )
        chat_name = _required_model_name(
            runtime_config.chat_model_name, "GTP_CHAT_MODEL"
        )
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
        coordinator_model = cls._model_factory(
            runtime_config.coordinator_model_provider,
            ollama_fallback_model_name=runtime_config.coordinator_ollama_fallback_model,
            json_schema_model_names=runtime_config.openai_json_schema_model_names,
            max_completion_tokens=runtime_config.coordinator_max_output_tokens,
            trace_sink=trace_sink,
            role="coordinator",
        )(coordinator_name)
        planner_model = cls._model_factory(
            runtime_config.planner_model_provider,
            ollama_fallback_model_name=runtime_config.planner_ollama_fallback_model,
            json_schema_model_names=runtime_config.openai_json_schema_model_names,
            max_completion_tokens=runtime_config.planner_max_output_tokens,
            trace_sink=trace_sink,
            role="planner",
        )(planner_name)
        chat_model = cls._model_factory(
            runtime_config.chat_model_provider,
            ollama_fallback_model_name=runtime_config.chat_ollama_fallback_model,
            json_schema_model_names=runtime_config.openai_json_schema_model_names,
            max_completion_tokens=runtime_config.chat_max_output_tokens,
            trace_sink=trace_sink,
            role="chat",
        )(chat_name)
        search = TavilyPlaceSearchProvider()
        return cls(
            CoordinatorAgent(coordinator_model),
            PlannerAgent(planner_model),
            ChatAgent(chat_model),
            search=search,
            trace_sink=trace_sink,
            config=runtime_config,
        )

    @staticmethod
    def _model_factory(
        provider: ModelProvider,
        *,
        ollama_fallback_model_name: str | None = None,
        json_schema_model_names: tuple[str, ...] = (),
        max_completion_tokens: int = 2048,
        trace_sink: TraceSink | None = None,
        role: str = "unknown",
    ):
        """Return a selected provider constructor with bounded OpenAI fallback."""

        if provider == "openai":

            def create_openai(model_name: str) -> ChatOpenAIStructuredModel:
                return ChatOpenAIStructuredModel(
                    model_name,
                    json_schema_model_names=json_schema_model_names,
                    max_completion_tokens=max_completion_tokens,
                    trace_sink=trace_sink,
                    role=role,
                )

            if not ollama_fallback_model_name:
                return create_openai
            base_url = os.getenv("OLLAMA_BASE_URL", "").strip() or None

            def create_fallback_openai(
                model_name: str,
            ) -> OpenAIWithOllamaFallbackStructuredModel:
                return OpenAIWithOllamaFallbackStructuredModel(
                    create_openai(model_name),
                    OllamaStructuredChatModel(
                        ollama_fallback_model_name,
                        base_url=base_url,
                        max_completion_tokens=max_completion_tokens,
                    ),
                )

            return create_fallback_openai
        if provider == "ollama":
            base_url = os.getenv("OLLAMA_BASE_URL", "").strip() or None

            def create_ollama(model_name: str) -> OllamaStructuredChatModel:
                return OllamaStructuredChatModel(
                    model_name,
                    base_url=base_url,
                    max_completion_tokens=max_completion_tokens,
                )

            return create_ollama
        raise ValueError(f"Unsupported model provider: {provider}")

    def create_session(self) -> str:
        return new_id("thread")

    def handle_turn(
        self,
        *,
        thread_id: str,
        message: str,
        current_plan: SightseeingPlan | None = None,
        request: TripRequest | None = None,
        session_summary: str = "",
        conversation_history: list[ConversationTurn] | None = None,
        language: Language = "vi",
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
            "language": language,
            "request": request,
            "current_plan": safe_current,
            "session_summary": bounded_summary(session_summary),
            "conversation_history": bounded_history(conversation_history or []),
            "graph_steps": 0,
            "search_calls": 0,
            "repair_attempts": 0,
            "committed": False,
            "validation_issues": [],
        }
        try:
            trace_metadata = {"thread_id": thread_id, "turn_id": turn_id}
            account_ref = current_account_trace_ref()
            if account_ref:
                trace_metadata["account_ref"] = account_ref
            result = self.graph.invoke(
                initial_state,
                config={
                    "recursion_limit": self.config.graph_step_limit + 2,
                    "metadata": trace_metadata,
                },
            )
            response = result.get("response")
            if isinstance(response, AgentResponse):
                return response
            return AgentResponse(
                status=ResponseStatus.PROVIDER_ERROR,
                message=localized("missing_graph_response", language),
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
                message=localized("graph_failure", language),
                current_plan=safe_current,
                validation_issues=[
                    ValidationIssue(
                        code="bounded_graph_failure",
                        message=sanitize_error(error),
                    )
                ],
                metadata={"thread_id": thread_id, "turn_id": turn_id},
            )
