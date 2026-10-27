from __future__ import annotations

from collections.abc import Callable, Mapping
from datetime import date, time
from typing import Any, TypeVar

import pytest
from pydantic import BaseModel, ValidationError

from grounded_travel_planner.adapters.model import (
    ChatOpenAIStructuredModel,
    OllamaStructuredChatModel,
)
from grounded_travel_planner.adapters.search import TavilyPlaceSearchProvider
from grounded_travel_planner.agents import ChatAgent, CoordinatorAgent, PlannerAgent
from grounded_travel_planner.config import (
    DEFAULT_CHAT_MODEL_NAME,
    DEFAULT_LIGHTWEIGHT_MODEL_NAME,
    DEFAULT_MODEL_NAME,
    RuntimeConfig,
)
from grounded_travel_planner.contracts import (
    SEARCH_SNIPPET_MAX_LENGTH,
    SOURCE_REFERENCE_SNIPPET_MAX_LENGTH,
    ChatResponse,
    ChatSearchDecision,
    CoordinatorDecision,
    IntentAction,
    PlaceRecommendation,
    PlanCandidate,
    PlanChangeIntent,
    PlannerProposal,
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
        self.prompts: list[str] = []

    def generate_structured(
        self,
        prompt: str,
        schema: type[T],
        *,
        metadata: Mapping[str, str] | None = None,
    ) -> T:
        self.calls.append(schema.__name__)
        self.prompts.append(prompt)
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
        raise AssertionError(schema)

    return ScriptedModel(handler)


def chat_model() -> ScriptedModel:
    def handler(prompt: str, schema: type[BaseModel]) -> BaseModel:
        if schema is ChatSearchDecision:
            return ChatSearchDecision(should_search=False, message="Phản hồi Chat.")
        assert schema is ChatResponse
        return ChatResponse(message="Phản hồi Chat.")

    return ScriptedModel(handler)


def planner_model(candidate_plan: SightseeingPlan) -> ScriptedModel:
    def handler(prompt: str, schema: type[BaseModel]) -> BaseModel:
        assert schema is PlannerProposal
        return PlannerProposal(plan=candidate_plan, summary="candidate")

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
    planner_llm.model_name = DEFAULT_LIGHTWEIGHT_MODEL_NAME
    chat_llm = chat_model()
    chat_llm.model_name = DEFAULT_CHAT_MODEL_NAME
    fake_search = search or FakeSearch([search_result()])
    config = RuntimeConfig()
    service = TravelPlannerService(
        CoordinatorAgent(coordinator_llm),
        PlannerAgent(planner_llm),
        ChatAgent(chat_llm),
        search=fake_search,
        trace_sink=trace,
        config=config,
    )
    return service, coordinator_llm, planner_llm, fake_search


def test_runtime_roles_use_configured_models() -> None:
    service, _, _, _ = service_for(IntentAction.CREATE_TRIP, plan())

    assert service.coordinator.role == "coordinator"
    assert service.planner.role == "planner"
    assert service.coordinator.model_name == DEFAULT_MODEL_NAME
    assert service.planner.model_name == DEFAULT_LIGHTWEIGHT_MODEL_NAME
    assert service.chat.role == "chat"
    assert service.chat.model_name == DEFAULT_CHAT_MODEL_NAME
    assert not hasattr(service.coordinator, "propose")
    assert not hasattr(service.planner, "commit")
    assert ChatOpenAIStructuredModel().model_name == "gpt-5.5"


def test_environment_service_assigns_default_models_to_all_roles() -> None:
    config = RuntimeConfig()

    service = TravelPlannerService.from_environment(config)

    assert config.model_name == DEFAULT_MODEL_NAME
    assert config.planner_model_name == DEFAULT_LIGHTWEIGHT_MODEL_NAME
    assert config.chat_model_name == DEFAULT_CHAT_MODEL_NAME
    assert service.coordinator.model_name == DEFAULT_MODEL_NAME
    assert service.planner.model_name == DEFAULT_LIGHTWEIGHT_MODEL_NAME
    assert service.chat.model_name == DEFAULT_CHAT_MODEL_NAME


def test_runtime_config_reads_openai_defaults_from_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    for name in (
        "GTP_MODEL_PROVIDER",
        "GTP_COORDINATOR_PROVIDER",
        "GTP_PLANNER_PROVIDER",
        "GTP_CHAT_PROVIDER",
        "GTP_COORDINATOR_MODEL",
        "GTP_PLANNER_MODEL",
        "GTP_CHAT_MODEL",
    ):
        monkeypatch.delenv(name, raising=False)

    config = RuntimeConfig.from_environment()

    assert config.model_provider == "openai"
    assert config.coordinator_model_provider == "openai"
    assert config.planner_model_provider == "openai"
    assert config.chat_model_provider == "openai"
    assert config.model_name == DEFAULT_MODEL_NAME
    assert config.planner_model_name == DEFAULT_LIGHTWEIGHT_MODEL_NAME
    assert config.chat_model_name == DEFAULT_CHAT_MODEL_NAME


def test_runtime_config_reads_all_role_model_overrides(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("GTP_MODEL_PROVIDER", "ollama")
    monkeypatch.setenv("GTP_COORDINATOR_MODEL", "qwen2.5:7b")
    monkeypatch.setenv("GTP_PLANNER_MODEL", "qwen2.5:3b")
    monkeypatch.setenv("GTP_CHAT_MODEL", "llama3.2:3b")

    config = RuntimeConfig.from_environment()

    assert config.model_provider == "ollama"
    assert config.model_name == "qwen2.5:7b"
    assert config.planner_model_name == "qwen2.5:3b"
    assert config.chat_model_name == "llama3.2:3b"


@pytest.mark.parametrize(
    ("name", "value", "match"),
    [
        ("GTP_MODEL_PROVIDER", "azure", "model_provider"),
        ("GTP_COORDINATOR_PROVIDER", "azure", "coordinator_provider"),
        ("GTP_PLANNER_PROVIDER", "azure", "planner_provider"),
        ("GTP_CHAT_PROVIDER", "azure", "chat_provider"),
        ("GTP_COORDINATOR_MODEL", "   ", "model name must not be blank"),
        ("GTP_PLANNER_MODEL", "", "model name must not be blank"),
        ("GTP_CHAT_MODEL", "\t", "model name must not be blank"),
    ],
)
def test_runtime_config_rejects_invalid_environment_values(
    monkeypatch: pytest.MonkeyPatch,
    name: str,
    value: str,
    match: str,
) -> None:
    monkeypatch.setenv(name, value)

    with pytest.raises(ValidationError, match=match):
        RuntimeConfig.from_environment()


def test_legacy_global_ollama_provider_selects_all_runtime_roles(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("GTP_MODEL_PROVIDER", "ollama")
    monkeypatch.setenv("GTP_COORDINATOR_PROVIDER", "")
    monkeypatch.setenv("GTP_PLANNER_PROVIDER", "")
    monkeypatch.setenv("GTP_CHAT_PROVIDER", "")
    monkeypatch.setenv("GTP_COORDINATOR_MODEL", "qwen2.5:7b")
    monkeypatch.setenv("GTP_PLANNER_MODEL", "qwen2.5:3b")
    monkeypatch.setenv("GTP_CHAT_MODEL", "llama3.2:3b")
    monkeypatch.setenv("OLLAMA_BASE_URL", "http://ollama.test:11434")

    service = TravelPlannerService.from_environment()

    assert isinstance(service.coordinator._model, OllamaStructuredChatModel)
    assert isinstance(service.planner._model, OllamaStructuredChatModel)
    assert isinstance(service.chat._model, OllamaStructuredChatModel)
    assert [
        service.coordinator.model_name,
        service.planner.model_name,
        service.chat.model_name,
    ] == ["qwen2.5:7b", "qwen2.5:3b", "llama3.2:3b"]
    assert service.coordinator._model._base_url == "http://ollama.test:11434"


def test_role_provider_overrides_take_precedence_over_global_fallback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("GTP_MODEL_PROVIDER", "ollama")
    monkeypatch.setenv("GTP_COORDINATOR_PROVIDER", "openai")
    monkeypatch.setenv("GTP_PLANNER_PROVIDER", "ollama")
    monkeypatch.setenv("GTP_CHAT_PROVIDER", "openai")

    config = RuntimeConfig.from_environment()

    assert config.model_provider == "ollama"
    assert config.coordinator_model_provider == "openai"
    assert config.planner_model_provider == "ollama"
    assert config.chat_model_provider == "openai"


def test_blank_role_provider_override_uses_global_fallback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("GTP_MODEL_PROVIDER", "ollama")
    monkeypatch.setenv("GTP_COORDINATOR_PROVIDER", "")
    monkeypatch.setenv("GTP_PLANNER_PROVIDER", "   ")
    monkeypatch.setenv("GTP_CHAT_PROVIDER", "\t")

    config = RuntimeConfig.from_environment()

    assert config.coordinator_provider is None
    assert config.planner_provider is None
    assert config.chat_provider is None
    assert config.coordinator_model_provider == "ollama"
    assert config.planner_model_provider == "ollama"
    assert config.chat_model_provider == "ollama"


def test_environment_service_constructs_exact_mixed_role_adapters(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    constructed: list[tuple[str, str, str | None]] = []

    class FakeOpenAIModel:
        def __init__(self, model_name: str) -> None:
            self._model_name = model_name
            constructed.append(("openai", model_name, None))

        @property
        def model_name(self) -> str:
            return self._model_name

    class FakeOllamaModel:
        def __init__(self, model_name: str, base_url: str | None = None) -> None:
            self._model_name = model_name
            constructed.append(("ollama", model_name, base_url))

        @property
        def model_name(self) -> str:
            return self._model_name

    monkeypatch.setattr(
        "grounded_travel_planner.service.ChatOpenAIStructuredModel", FakeOpenAIModel
    )
    monkeypatch.setattr(
        "grounded_travel_planner.service.OllamaStructuredChatModel", FakeOllamaModel
    )
    monkeypatch.setenv("GTP_MODEL_PROVIDER", "openai")
    monkeypatch.setenv("GTP_COORDINATOR_PROVIDER", "openai")
    monkeypatch.setenv("GTP_PLANNER_PROVIDER", "ollama")
    monkeypatch.setenv("GTP_CHAT_PROVIDER", "ollama")
    monkeypatch.setenv("GTP_COORDINATOR_MODEL", "gpt-5.5")
    monkeypatch.setenv("GTP_PLANNER_MODEL", "qwen2.5:3b")
    monkeypatch.setenv("GTP_CHAT_MODEL", "qwen2.5:3b")
    monkeypatch.setenv("OLLAMA_BASE_URL", "http://ollama.test:11434")

    service = TravelPlannerService.from_environment()

    assert constructed == [
        ("openai", "gpt-5.5", None),
        ("ollama", "qwen2.5:3b", "http://ollama.test:11434"),
        ("ollama", "qwen2.5:3b", "http://ollama.test:11434"),
        ("ollama", "qwen2.5:3b", "http://ollama.test:11434"),
    ]
    assert isinstance(service.coordinator._model._primary, FakeOpenAIModel)
    assert isinstance(service.coordinator._model._fallback, FakeOllamaModel)
    assert isinstance(service.planner._model, FakeOllamaModel)
    assert isinstance(service.chat._model, FakeOllamaModel)


def test_openai_adapter_uses_function_calling_for_pydantic_schema(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    observed: dict[str, object] = {}

    class FakeChatOpenAI:
        def __init__(
            self,
            *,
            model: str,
            max_retries: int,
            timeout: int,
        ) -> None:
            observed["model"] = model
            observed["max_retries"] = max_retries
            observed["timeout"] = timeout

        def with_structured_output(self, schema, *, method: str):
            observed["schema"] = schema
            observed["method"] = method
            return self

        def invoke(self, messages, config):
            observed["metadata"] = config["metadata"]
            return ChatResponse(message="ok")

    monkeypatch.setattr("langchain_openai.ChatOpenAI", FakeChatOpenAI)
    adapter = ChatOpenAIStructuredModel()

    result = adapter.generate_structured(
        "explain",
        ChatResponse,
        metadata={"thread_id": "thread-adapter"},
    )

    assert result.message == "ok"
    assert observed == {
        "model": "gpt-5.5",
        "max_retries": 0,
        "timeout": 20,
        "schema": ChatResponse,
        "method": "function_calling",
        "metadata": {"thread_id": "thread-adapter"},
    }


def test_terra_adapter_uses_json_schema_without_reasoning(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    observed: dict[str, object] = {}

    class FakeChatOpenAI:
        def __init__(self, **kwargs: object) -> None:
            observed.update(kwargs)

        def with_structured_output(self, schema, *, method: str):
            observed["schema"] = schema
            observed["method"] = method
            return self

        def invoke(self, messages, config):
            return ChatResponse(message="ok")

    monkeypatch.setattr("langchain_openai.ChatOpenAI", FakeChatOpenAI)

    result = ChatOpenAIStructuredModel("gpt-6.1-terra").generate_structured(
        "explain", ChatResponse
    )

    assert result.message == "ok"
    assert observed == {
        "model": "gpt-6.1-terra",
        "max_retries": 0,
        "timeout": 20,
        "reasoning_effort": "none",
        "schema": ChatResponse,
        "method": "json_schema",
    }


def test_ollama_adapter_uses_structured_output_without_network(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    observed: dict[str, object] = {}

    class FakeChatOllama:
        def __init__(self, *, model: str, base_url: str) -> None:
            observed["model"] = model
            observed["base_url"] = base_url

        def with_structured_output(self, schema):
            observed["schema"] = schema
            return self

        def invoke(self, messages, config):
            observed["messages"] = messages
            observed["metadata"] = config["metadata"]
            return ChatResponse(message="ok")

    monkeypatch.setattr("langchain_ollama.ChatOllama", FakeChatOllama)
    adapter = OllamaStructuredChatModel("qwen2.5:3b", "http://localhost:11434")

    result = adapter.generate_structured(
        "explain",
        ChatResponse,
        metadata={"thread_id": "thread-adapter"},
    )

    assert result.message == "ok"
    assert observed["model"] == "qwen2.5:3b"
    assert observed["base_url"] == "http://localhost:11434"
    assert observed["schema"] is ChatResponse
    assert observed["metadata"] == {"thread_id": "thread-adapter"}
    assert [message.content for message in observed["messages"]] == [
        (
            "You are a bounded travel-planner runtime component. Return only "
            "the requested structured output. Do not include secrets, API keys, "
            "or unsupported claims."
        ),
        "explain",
    ]


def test_ordinary_chat_does_not_search_or_mutate_plan() -> None:
    existing = plan()
    original = existing.model_copy(deep=True)
    service, coordinator_llm, planner_llm, search = service_for(
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
    assert coordinator_llm.calls == ["CoordinatorDecision"]
    assert response.metadata["chat_role"] == "chat"
    assert response.metadata["chat_model"] == DEFAULT_CHAT_MODEL_NAME
    assert "User message: Thanks, that looks good." in service.chat._model.prompts[0]


def test_trip_extension_resolves_request_and_commits_new_day() -> None:
    current = plan()
    pagoda_source = source(
        title="Thien Mu Pagoda Hue visitor guide",
        url="https://travel.example/hue/thien-mu-pagoda",
        snippet="Thien Mu Pagoda Hue visitor information.",
    )
    new_entry = current.entries[0].model_copy(
        update={
            "id": "entry_day_3",
            "day_index": 3,
            "place": current.entries[0].place.model_copy(
                update={
                    "place_id": "place_day_3",
                    "name": "Thien Mu Pagoda",
                    "source_references": [pagoda_source],
                }
            ),
        }
    )
    candidate_plan = current.model_copy(
        update={"entries": [*current.entries, new_entry], "day_count": 3}
    )

    def extension_coordinator(prompt: str, schema: type[BaseModel]) -> BaseModel:
        assert schema is CoordinatorDecision
        return CoordinatorDecision(
            intent=PlanChangeIntent(
                action=IntentAction.EXTEND_TRIP,
                day_count_delta=1,
            ),
            requires_planner=True,
        )

    observed_prompts: list[str] = []

    def extension_planner(prompt: str, schema: type[BaseModel]) -> BaseModel:
        assert schema is PlannerProposal
        observed_prompts.append(prompt)
        return PlannerProposal(plan=candidate_plan, summary="Ngày thứ ba đã được thêm.")

    search = FakeSearch(
        [
            SearchResult(
                source_id=pagoda_source.source_id,
                title=pagoda_source.title,
                url=pagoda_source.url,
                snippet=pagoda_source.snippet,
                score=0.95,
            )
        ]
    )

    service = TravelPlannerService(
        CoordinatorAgent(ScriptedModel(extension_coordinator)),
        PlannerAgent(ScriptedModel(extension_planner)),
        ChatAgent(chat_model()),
        search=search,
        config=RuntimeConfig(),
    )

    response = service.handle_turn(
        thread_id="thread-extend",
        message="thêm một ngày",
        current_plan=current,
    )

    assert response.status is ResponseStatus.COMMITTED
    assert response.committed is True
    assert response.current_plan is not None
    assert response.current_plan.day_count == 3
    assert response.current_plan.revision == 2
    assert any(entry.day_index == 3 for entry in response.current_plan.entries)
    assert response.search_calls == 1
    assert len(search.calls) == 1
    assert '"day_count":3' in observed_prompts[0]
    assert "entry_day_out_of_range" not in {
        issue.code for issue in response.validation_issues
    }
    chat_prompt = service.chat._model.prompts[0]
    assert "Planner summary: Ngày thứ ba đã được thêm." in chat_prompt
    assert "Current visible itinerary:" in chat_prompt


def test_trip_extension_over_seven_rejects_before_planner_or_search() -> None:
    current = plan().model_copy(update={"day_count": 7})

    def extension_coordinator(prompt: str, schema: type[BaseModel]) -> BaseModel:
        assert schema is CoordinatorDecision
        return CoordinatorDecision(
            intent=PlanChangeIntent(
                action=IntentAction.EXTEND_TRIP,
                day_count_delta=1,
            ),
            requires_planner=True,
        )

    planner_llm = planner_model(plan())
    search = FakeSearch([search_result()])
    service = TravelPlannerService(
        CoordinatorAgent(ScriptedModel(extension_coordinator)),
        PlannerAgent(planner_llm),
        ChatAgent(chat_model()),
        search=search,
        config=RuntimeConfig(),
    )

    response = service.handle_turn(
        thread_id="thread-extend-over-limit",
        message="thêm một ngày",
        current_plan=current,
    )

    assert response.status is ResponseStatus.REJECTED
    assert response.current_plan == current
    assert planner_llm.calls == []
    assert search.calls == []
    assert "day_count_out_of_range" in {
        issue.code for issue in response.validation_issues
    }


@pytest.mark.parametrize(
    "intent, expected_code",
    [
        (
            PlanChangeIntent(action=IntentAction.EXTEND_TRIP),
            "trip_extension_target_required",
        ),
        (
            PlanChangeIntent(action=IntentAction.EXTEND_TRIP, day_count=2),
            "trip_extension_must_increase",
        ),
    ],
)
def test_invalid_trip_extension_rejects_before_planner_or_search(
    intent: PlanChangeIntent, expected_code: str
) -> None:
    def extension_coordinator(prompt: str, schema: type[BaseModel]) -> BaseModel:
        assert schema is CoordinatorDecision
        return CoordinatorDecision(intent=intent, requires_planner=True)

    planner_llm = planner_model(plan())
    search = FakeSearch([search_result()])
    service = TravelPlannerService(
        CoordinatorAgent(ScriptedModel(extension_coordinator)),
        PlannerAgent(planner_llm),
        ChatAgent(chat_model()),
        search=search,
        config=RuntimeConfig(),
    )

    response = service.handle_turn(
        thread_id=f"thread-extend-{expected_code}",
        message="thêm ngày",
        current_plan=plan(),
    )

    assert response.status is ResponseStatus.REJECTED
    assert planner_llm.calls == []
    assert search.calls == []
    assert expected_code in {issue.code for issue in response.validation_issues}


def test_trip_extension_rejects_changed_existing_entry() -> None:
    current = plan()
    changed_existing = current.entries[0].model_copy(update={"start_time": time(11)})
    candidate = current.model_copy(
        update={
            "day_count": 3,
            "entries": [
                changed_existing,
                current.entries[0].model_copy(
                    update={"id": "entry_day_3", "day_index": 3}
                ),
            ],
        }
    )

    issues = validate_requested_change(
        PlanChangeIntent(action=IntentAction.EXTEND_TRIP, day_count_delta=1),
        current,
        candidate,
    )

    assert issues[0].code == "requested_change_not_applied"


def test_trip_extension_requires_a_stop_on_each_added_day() -> None:
    current = plan()
    candidate = current.model_copy(
        update={
            "day_count": 4,
            "entries": [
                *current.entries,
                current.entries[0].model_copy(
                    update={"id": "entry_day_4", "day_index": 4}
                ),
            ],
        }
    )

    issues = validate_requested_change(
        PlanChangeIntent(action=IntentAction.EXTEND_TRIP, day_count=4),
        current,
        candidate,
    )

    assert issues[0].code == "requested_change_not_applied"


def test_trip_shortening_preserves_retained_stops_and_source_data() -> None:
    current = plan().model_copy(
        update={
            "day_count": 3,
            "entries": [
                *plan().entries,
                plan()
                .entries[0]
                .model_copy(update={"id": "entry_day_3", "day_index": 3}),
            ],
        }
    )
    intent = PlanChangeIntent(action=IntentAction.SHORTEN_TRIP, day_count_delta=1)
    valid = current.model_copy(update={"day_count": 2, "entries": current.entries[:1]})
    changed = valid.model_copy(
        update={
            "entries": [current.entries[0].model_copy(update={"start_time": time(11)})]
        }
    )
    invented = valid.model_copy(
        update={
            "entries": [
                *valid.entries,
                current.entries[1].model_copy(
                    update={"id": "invented", "day_index": 2}
                ),
            ]
        }
    )

    assert validate_requested_change(intent, current, valid) == []
    assert validate_requested_change(intent, current, changed)[0].code == (
        "requested_change_not_applied"
    )
    assert validate_requested_change(intent, current, invented)[0].code == (
        "requested_change_not_applied"
    )


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

    def broken_chat(prompt: str, schema: type[BaseModel]) -> BaseModel:
        raise RuntimeError("simulated chat failure")

    search = FakeSearch([])
    config = RuntimeConfig()
    service = TravelPlannerService(
        CoordinatorAgent(ScriptedModel(coordinator_handler)),
        PlannerAgent(ScriptedModel(lambda prompt, schema: PlannerProposal())),
        ChatAgent(ScriptedModel(broken_chat)),
        search=search,
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
    assert "lịch trình trước đó vẫn được giữ nguyên" in response.message
    assert search.calls == []
    assert "Understand requests in Vietnamese or English" in prompts[0]
    assert len(prompts) == 1


@pytest.mark.parametrize("language", ["vi", "en"])
def test_invalid_model_key_preserves_plan_without_retrying_chat(language: str) -> None:
    class InvalidKeyError(Exception):
        status_code = 401

    def coordinator_failure(prompt: str, schema: type[BaseModel]) -> BaseModel:
        raise InvalidKeyError("token_invalidated")

    def unexpected_model_call(prompt: str, schema: type[BaseModel]) -> BaseModel:
        raise AssertionError("Planner and Chat must not be called after auth failure")

    coordinator_llm = ScriptedModel(coordinator_failure)
    planner_llm = ScriptedModel(unexpected_model_call)
    chat_llm = ScriptedModel(unexpected_model_call)
    search = FakeSearch([search_result()])
    service = TravelPlannerService(
        CoordinatorAgent(coordinator_llm),
        PlannerAgent(planner_llm),
        ChatAgent(chat_llm),
        search=search,
        config=RuntimeConfig(),
    )
    current = plan()

    response = service.handle_turn(
        thread_id=f"invalid-key-{language}",
        message="Hãy tạo lịch trình tham quan 2 ngày tại Hà Giang, bắt đầu ngày 2026-10-26.",
        current_plan=current,
        language=language,
    )

    assert response.status is ResponseStatus.PROVIDER_ERROR
    assert response.current_plan == current
    assert response.committed is False
    assert [issue.code for issue in response.validation_issues] == [
        "model_authentication_failure"
    ]
    assert ("Khóa API" if language == "vi" else "API key") in response.message
    assert "token_invalidated" not in response.message
    assert coordinator_llm.calls == ["CoordinatorDecision"]
    assert planner_llm.calls == chat_llm.calls == search.calls == []


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
        "coordinator.route",
        "planner.propose",
        "validation.candidate",
        "chat.respond",
    }


@pytest.mark.parametrize(
    "invalid_plan", [pytest.param({}, id="omitted"), {"plan": None}]
)
@pytest.mark.parametrize(
    ("action", "has_current_plan", "expected_search_calls"),
    [
        pytest.param(IntentAction.CHANGE_TIME, True, 0, id="edit"),
        pytest.param(IntentAction.CREATE_TRIP, False, 1, id="create"),
    ],
)
def test_missing_planner_plan_is_a_model_failure_without_retry(
    invalid_plan: dict[str, object],
    action: IntentAction,
    has_current_plan: bool,
    expected_search_calls: int,
) -> None:
    """Reject malformed Planner output at the provider boundary.

    An edit retains its committed itinerary without invoking search. A create
    may complete its single required search before the invalid model payload is
    detected, but must not enter candidate validation or retry planning.
    """

    def malformed_planner(
        prompt: str, schema: type[BaseModel]
    ) -> BaseModel | dict[str, object]:
        assert schema is PlannerProposal
        return invalid_plan

    current = plan() if has_current_plan else None
    config = RuntimeConfig()
    planner_llm = ScriptedModel(malformed_planner)
    search = FakeSearch([search_result()])
    service = TravelPlannerService(
        CoordinatorAgent(coordinator_model(action)),
        PlannerAgent(planner_llm),
        ChatAgent(chat_model()),
        search=search,
        config=config,
    )

    response = service.handle_turn(
        thread_id=f"thread-missing-plan-{action.value}",
        message="Update this itinerary.",
        request=(
            None
            if current is not None
            else TripRequest(
                destination="Hue",
                start_date=date(2026, 11, 1),
                day_count=2,
            )
        ),
        current_plan=current,
    )

    assert response.status is ResponseStatus.PROVIDER_ERROR
    assert response.committed is False
    assert response.current_plan == current
    assert {issue.code for issue in response.validation_issues} == {
        "planner_model_failure"
    }
    assert "candidate_required" not in {
        issue.code for issue in response.validation_issues
    }
    assert planner_llm.calls == ["PlannerProposal"]
    assert response.repair_attempts == 0
    assert response.search_calls == expected_search_calls
    assert len(search.calls) == expected_search_calls


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
    assert response.graph_steps <= 8
    assert planner_llm.calls.count("PlannerProposal") == 2
    assert search.calls == []
    chat_prompt = service.chat._model.prompts[0]
    assert "overlap on day 1" in chat_prompt
    assert "Current visible itinerary:" in chat_prompt
    assert "Planner summary: " in chat_prompt
    assert '"id":"entry_2"' not in chat_prompt
    assert '"revision":2' not in chat_prompt


def test_source_provenance_and_opening_hours_claims_are_rejected() -> None:
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
    assert "source_place_mismatch" not in codes
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
        assert schema is PlannerProposal
        planner_prompts.append(prompt)
        return PlannerProposal(plan=candidate_plan, summary="candidate")

    config = RuntimeConfig()
    search = FakeSearch([search_result()])
    service = TravelPlannerService(
        CoordinatorAgent(coordinator_model(IntentAction.CREATE_TRIP)),
        PlannerAgent(ScriptedModel(planner_handler)),
        ChatAgent(chat_model()),
        search=search,
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
        assert schema is PlannerProposal
        return PlannerProposal(
            plan=candidate_plan,
            issues=[
                ValidationIssue(
                    code="opening_hours_unverified",
                    message="Returned sources do not substantiate opening hours.",
                )
            ],
        )

    config = RuntimeConfig()
    search = FakeSearch([search_result()])
    service = TravelPlannerService(
        CoordinatorAgent(coordinator_model(IntentAction.CREATE_TRIP)),
        PlannerAgent(ScriptedModel(planner_handler)),
        ChatAgent(chat_model()),
        search=search,
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


def test_planner_ignores_untrusted_model_sources_before_validation() -> None:
    trusted = search_result()
    candidate_plan = plan()
    untrusted = source(
        title="Injected source",
        url="https://injected.example/hue",
        snippet="x" * (SEARCH_SNIPPET_MAX_LENGTH + 1),
    )

    def planner_handler(prompt: str, schema: type[BaseModel]) -> BaseModel:
        assert schema is PlannerProposal
        payload = {
            "plan": candidate_plan.model_dump(mode="json"),
            "summary": "candidate",
            "returned_sources": [untrusted.model_dump(mode="json")],
        }
        return schema.model_validate(payload)

    planner = PlannerAgent(ScriptedModel(planner_handler))
    result = planner.propose(
        intent=PlanChangeIntent(action=IntentAction.CREATE_TRIP),
        request=TripRequest(
            destination="Hue",
            start_date=date(2026, 11, 1),
            day_count=2,
        ),
        current_plan=None,
        metadata={"thread_id": "thread-untrusted-source"},
        retained_sources=[
            SourceReference(
                source_id=trusted.source_id,
                title=trusted.title,
                url=trusted.url,
                snippet=trusted.snippet,
                retrieval_query="attractions Hue sightseeing official visitor information",
                supports_opening_hours=trusted.supports_opening_hours,
            )
        ],
    )

    assert result.returned_sources == [
        SourceReference(
            source_id=trusted.source_id,
            title=trusted.title,
            url=trusted.url,
            snippet=trusted.snippet,
            retrieval_query="attractions Hue sightseeing official visitor information",
            supports_opening_hours=trusted.supports_opening_hours,
        )
    ]
    assert result.returned_source_urls == {str(trusted.url)}
    assert result.plan.entries[0].place.source_references == [
        result.returned_sources[0]
    ]
    assert "returned_sources" not in PlannerProposal.model_json_schema()["properties"]


def test_source_reference_accepts_four_thousand_character_snippet() -> None:
    source_with_long_snippet = SourceReference.model_validate(
        {
            "source_id": "source_long",
            "title": "Long source",
            "url": "https://travel.example/long",
            "snippet": "x" * SOURCE_REFERENCE_SNIPPET_MAX_LENGTH,
        }
    )

    assert (
        len(source_with_long_snippet.snippet or "")
        == SOURCE_REFERENCE_SNIPPET_MAX_LENGTH
    )
    with pytest.raises(ValueError):
        SourceReference.model_validate(
            {
                "source_id": "source_too_long",
                "title": "Too long source",
                "url": "https://travel.example/too-long",
                "snippet": "x" * (SOURCE_REFERENCE_SNIPPET_MAX_LENGTH + 1),
            }
        )


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
        PlannerAgent(planner_llm),
        ChatAgent(chat_model()),
        search=FakeSearch([search_result()]),
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
    assert len(results[0].snippet) == SEARCH_SNIPPET_MAX_LENGTH
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
        return ChatResponse(message="Added the place.")

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
        PlannerAgent(planner_model(candidate_plan)),
        ChatAgent(chat_model()),
        search=search,
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
