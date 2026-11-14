"""Offline LangSmith account-usage attribution and aggregation regressions."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from types import SimpleNamespace

import pytest

from grounded_travel_planner.adapters.model import (
    ChatOpenAIStructuredModel,
    OllamaStructuredChatModel,
)
from grounded_travel_planner.contracts import ChatResponse
from grounded_travel_planner.graph.nodes import _metadata
from grounded_travel_planner.usage import (
    UsageError,
    UsageRepository,
    account_trace_ref,
    account_usage_context,
    current_account_trace_ref,
)


def _run(
    account_id: str,
    *,
    at: str = "2026-11-01T12:00:00+00:00",
    provider: str = "openai",
    model: str = "priced",
    prompt: int | None = 10,
    completion: int | None = 5,
    cost: float | None = 0.002,
    price_model_id: str | None = "price-id",
):
    return SimpleNamespace(
        metadata={
            "account_ref": account_trace_ref(account_id),
            "ls_provider": provider,
            "ls_model_name": model,
            "agent_role": "planner",
        },
        run_type="LLM",
        name=model,
        start_time=datetime.fromisoformat(at),
        prompt_tokens=prompt,
        completion_tokens=completion,
        total_cost=cost,
        price_model_id=price_model_id,
    )


class _Runs:
    def __init__(self, runs):
        self.items = runs
        self.calls = []
        self.error = None

    def query(self, **kwargs):
        self.calls.append(kwargs)

        async def pages():
            for run in self.items:
                if self.error:
                    raise self.error
                yield run

        return pages()


class _Client:
    def __init__(self, runs):
        self.runs = _Runs(runs)
        self.read_project_calls = 0

    def read_project(self, *, project_name):
        assert project_name == "test-project"
        self.read_project_calls += 1
        return SimpleNamespace(id="project-id")


def test_langsmith_usage_filters_account_and_date_and_keeps_unknown_cost():
    first, second = "account-one", "account-two"
    client = _Client(
        [
            _run(first, cost=0.002),
            _run(first, cost=None, model="unpriced"),
            _run(second, prompt=7, completion=3, cost=0.001),
            _run(first, at="2026-10-01T12:00:00+00:00", cost=1),
            _run(first, at="2026-11-02T00:00:00+00:00", cost=1),
        ]
    )
    usage = UsageRepository(client=client, project_name="test-project")
    summaries = usage.summary_for_users(
        [first, second],
        start="2026-11-01T00:00:00+00:00",
        end="2026-11-02T00:00:00+00:00",
    )
    assert summaries[first].input_tokens == 20
    assert summaries[first].output_tokens == 10
    assert summaries[first].estimated_cost_usd is None
    assert summaries[first].unpriced_calls == 1
    assert summaries[second].estimated_cost_usd == Decimal("0.001")
    assert client.read_project_calls == 1
    query = client.runs.calls[0]
    assert query["run_type"] == "LLM"
    assert query["project_ids"] == ["project-id"]
    assert query["min_start_time"] == datetime(2026, 11, 1, tzinfo=timezone.utc)
    assert "in(metadata_value" in query["filter"]
    assert "PROMPT_TOKENS" in query["selects"]
    assert "TOTAL_COST" in query["selects"]
    assert "INPUTS" not in query["selects"]

    summary, detail = usage.usage_for_user(
        first,
        start="2026-11-01T00:00:00+00:00",
        end="2026-11-02T00:00:00+00:00",
    )
    assert summary == summaries[first]
    assert [row["model"] for row in detail] == ["priced", "unpriced"]
    assert detail[0]["estimated_cost_usd"] == Decimal("0.002")
    assert detail[1]["estimated_cost_usd"] is None
    assert len(client.runs.calls) == 2


def test_langsmith_missing_usage_and_unknown_zero_price_are_not_fabricated():
    account = "account-one"
    usage = UsageRepository(
        client=_Client(
            [
                _run(account, prompt=None, completion=None, cost=None),
                _run(account, cost=0, price_model_id=None),
                _run(account, cost=0, price_model_id="free-price"),
            ]
        ),
        project_name="test-project",
    )
    summary = usage.summary_for_users([account])[account]
    assert summary.input_tokens == 20
    assert summary.unpriced_calls == 1
    assert summary.estimated_cost_usd is None


def test_langsmith_failure_is_explicit_and_no_credentials_are_required_for_empty_page():
    client = _Client([])
    client.runs.error = RuntimeError("secret provider failure")
    usage = UsageRepository(client=client, project_name="test-project")
    assert usage.summary_for_users([]) == {}
    client.runs.items = [_run("account-one")]
    with pytest.raises(UsageError, match="LangSmith usage is unavailable"):
        usage.summary_for_users(["account-one"])


def test_account_ref_reaches_model_trace_without_raw_account_id(monkeypatch):
    account_id = "123e4567-e89b-42d3-a456-426614174000"
    observed = []

    class _Model:
        def __init__(self, **kwargs):
            del kwargs

        def with_structured_output(self, *args, **kwargs):
            del args, kwargs
            return self

        def invoke(self, messages, config):
            del messages
            observed.append(config)
            return {
                "raw": SimpleNamespace(
                    usage_metadata={"input_tokens": 13, "output_tokens": 5}
                ),
                "parsed": ChatResponse(message="ok"),
                "parsing_error": None,
            }

    monkeypatch.setattr("langchain_openai.ChatOpenAI", _Model)
    adapter = ChatOpenAIStructuredModel("priced", role="chat")
    with account_usage_context(account_id):
        assert current_account_trace_ref() == account_trace_ref(account_id)
        metadata = _metadata({"thread_id": "thread", "turn_id": "turn"}, "chat")
        adapter.generate_structured("private", ChatResponse, metadata=metadata)
    assert current_account_trace_ref() is None
    assert observed[0]["metadata"]["account_ref"] == account_trace_ref(account_id)
    assert observed[0]["metadata"]["ls_provider"] == "openai"
    assert observed[0]["metadata"]["ls_model_name"] == "priced"
    assert account_id not in str(observed)


def test_ollama_trace_has_provider_and_account_ref(monkeypatch):
    observed = []

    class _Model:
        def __init__(self, **kwargs):
            del kwargs

        def with_structured_output(self, *args, **kwargs):
            del args, kwargs
            return self

        def invoke(self, messages, config):
            del messages
            observed.append(config)
            return ChatResponse(message="ok")

    monkeypatch.setattr("langchain_ollama.ChatOllama", _Model)
    with account_usage_context("account-one"):
        OllamaStructuredChatModel("local", role="chat").generate_structured(
            "private", ChatResponse, metadata={"thread_id": "thread"}
        )
    assert observed[0]["metadata"]["ls_provider"] == "ollama"
    assert observed[0]["metadata"]["account_ref"] == account_trace_ref("account-one")
