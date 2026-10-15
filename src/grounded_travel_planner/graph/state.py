"""Explicit graph state for one session turn."""

from __future__ import annotations

from typing_extensions import NotRequired, TypedDict

from grounded_travel_planner.contracts import (
    AgentResponse,
    CoordinatorDecision,
    PlanCandidate,
    SightseeingPlan,
    TripRequest,
    ValidationIssue,
)


class PlannerState(TypedDict):
    thread_id: str
    turn_id: str
    message: str
    request: TripRequest | None
    current_plan: SightseeingPlan | None
    graph_steps: int
    search_calls: int
    repair_attempts: int
    committed: bool
    decision: NotRequired[CoordinatorDecision]
    candidate: NotRequired[PlanCandidate | None]
    validation_issues: NotRequired[list[ValidationIssue]]
    repair_issues: NotRequired[list[ValidationIssue]]
    response_hint: NotRequired[str]
    response: NotRequired[AgentResponse]
