"""LangChain structured-output model adapters."""

from collections.abc import Mapping
from typing import TypeVar

from pydantic import BaseModel

from grounded_travel_planner.providers import StructuredChatModel, TraceSink
from grounded_travel_planner.usage import current_account_trace_ref

T = TypeVar("T", bound=BaseModel)
OPENAI_MAX_RETRIES = 0
# Full itinerary schemas can take longer than a short chat response to generate.
OPENAI_TIMEOUT_SECONDS = 60


class ChatOpenAIStructuredModel(StructuredChatModel):
    """Lazy adapter so importing the package does not touch OpenAI."""

    def __init__(
        self,
        model_name: str,
        *,
        json_schema_model_names: tuple[str, ...] = (),
        max_completion_tokens: int = 2048,
        trace_sink: TraceSink | None = None,
        role: str = "unknown",
    ) -> None:
        self._model_name = model_name
        self._json_schema_model_names = frozenset(json_schema_model_names)
        self._max_completion_tokens = max_completion_tokens
        self._trace_sink = trace_sink
        self._role = role

    @property
    def model_name(self) -> str:
        return self._model_name

    def generate_structured(
        self,
        prompt: str,
        schema: type[T],
        *,
        metadata: Mapping[str, str] | None = None,
    ) -> T:
        from langchain_core.messages import HumanMessage, SystemMessage
        from langchain_openai import ChatOpenAI

        model_options: dict[str, str | int] = {
            "model": self._model_name,
            "max_retries": OPENAI_MAX_RETRIES,
            "timeout": OPENAI_TIMEOUT_SECONDS,
            "max_completion_tokens": self._max_completion_tokens,
        }
        structured_output_method = "function_calling"
        structured_schema: type[T] | dict[str, object] = schema
        if self._model_name in self._json_schema_model_names:
            model_options["reasoning_effort"] = "none"
            structured_output_method = "json_schema"
            structured_schema = _openai_json_schema(schema)
        model = ChatOpenAI(
            **model_options,
        ).with_structured_output(
            structured_schema,
            method=structured_output_method,
            include_raw=True,
            **({"strict": False} if structured_output_method == "json_schema" else {}),
        )
        trace_metadata = dict(metadata or {})
        account_ref = current_account_trace_ref()
        if account_ref:
            trace_metadata["account_ref"] = account_ref
        trace_metadata.update(ls_provider="openai", ls_model_name=self._model_name)
        result = model.invoke(
            [
                SystemMessage(
                    content=(
                        "You are a bounded travel-planner runtime component. "
                        "Return only the requested structured output. Do not "
                        "include secrets, API keys, or unsupported claims."
                    )
                ),
                HumanMessage(content=prompt),
            ],
            config={"metadata": trace_metadata},
        )
        if not isinstance(result, Mapping) or "parsed" not in result:
            if isinstance(result, schema):
                return result
            return schema.model_validate(result)

        self._record_usage(result.get("raw"), metadata)
        parsing_error = result.get("parsing_error")
        if isinstance(parsing_error, Exception):
            raise parsing_error
        parsed = result.get("parsed")
        if isinstance(parsed, schema):
            return parsed
        return schema.model_validate(parsed)

    def _record_usage(self, raw: object, metadata: Mapping[str, str] | None) -> None:
        """Record only provider usage counters; telemetry cannot affect a turn."""

        if metadata is None:
            return
        thread_id = metadata.get("thread_id")
        turn_id = metadata.get("turn_id")
        usage = getattr(raw, "usage_metadata", None)
        if not thread_id or not turn_id or not isinstance(usage, Mapping):
            return
        input_tokens = usage.get("input_tokens")
        output_tokens = usage.get("output_tokens")
        if (
            not isinstance(input_tokens, int)
            or isinstance(input_tokens, bool)
            or input_tokens < 0
            or not isinstance(output_tokens, int)
            or isinstance(output_tokens, bool)
            or output_tokens < 0
        ):
            return
        if self._trace_sink is None:
            return
        try:
            self._trace_sink.record_event(
                "model.usage",
                {
                    "model": self._model_name,
                    "role": self._role,
                    "input_tokens": input_tokens,
                    "output_tokens": output_tokens,
                    "turn_id": turn_id,
                },
                thread_id=thread_id,
            )
        except Exception:  # noqa: BLE001 - telemetry must not affect planning
            return


