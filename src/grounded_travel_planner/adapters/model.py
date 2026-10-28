"""LangChain structured-output model adapters."""

from collections.abc import Mapping
from typing import TypeVar

from pydantic import BaseModel

from grounded_travel_planner.providers import StructuredChatModel

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
    ) -> None:
        self._model_name = model_name
        self._json_schema_model_names = frozenset(json_schema_model_names)

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
            **({"strict": False} if structured_output_method == "json_schema" else {}),
        )
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
            config={"metadata": dict(metadata or {})},
        )
        if isinstance(result, schema):
            return result
        return schema.model_validate(result)


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

    def __init__(self, model_name: str, base_url: str | None = None) -> None:
        self._model_name = model_name
        self._base_url = base_url.strip() if base_url else None

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

        model_options: dict[str, str] = {"model": self._model_name}
        if self._base_url:
            model_options["base_url"] = self._base_url
        model = ChatOllama(**model_options).with_structured_output(schema)
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
            config={"metadata": dict(metadata or {})},
        )
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
