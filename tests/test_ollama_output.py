"""Final-provider output failures remain bounded and safe."""

from types import SimpleNamespace

import pytest
from pydantic import BaseModel

from grounded_travel_planner.adapters.model import (
    OllamaOutputError,
    OllamaStructuredChatModel,
)


class Result(BaseModel):
    value: str


def _adapter(monkeypatch, result):
    calls = []

    class Model:
        def __init__(self, **kwargs):
            assert kwargs["num_predict"] == 2048
            assert kwargs["reasoning"] is False

        def with_structured_output(self, schema, *, method, include_raw):
            assert schema is Result
            assert method == "json_schema"
            assert include_raw is True
            return self

        def invoke(self, *args, **kwargs):
            calls.append(1)
            return result

    monkeypatch.setattr("langchain_ollama.ChatOllama", Model)
    return OllamaStructuredChatModel("test-local"), calls


def _envelope(content, *, reason="stop", parsed=None, error=None):
    return {
        "raw": SimpleNamespace(
            content=content,
            response_metadata={"done_reason": reason},
            additional_kwargs={"reasoning_content": "PRIVATE THINKING"},
        ),
        "parsed": parsed,
        "parsing_error": error,
    }


@pytest.mark.parametrize(
    ("result", "reason"),
    [
        (None, "empty_output"),
        ("  ", "empty_output"),
        (_envelope(""), "empty_output"),
        (_envelope(" \n "), "empty_output"),
        (_envelope([], error=ValueError("PRIVATE")), "empty_output"),
        (_envelope("", reason="length"), "output_token_limit"),
        (_envelope('{"value":', reason="length"), "output_token_limit"),
        (
            _envelope("bad JSON", error=ValueError("PRIVATE")),
            "invalid_structured_output",
        ),
        (_envelope("{}", parsed={}), "invalid_structured_output"),
    ],
)
def test_invalid_output_is_classified_without_retry_or_content(
    monkeypatch, result, reason
):
    adapter, calls = _adapter(monkeypatch, result)
    with pytest.raises(OllamaOutputError) as caught:
        adapter.generate_structured("synthetic", Result)
    assert caught.value.reason == reason
    assert "PRIVATE" not in str(caught.value)
    assert calls == [1]


def test_valid_output_is_validated(monkeypatch):
    adapter, calls = _adapter(
        monkeypatch, _envelope('{"value":"ok"}', parsed={"value": "ok"})
    )
    assert adapter.generate_structured("synthetic", Result) == Result(value="ok")
    assert calls == [1]