def _openai_json_schema(schema: type[T]) -> dict[str, object]:
    """Make Pydantic JSON Schema acceptable to OpenAI's supported subset.

    OpenAI currently rejects the JSON Schema ``uri`` format used by Pydantic's
    ``HttpUrl``. URL semantics are still enforced locally when the returned
    mapping is validated against the original Pydantic model.
    """

    generated = schema.model_json_schema()

    def remove_unsupported_uri_format(value: object) -> None:
        if isinstance(value, dict):
            if value.get("format") == "uri":
                value.pop("format")
            for child in value.values():
                remove_unsupported_uri_format(child)
        elif isinstance(value, list):
            for child in value:
                remove_unsupported_uri_format(child)

    remove_unsupported_uri_format(generated)
    return generated


class OllamaStructuredChatModel(StructuredChatModel):
    """ChatOllama adapter with the same bounded structured-output contract."""

    def __init__(
        self,
        model_name: str,
        base_url: str | None = None,
        *,
        max_completion_tokens: int = 2048,
        role: str = "unknown",
    ) -> None:
        self._model_name = model_name
        self._base_url = base_url.strip() if base_url else None
        self._max_completion_tokens = max_completion_tokens
        self._role = role

    @property
    def model_name(self) -> str:
        return self._model_name

    def generate_structured(
        self,
        prompt: str,
        schema: type[T],
        *,
        metadata: Mapping[str, str] | None = None,
    ) -> T:
        from langchain_core.messages import HumanMessage, SystemMessage
        from langchain_ollama import ChatOllama

        model_options: dict[str, str | int] = {
            "model": self._model_name,
            # ChatOllama forwards ``num_predict`` to Ollama as its generation cap.
            "num_predict": self._max_completion_tokens,
        }
        if self._base_url:
            model_options["base_url"] = self._base_url
        model = ChatOllama(**model_options).with_structured_output(schema)
        trace_metadata = dict(metadata or {})
        account_ref = current_account_trace_ref()
        if account_ref:
            trace_metadata["account_ref"] = account_ref
        trace_metadata.update(ls_provider="ollama", ls_model_name=self._model_name)
        result = model.invoke(
            [
                SystemMessage(
                    content=(
                        "You are a bounded travel-planner runtime component. "
                        "Return only the requested structured output. Do not "
                        "include secrets, API keys, or unsupported claims."
                    )
                ),
                HumanMessage(content=prompt),
            ],
            config={"metadata": trace_metadata},
        )
        if isinstance(result, Mapping) and "parsed" in result:
            parsing_error = result.get("parsing_error")
            if isinstance(parsing_error, Exception):
                raise parsing_error
            result = result["parsed"]
        if isinstance(result, schema):
            return result
        return schema.model_validate(result)


class OpenAIWithOllamaFallbackStructuredModel(StructuredChatModel):
    """Make one local attempt after any selected OpenAI API error."""

    def __init__(
        self,
        primary: StructuredChatModel,
        fallback: StructuredChatModel,
    ) -> None:
        self._primary = primary
        self._fallback = fallback

    @property
    def model_name(self) -> str:
        """Expose the selected OpenAI model, never the fallback identifier."""

        return self._primary.model_name

    def generate_structured(
        self,
        prompt: str,
        schema: type[T],
        *,
        metadata: Mapping[str, str] | None = None,
    ) -> T:
        from openai import OpenAIError

        try:
            return self._primary.generate_structured(prompt, schema, metadata=metadata)
        except OpenAIError:
            pass
        return self._fallback.generate_structured(prompt, schema, metadata=metadata)
