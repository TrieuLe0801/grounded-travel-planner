"""Runtime configuration and product bounds."""

import os
from typing import Literal, TypeAlias

from pydantic import BaseModel, Field, field_validator

DEFAULT_MODEL_NAME = "gpt-5.5"
DEFAULT_LIGHTWEIGHT_MODEL_NAME = "gpt-6.1-terra"
DEFAULT_CHAT_MODEL_NAME = "gpt-4.1"
DEFAULT_OLLAMA_FALLBACK_MODEL_NAME = "qwen2.5:3b"
DEFAULT_MODEL_PROVIDER = "openai"
ModelProvider: TypeAlias = Literal["openai", "ollama"]


class RuntimeConfig(BaseModel):
    """Small immutable runtime settings used by agents and graph nodes."""

    # ``model_name`` remains the public/default model setting for existing
    # callers and is assigned to the Coordinator. The Planner and Chat roles
    # can use a smaller model without changing that contract.
    model_name: str = DEFAULT_MODEL_NAME
    planner_model_name: str = DEFAULT_LIGHTWEIGHT_MODEL_NAME
    chat_model_name: str = DEFAULT_CHAT_MODEL_NAME
    # OpenAI roles may make one local Ollama attempt when the remote provider
    # is unavailable. These names are deliberately separate from the selected
    # OpenAI role models so an API model identifier is never sent to Ollama.
    ollama_fallback_model_name: str = DEFAULT_OLLAMA_FALLBACK_MODEL_NAME
    coordinator_ollama_fallback_model_name: str | None = None
    planner_ollama_fallback_model_name: str | None = None
    chat_ollama_fallback_model_name: str | None = None
    # ``model_provider`` is the legacy global fallback. Per-role providers are
    # optional so existing injected RuntimeConfig instances keep their meaning.
    model_provider: ModelProvider = DEFAULT_MODEL_PROVIDER
    coordinator_provider: ModelProvider | None = None
    planner_provider: ModelProvider | None = None
    chat_provider: ModelProvider | None = None
    graph_step_limit: int = Field(default=8, ge=1, le=8)
    search_call_limit: int = Field(default=2, ge=0, le=2)
    repair_attempt_limit: int = Field(default=1, ge=0, le=1)
    default_visit_minutes: int = Field(default=90, ge=15)
    default_travel_minutes: int = Field(default=20, ge=0)

    @field_validator(
        "model_name",
        "planner_model_name",
        "chat_model_name",
        "ollama_fallback_model_name",
    )
    @classmethod
    def model_names_must_not_be_blank(cls, value: str) -> str:
        """Reject unusable role names before live providers are constructed."""

        normalized = value.strip()
        if not normalized:
            raise ValueError("model name must not be blank")
        return normalized

    @field_validator(
        "coordinator_ollama_fallback_model_name",
        "planner_ollama_fallback_model_name",
        "chat_ollama_fallback_model_name",
    )
    @classmethod
    def optional_fallback_model_names_must_not_be_blank(
        cls, value: str | None
    ) -> str | None:
        """Allow an unset role override but reject an explicitly blank one."""

        if value is None:
            return None
        normalized = value.strip()
        if not normalized:
            raise ValueError("fallback model name must not be blank")
        return normalized

    @classmethod
    def from_environment(cls) -> "RuntimeConfig":
        """Read provider fallback, role overrides and all model names from env."""

        def optional_provider(name: str) -> str | None:
            value = os.getenv(name)
            return value if value and value.strip() else None

        def optional_model_name(name: str) -> str | None:
            return os.environ.get(name)

        return cls(
            model_provider=os.getenv("GTP_MODEL_PROVIDER", DEFAULT_MODEL_PROVIDER),
            coordinator_provider=optional_provider("GTP_COORDINATOR_PROVIDER"),
            planner_provider=optional_provider("GTP_PLANNER_PROVIDER"),
            chat_provider=optional_provider("GTP_CHAT_PROVIDER"),
            model_name=os.getenv("GTP_COORDINATOR_MODEL", DEFAULT_MODEL_NAME),
            planner_model_name=os.getenv(
                "GTP_PLANNER_MODEL", DEFAULT_LIGHTWEIGHT_MODEL_NAME
            ),
            chat_model_name=os.getenv("GTP_CHAT_MODEL", DEFAULT_CHAT_MODEL_NAME),
            ollama_fallback_model_name=os.getenv(
                "GTP_OLLAMA_FALLBACK_MODEL", DEFAULT_OLLAMA_FALLBACK_MODEL_NAME
            ),
            coordinator_ollama_fallback_model_name=optional_model_name(
                "GTP_COORDINATOR_OLLAMA_FALLBACK_MODEL"
            ),
            planner_ollama_fallback_model_name=optional_model_name(
                "GTP_PLANNER_OLLAMA_FALLBACK_MODEL"
            ),
            chat_ollama_fallback_model_name=optional_model_name(
                "GTP_CHAT_OLLAMA_FALLBACK_MODEL"
            ),
        )

    @property
    def coordinator_model_provider(self) -> ModelProvider:
        return self.coordinator_provider or self.model_provider

    @property
    def planner_model_provider(self) -> ModelProvider:
        return self.planner_provider or self.model_provider

    @property
    def chat_model_provider(self) -> ModelProvider:
        return self.chat_provider or self.model_provider

    @property
    def coordinator_ollama_fallback_model(self) -> str:
        return (
            self.coordinator_ollama_fallback_model_name
            or self.ollama_fallback_model_name
        )

    @property
    def planner_ollama_fallback_model(self) -> str:
        return (
            self.planner_ollama_fallback_model_name or self.ollama_fallback_model_name
        )

    @property
    def chat_ollama_fallback_model(self) -> str:
        return self.chat_ollama_fallback_model_name or self.ollama_fallback_model_name
