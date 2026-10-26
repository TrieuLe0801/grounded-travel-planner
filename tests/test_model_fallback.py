"""Offline contracts for bounded OpenAI-to-Ollama model fallback."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date, time
from typing import TypeVar

import httpx
import pytest
from openai import (
    APIConnectionError,
    APIStatusError,
    APITimeoutError,
    AuthenticationError,
    InternalServerError,
    OpenAIError,
    RateLimitError,
)
from pydantic import BaseModel, ValidationError

from grounded_travel_planner.adapters.model import (
    OllamaStructuredChatModel,
    OpenAIWithOllamaFallbackStructuredModel,
)
from grounded_travel_planner.agents import ChatAgent, CoordinatorAgent, PlannerAgent
from grounded_travel_planner.config import RuntimeConfig
from grounded_travel_planner.contracts import (
    PlaceRecommendation,
    ResponseStatus,
    ScheduleEntry,
    SightseeingPlan,
    SourceReference,
)
from grounded_travel_planner.service import TravelPlannerService

T = TypeVar("T", bound=BaseModel)


class _Result(BaseModel):
    value: str


class _RecordingModel:
    def __init__(self, model_name: str, result: BaseModel | Exception) -> None:
        self.model_name = model_name
        self._result = result
        self.calls: list[tuple[str, type[BaseModel], Mapping[str, str] | None]] = []

    def generate_structured(
        self,
        prompt: str,
        schema: type[T],
        *,
        metadata: Mapping[str, str] | None = None,
    ) -> T:
        self.calls.append((prompt, schema, metadata))
        if isinstance(self._result, Exception):
            raise self._result
        return schema.model_validate(self._result)


def _request() -> httpx.Request:
    return httpx.Request("POST", "https://api.openai.com/v1/responses")


def _status_error(status_code: int) -> APIStatusError:
    request = _request()
    return APIStatusError(
        "OpenAI unavailable",
        response=httpx.Response(status_code, request=request),
        body=None,
    )


def _authentication_error() -> AuthenticationError:
    request = _request()
    return AuthenticationError(
        "invalid key",
        response=httpx.Response(401, request=request),
        body=None,
    )


def test_successful_openai_response_does_not_call_ollama(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "configured-key")
    primary = _RecordingModel("gpt-test", _Result(value="remote answer"))
    fallback = _RecordingModel("qwen-test", _Result(value="local answer"))

    result = OpenAIWithOllamaFallbackStructuredModel(
        primary, fallback
    ).generate_structured("prompt", _Result, metadata={"thread_id": "thread-ok"})

    assert result.value == "remote answer"
    assert len(primary.calls) == 1
    assert fallback.calls == []


@pytest.mark.parametrize(
    "error",
    [
        _authentication_error(),
        RateLimitError(
            "rate limited",
            response=httpx.Response(429, request=_request()),
            body=None,
        ),
        InternalServerError(
            "server error",
            response=httpx.Response(500, request=_request()),
            body=None,
        ),
        APIConnectionError(request=_request()),
        APITimeoutError(request=_request()),
        _status_error(403),
        _status_error(408),
        _status_error(503),
    ],
    ids=["401", "429", "500", "connection", "timeout", "403", "408", "503"],
)
def test_openai_availability_errors_retry_once_on_ollama(
    monkeypatch: pytest.MonkeyPatch, error: Exception
) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "configured-key")
    primary = _RecordingModel("gpt-test", error)
    fallback = _RecordingModel("qwen-test", _Result(value="local answer"))
    model = OpenAIWithOllamaFallbackStructuredModel(primary, fallback)
    metadata = {"thread_id": "thread-fallback", "turn_id": "turn-fallback"}

    result = model.generate_structured("same prompt", _Result, metadata=metadata)

    assert result == _Result(value="local answer")
    assert model.model_name == "gpt-test"
    assert primary.calls == [("same prompt", _Result, metadata)]
    assert fallback.calls == [("same prompt", _Result, metadata)]


def test_missing_openai_key_uses_ollama_after_one_primary_attempt(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    primary = _RecordingModel("gpt-test", OpenAIError("api key missing"))
    fallback = _RecordingModel("qwen-test", _Result(value="local answer"))

    result = OpenAIWithOllamaFallbackStructuredModel(
        primary, fallback
    ).generate_structured("prompt", _Result, metadata={"thread_id": "thread-key"})

    assert result.value == "local answer"
    assert len(primary.calls) == len(fallback.calls) == 1
    assert primary.calls[0] == fallback.calls[0]


@pytest.mark.parametrize(
    "error",
    [
        ValidationError.from_exception_data(
            _Result.__name__,
            [{"type": "missing", "loc": ("value",), "input": {}}],
        ),
        RuntimeError("programming error"),
        _status_error(400),
    ],
    ids=["schema-validation", "programming", "openai-400"],
)
def test_non_availability_failures_do_not_call_ollama(
    monkeypatch: pytest.MonkeyPatch, error: Exception
) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "configured-key")
    primary = _RecordingModel("gpt-test", error)
    fallback = _RecordingModel("qwen-test", _Result(value="must not be used"))
    model = OpenAIWithOllamaFallbackStructuredModel(primary, fallback)

    with pytest.raises(type(error)):
        model.generate_structured("prompt", _Result)

    assert len(primary.calls) == 1
    assert fallback.calls == []


def test_explicit_ollama_selection_does_not_wrap_or_create_openai() -> None:
    factory = TravelPlannerService._model_factory(
        "ollama", ollama_fallback_model_name="qwen-fallback"
    )

    model = factory("qwen-selected")

    assert isinstance(model, OllamaStructuredChatModel)
    assert model.model_name == "qwen-selected"


def test_role_fallback_names_override_global_name(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("GTP_OLLAMA_FALLBACK_MODEL", "qwen-global")
    monkeypatch.setenv("GTP_COORDINATOR_OLLAMA_FALLBACK_MODEL", "qwen-coordinator")
    monkeypatch.setenv("GTP_PLANNER_OLLAMA_FALLBACK_MODEL", "qwen-planner")
    monkeypatch.setenv("GTP_CHAT_OLLAMA_FALLBACK_MODEL", "qwen-chat")

    config = RuntimeConfig.from_environment()

    assert config.coordinator_ollama_fallback_model == "qwen-coordinator"
    assert config.planner_ollama_fallback_model == "qwen-planner"
    assert config.chat_ollama_fallback_model == "qwen-chat"


def _existing_plan() -> SightseeingPlan:
    source = SourceReference(
        source_id="source-existing",
        title="Existing source",
        url="https://example.test/existing",
    )
    place = PlaceRecommendation(
        place_id="place-existing",
        name="Existing Place",
        description="An already grounded place.",
        source_references=[source],
    )
    return SightseeingPlan(
        plan_id="plan-existing",
        destination="Hue",
        start_date=date(2026, 11, 1),
        day_count=1,
        entries=[
            ScheduleEntry(
                id="entry-existing",
                day_index=1,
                start_time=time(9),
                end_time=time(10, 30),
                place=place,
            )
        ],
        summary="Existing plan",
    )


class _NoSearch:
    def search_places(self, *args, **kwargs):
        raise AssertionError("A provider failure before routing must not search")


def test_both_model_attempts_failing_preserves_the_current_plan(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "configured-key")
    current = _existing_plan()
    primary = _RecordingModel("gpt-test", APIConnectionError(request=_request()))
    fallback = _RecordingModel("qwen-test", RuntimeError("ollama unavailable"))
    failed_coordinator = OpenAIWithOllamaFallbackStructuredModel(primary, fallback)
    unused = _RecordingModel("unused", AssertionError("must not be called"))
    service = TravelPlannerService(
        CoordinatorAgent(failed_coordinator),
        PlannerAgent(unused),
        ChatAgent(unused),
        search=_NoSearch(),
        config=RuntimeConfig(),
    )

    response = service.handle_turn(
        thread_id="thread-both-fail",
        message="Hãy thay đổi lịch trình.",
        current_plan=current,
    )

    assert response.status is ResponseStatus.PROVIDER_ERROR
    assert response.current_plan == current
    assert response.committed is False
    assert len(primary.calls) == len(fallback.calls) == 1
