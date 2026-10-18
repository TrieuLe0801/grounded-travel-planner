"""LangChain structured-output model adapters."""

from collections.abc import Mapping
from typing import TypeVar

from pydantic import BaseModel

from grounded_travel_planner.config import DEFAULT_MODEL_NAME
from grounded_travel_planner.providers import StructuredChatModel

T = TypeVar("T", bound=BaseModel)


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

        model = ChatOpenAI(model=self._model_name).with_structured_output(
            schema,
            method="function_calling",
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
