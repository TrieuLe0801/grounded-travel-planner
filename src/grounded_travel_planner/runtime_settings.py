"""Validated administrator-owned runtime model settings."""

from __future__ import annotations

import re
from contextlib import contextmanager
from contextvars import ContextVar, Token
from typing import Literal, TypeAlias

from pydantic import BaseModel, ConfigDict, Field, field_validator

RuntimeProvider: TypeAlias = Literal["openai", "ollama"]
AgentRole: TypeAlias = Literal["coordinator", "planner", "chat"]


class AgentModelSettings(BaseModel):
    """Allowlisted settings for one runtime role; never holds credentials."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    provider: RuntimeProvider
    model: str = Field(min_length=1, max_length=128)
    system_prompt: str = Field(default="", max_length=8000)
    temperature: float = Field(default=1.0, ge=0, le=2)
    top_p: float = Field(default=1.0, gt=0, le=1)
    max_output_tokens: int = Field(ge=256, le=16384)

    @field_validator("model")
    @classmethod
    def validate_model_identifier(cls, value: str) -> str:
        value = value.strip()
        lowered = value.casefold()
        credential_prefixes = ("sk-", "lsv2_", "ls__")
        if (
            "://" in value
            or lowered.startswith(credential_prefixes)
            or re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:/-]{0,127}", value) is None
        ):
            raise ValueError("Model identifier contains unsupported characters.")
        return value

    @field_validator("system_prompt")
    @classmethod
    def normalize_system_prompt(cls, value: str) -> str:
        return value.strip()


class RuntimeAgentSettings(BaseModel):
    """Complete application-wide settings for the three fixed runtime roles."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    coordinator: AgentModelSettings
    planner: AgentModelSettings
    chat: AgentModelSettings

    def for_role(self, role: AgentRole) -> AgentModelSettings:
        return getattr(self, role)


_TURN_SETTINGS: ContextVar[RuntimeAgentSettings | None] = ContextVar(
    "gtp_turn_model_settings", default=None
)


def current_turn_agent_settings(role: AgentRole) -> AgentModelSettings | None:
    settings = _TURN_SETTINGS.get()
    return settings.for_role(role) if settings is not None else None


@contextmanager
def turn_model_settings(
    settings: RuntimeAgentSettings | None,
):
    """Pin one immutable model-settings version to this graph invocation."""

    token: Token[RuntimeAgentSettings | None] = _TURN_SETTINGS.set(settings)
    try:
        yield
    finally:
        _TURN_SETTINGS.reset(token)
