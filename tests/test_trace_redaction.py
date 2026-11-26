"""Offline trace privacy setup contracts for LangChain model calls."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

import pytest

from grounded_travel_planner.adapters.trace import (
    LangSmithTraceSink,
    redact_trace_content,
)
from grounded_travel_planner.service import TravelPlannerService
from grounded_travel_planner.usage import account_trace_ref


@pytest.mark.parametrize(
    ("tracing", "api_key", "expected_clients"),
    [
        ("true", "configured-test-key", 1),
        ("false", "configured-test-key", 0),
        ("true", "", 0),
    ],
)
def test_langsmith_tracing_client_preserves_redacted_inputs_and_outputs(
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
        assert clients == [
            {
                "hide_inputs": False,
                "hide_outputs": False,
                "anonymizer": redact_trace_content,
            }
        ]
        assert configured[0] is instances[0]


@pytest.mark.parametrize(
    "text",
    [
        "Thời gian tham quan là ước tính; giờ mở cửa chưa được xác minh. " * 20,
        "Visit duration is estimated; opening hours remain unverified. " * 20,
    ],
)
def test_trace_content_preserves_complete_messages_and_usage(text: str) -> None:
    payload = {
        "messages": [{"type": "human", "data": {"content": text}}],
        "generations": [[{"message": {"content": text}}]],
        "usage_metadata": {"input_tokens": 123, "output_tokens": 456},
        "metadata": {"thread_id": "session-123", "source_id": "source-1"},
    }

    assert len(text) > 500
    assert redact_trace_content(payload) == payload


def test_trace_content_redacts_nested_credentials_without_mutation() -> None:
    payload = {
        "messages": [
            {
                "content": [
                    {"type": "text", "text": "Example sk-syntheticsecret123"},
                    "Bearer syntheticcredential123",
                    {"api_key": "short-secret", "text": "Hà Nội"},
                ]
            }
        ],
        "Authorization": "short-secret",
        "access_token": "short-secret",
        "password": "short-secret",
        "token_usage": {"prompt_tokens": 12, "completion_tokens": 4},
    }

    redacted = redact_trace_content(payload)

    assert redacted["messages"][0]["content"] == [
        {"type": "text", "text": "Example [REDACTED]"},
        "[REDACTED]",
        {"api_key": "[REDACTED]", "text": "Hà Nội"},
    ]
    for field in ("Authorization", "access_token", "password"):
        assert redacted[field] == "[REDACTED]"
    assert redacted["token_usage"] == payload["token_usage"]
    assert payload["Authorization"] == "short-secret"


def test_lazy_trace_client_uses_same_redaction(monkeypatch: pytest.MonkeyPatch) -> None:
    import langsmith

    options: list[dict[str, object]] = []

    class FakeClient:
        def __init__(self, **kwargs: object) -> None:
            options.append(kwargs)

    monkeypatch.setattr(langsmith, "Client", FakeClient)
    sink = LangSmithTraceSink()

    assert sink._get_client() is sink._get_client()
    assert options == [
        {
            "hide_inputs": False,
            "hide_outputs": False,
            "anonymizer": redact_trace_content,
        }
    ]


def test_sdk_redacts_serialized_langchain_messages() -> None:
    from langchain_core.messages import AIMessage, HumanMessage
    from langsmith import Client

    client = Client(
        api_key="synthetic-test-key",
        api_url="http://localhost:1",
        auto_batch_tracing=False,
        hide_inputs=False,
        hide_outputs=False,
        anonymizer=redact_trace_content,
    )
    text = "Thời gian tham quan chưa được xác minh. " * 20
    inputs = client._hide_run_inputs(
        {"messages": [HumanMessage(content=text + "sk-syntheticsecret123")]}
    )
    outputs = client._hide_run_outputs(
        {
            "message": AIMessage(
                content="Keep this answer; Bearer syntheticcredential123",
                usage_metadata={
                    "input_tokens": 12,
                    "output_tokens": 4,
                    "total_tokens": 16,
                },
            )
        }
    )
    metadata = {
        "thread_id": "abbeec73-d0f2-409e-a35f-6a1ae0487587",
        "account_ref": account_trace_ref("df98f64d-173a-45e7-a4d6-a352a15f2686"),
        "source_id": "source-" + "a" * 64,
        "ls_provider": "ollama",
        "ls_model_name": "synthetic-model",
    }

    assert inputs["messages"][0]["content"] == text + "[REDACTED]"
    assert outputs["message"]["content"] == "Keep this answer; [REDACTED]"
    assert outputs["message"]["usage_metadata"] == {
        "input_tokens": 12,
        "output_tokens": 4,
        "total_tokens": 16,
    }
    assert client._hide_run_metadata(metadata) == metadata
    assert redact_trace_content({"source_ids": [metadata["source_id"]]}) == {
        "source_ids": [metadata["source_id"]]
    }


def test_trace_event_completes_when_sdk_create_returns_none() -> None:
    created: list[dict[str, object]] = []
    updated: list[tuple[UUID, dict[str, object]]] = []

    class FakeClient:
        def create_run(self, **kwargs: object) -> None:
            created.append(kwargs)

        def update_run(self, run_id: UUID, **kwargs: object) -> None:
            updated.append((run_id, kwargs))

    before = datetime.now(timezone.utc)
    sink = LangSmithTraceSink("test-project", client=FakeClient())
    sink.record_event(
        "validation",
        {"status": "valid", "api_key": "synthetic-secret"},
        thread_id="session-123",
    )

    assert len(created) == len(updated) == 1
    run_id = created[0]["id"]
    assert isinstance(run_id, UUID)
    assert created[0]["inputs"] == {"status": "valid", "api_key": "[REDACTED]"}
    assert created[0]["extra"] == {"metadata": {"thread_id": "session-123"}}
    assert created[0]["project_name"] == "test-project"
    assert updated[0][0] == run_id
    assert updated[0][1]["outputs"] == {"ok": True}
    assert before <= updated[0][1]["end_time"] <= datetime.now(timezone.utc)


def test_trace_event_failure_does_not_interrupt_application() -> None:
    class FailingClient:
        def create_run(self, **kwargs: object) -> None:
            raise RuntimeError("synthetic trace failure")

    LangSmithTraceSink(client=FailingClient()).record_event(
        "validation", {"status": "valid"}, thread_id="session-123"
    )
