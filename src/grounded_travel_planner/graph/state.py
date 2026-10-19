"""Explicit graph state for one session turn."""

from __future__ import annotations

from typing import Literal

from typing_extensions import NotRequired, TypedDict

from grounded_travel_planner.contracts import (
    AgentResponse,
    ChatSearchDecision,
    ConversationTurn,
    CoordinatorDecision,
    PlanCandidate,
    SightseeingPlan,
    SourceReference,
    TavilyToolRequest,
    TripRequest,
    ValidationIssue,
)


class PlannerState(TypedDict):
    thread_id: str
    turn_id: str
    message: str
    request: TripRequest | None
    current_plan: SightseeingPlan | None
    session_summary: str
    conversation_history: list[ConversationTurn]
    graph_steps: int
    search_calls: int
    repair_attempts: int
    committed: bool
    decision: NotRequired[CoordinatorDecision]
    candidate: NotRequired[PlanCandidate | None]
    validation_issues: NotRequired[list[ValidationIssue]]
    response_hint: NotRequired[str]
    search_request: NotRequired[TavilyToolRequest | None]
    last_search_owner: NotRequired[Literal["planner", "chat"] | None]
    planner_search_sources: NotRequired[list[SourceReference]]
    chat_search_sources: NotRequired[list[SourceReference]]
    chat_search_failed: NotRequired[bool]
    chat_decision: NotRequired[ChatSearchDecision | None]
    response: NotRequired[AgentResponse]
