"""Offline trace privacy setup contracts for LangChain model calls."""

from __future__ import annotations

import pytest

from grounded_travel_planner.service import TravelPlannerService


@pytest.mark.parametrize(
    ("tracing", "api_key", "expected_clients"),
    [
        ("true", "configured-test-key", 1),
        ("false", "configured-test-key", 0),
        ("true", "", 0),
    ],
)
def test_langsmith_tracing_client_hides_model_inputs_and_outputs(
    monkeypatch: pytest.MonkeyPatch,
    tracing: str,
    api_key: str,
    expected_clients: int,
) -> None:
    import langsmith
    import langsmith.run_trees

    clients: list[dict[str, object]] = []
    instances: list[object] = []
    configured: list[object] = []

    class FakeClient:
        def __init__(self, **kwargs: object) -> None:
            clients.append(kwargs)
            instances.append(self)

    def configure(*, client: object) -> None:
        configured.append(client)

    monkeypatch.setattr(langsmith, "Client", FakeClient)
    monkeypatch.setattr(langsmith.run_trees, "configure", configure)
    monkeypatch.setenv("LANGSMITH_TRACING", tracing)
    monkeypatch.setenv("LANGSMITH_API_KEY", api_key)
    monkeypatch.setenv("GTP_COORDINATOR_MODEL", "coordinator-test-model")
    monkeypatch.setenv("GTP_PLANNER_MODEL", "planner-test-model")
    monkeypatch.setenv("GTP_CHAT_MODEL", "chat-test-model")
    monkeypatch.setenv("GTP_OLLAMA_FALLBACK_MODEL", "fallback-test-model")

    TravelPlannerService.from_environment()

    assert len(clients) == expected_clients
    assert len(configured) == expected_clients
    if expected_clients:
        assert clients == [{"hide_inputs": True, "hide_outputs": True}]
        assert configured[0] is instances[0]
