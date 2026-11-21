"""Offline runtime model-settings isolation and validation tests."""

from __future__ import annotations

from collections.abc import Mapping
from typing import TypeVar

import pytest
from pydantic import BaseModel, ValidationError

from grounded_travel_planner.adapters.model import AdminConfigurableStructuredModel
from grounded_travel_planner.contracts import (
    AgentResponse,
    ChatResponse,
    ResponseStatus,
)
from grounded_travel_planner.runtime_settings import (
    AgentModelSettings,
    RuntimeAgentSettings,
    current_turn_agent_settings,
    turn_model_settings,
)

T = TypeVar("T", bound=BaseModel)


def _settings(model: str) -> RuntimeAgentSettings:
    role = AgentModelSettings(
        provider="ollama",
        model=model,
        system_prompt="Additional role instructions.",
        temperature=0.2,
        top_p=0.8,
        max_output_tokens=1024,
    )
    return RuntimeAgentSettings(coordinator=role, planner=role, chat=role)


class _ResultModel:
    def __init__(self, model_name: str) -> None:
        self.model_name = model_name
        self.calls: list[tuple[str, str | None]] = []

    def generate_structured(
        self,
        prompt: str,
        schema: type[T],
        *,
        metadata: Mapping[str, str] | None = None,
        system_prompt: str | None = None,
    ) -> T:
        self.calls.append((self.model_name, system_prompt or prompt))
        return schema.model_validate({"message": "ok"})


def test_admin_model_adapter_uses_immutable_turn_snapshot() -> None:
    default_model = _ResultModel("environment-model")
    resolved: list[AgentModelSettings] = []

    def factory(settings: AgentModelSettings) -> _ResultModel:
        resolved.append(settings)
        return _ResultModel(settings.model)

    model = AdminConfigurableStructuredModel("planner", default_model, factory)
    first = _settings("planner-v1")
    second = _settings("planner-v2")

    with turn_model_settings(first):
        assert model.model_name == "planner-v1"
        current = model.generate_structured("task", ChatResponse)
        assert current.message == "ok"
        assert current_turn_agent_settings("planner") is first.planner
        assert model.model_name == "planner-v1"
    with turn_model_settings(second):
        assert model.model_name == "planner-v2"
        model.generate_structured("task", ChatResponse)

    assert [settings.model for settings in resolved] == ["planner-v1", "planner-v2"]
    assert default_model.calls == []
    assert current_turn_agent_settings("planner") is None


@pytest.mark.parametrize(
    "changes",
    [
        {"provider": "arbitrary"},
        {"model": "https://provider.example/model"},
        {"model": "sk-test-secret"},
        {"model": "lsv2_test-secret"},
        {"temperature": -0.1},
        {"temperature": 2.1},
        {"top_p": 0},
        {"top_p": 1.1},
        {"max_output_tokens": 255},
        {"max_output_tokens": 16385},
        {"api_key": "must-not-be-accepted"},
        {"base_url": "http://attacker.example"},
    ],
)
def test_model_settings_reject_unsupported_or_unbounded_fields(changes) -> None:
    values = _settings("safe-model").planner.model_dump()
    values.update(changes)
    with pytest.raises(ValidationError):
        AgentModelSettings.model_validate(values)


def test_service_pins_one_settings_version_for_each_graph_turn() -> None:
    from grounded_travel_planner.adapters.trace import NoOpTraceSink
    from grounded_travel_planner.agents import ChatAgent, CoordinatorAgent, PlannerAgent
    from grounded_travel_planner.service import TravelPlannerService

    class NoSearch:
        def search_places(self, *args, **kwargs):
            return []

    class EmptyModel:
        model_name = "unused"

        def generate_structured(self, *args, **kwargs):
            raise AssertionError("The stub graph must not invoke a model")

    class SnapshotGraph:
        def __init__(self) -> None:
            self.seen: list[str | None] = []
            self.latest = _settings("planner-v1")

        def invoke(self, state, *, config):
            del state, config
            active = current_turn_agent_settings("planner")
            self.seen.append(active.model if active else None)
            self.latest = _settings("planner-v2")
            return {
                "response": AgentResponse(
                    status=ResponseStatus.UNCHANGED,
                    message="ok",
                )
            }

    model = EmptyModel()
    service = TravelPlannerService(
        CoordinatorAgent(model),
        PlannerAgent(model),
        ChatAgent(model),
        search=NoSearch(),
        trace_sink=NoOpTraceSink(),
    )
    graph = SnapshotGraph()
    service.graph = graph
    service.set_runtime_settings_source(lambda: graph.latest)

    for _ in range(2):
        result = service.handle_turn(thread_id="thread-settings", message="hello")
        assert result.status is ResponseStatus.UNCHANGED

    assert graph.seen == ["planner-v1", "planner-v2"]
    assert current_turn_agent_settings("planner") is None
