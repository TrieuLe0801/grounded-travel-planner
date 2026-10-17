"""Runtime configuration and product bounds."""

from pydantic import BaseModel, Field

DEFAULT_MODEL_NAME = "gpt-5.5"
DEFAULT_LIGHTWEIGHT_MODEL_NAME = "gpt-5.4-mini"


class RuntimeConfig(BaseModel):
    """Small immutable runtime settings used by agents and graph nodes."""

    # ``model_name`` remains the public/default model setting for existing
    # callers and is assigned to the Coordinator. The Planner and Chat roles
    # can use a smaller model without changing that contract.
    model_name: str = DEFAULT_MODEL_NAME
    planner_model_name: str = DEFAULT_LIGHTWEIGHT_MODEL_NAME
    chat_model_name: str = DEFAULT_LIGHTWEIGHT_MODEL_NAME
    graph_step_limit: int = Field(default=8, ge=1, le=8)
    search_call_limit: int = Field(default=2, ge=0, le=2)
    repair_attempt_limit: int = Field(default=1, ge=0, le=1)
    default_visit_minutes: int = Field(default=90, ge=15)
    default_travel_minutes: int = Field(default=20, ge=0)
