"""Runtime configuration and product bounds."""

from pydantic import BaseModel, Field

DEFAULT_MODEL_NAME = "gpt-5.5"


class RuntimeConfig(BaseModel):
    """Small immutable runtime settings used by agents and graph nodes."""

    model_name: str = DEFAULT_MODEL_NAME
    graph_step_limit: int = Field(default=8, ge=1, le=8)
    search_call_limit: int = Field(default=2, ge=0, le=2)
    repair_attempt_limit: int = Field(default=1, ge=0, le=1)
    default_visit_minutes: int = Field(default=90, ge=15)
    default_travel_minutes: int = Field(default=20, ge=0)
