"""LangChain structured-output model adapters."""

import os
from collections.abc import Mapping
from typing import TypeVar

from pydantic import BaseModel

from grounded_travel_planner.config import DEFAULT_MODEL_NAME
from grounded_travel_planner.providers import StructuredChatModel

T = TypeVar("T", bound=BaseModel)
OPENAI_MAX_RETRIES = 0
OPENAI_TIMEOUT_SECONDS = 20
OPENAI_JSON_SCHEMA_MODEL_NAMES = frozenset({"gpt-6.1-terra"})


class ChatOpenAIStructuredModel(StructuredChatModel):
    """Lazy adapter so importing the package does not touch OpenAI."""

    def __init__(self, model_name: str = DEFAULT_MODEL_NAME) -> None:
        self._model_name = model_name

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
        if self._model_name in OPENAI_JSON_SCHEMA_MODEL_NAMES:
            model_options["reasoning_effort"] = "none"
            structured_output_method = "json_schema"
        model = ChatOpenAI(
            **model_options,
        ).with_structured_output(
            schema,
            method=structured_output_method,
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
    """Make one local attempt only for an unavailable selected OpenAI model."""

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
        try:
            return self._primary.generate_structured(prompt, schema, metadata=metadata)
        except Exception as error:
            if not _is_openai_fallback_error(
                error,
                missing_api_key=not os.getenv("OPENAI_API_KEY", "").strip(),
            ):
                raise
        return self._fallback.generate_structured(prompt, schema, metadata=metadata)


def _is_openai_fallback_error(error: Exception, *, missing_api_key: bool) -> bool:
    """Return whether a failed remote OpenAI request can use local Ollama."""

    from openai import (
        APIConnectionError,
        APIStatusError,
        APITimeoutError,
        AuthenticationError,
        InternalServerError,
        OpenAIError,
        RateLimitError,
    )

    if isinstance(
        error,
        (
            APIConnectionError,
            APITimeoutError,
            AuthenticationError,
            InternalServerError,
            RateLimitError,
        ),
    ):
        return True
    if missing_api_key and isinstance(error, OpenAIError):
        return True
    return isinstance(error, APIStatusError) and (
        error.status_code in {401, 403, 408, 429} or error.status_code >= 500
    )
