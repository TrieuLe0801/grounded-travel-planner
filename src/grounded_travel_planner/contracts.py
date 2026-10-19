"""Typed contracts shared by UI, graph, agents and providers."""

from datetime import date, time
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field, HttpUrl, field_validator

# Search snippets stay small before becoming prompt data. Source references can
# retain more text when persisted in an already-grounded plan.
SEARCH_SNIPPET_MAX_LENGTH = 1000
SOURCE_REFERENCE_SNIPPET_MAX_LENGTH = 4000


class IntentAction(str, Enum):
    ORDINARY_CHAT = "ordinary_chat"
    CREATE_TRIP = "create_trip"
    ADD_PLACE = "add_place"
    REMOVE_PLACE = "remove_place"
    REPLACE_PLACE = "replace_place"
    REORDER_PLACES = "reorder_places"
    CHANGE_DAY = "change_day"
    CHANGE_TIME = "change_time"
    EXTEND_TRIP = "extend_trip"


class IssueSeverity(str, Enum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


class ResponseStatus(str, Enum):
    COMMITTED = "committed"
    UNCHANGED = "unchanged"
    REJECTED = "rejected"
    NEEDS_INPUT = "needs_input"
    PROVIDER_ERROR = "provider_error"


class TripRequest(BaseModel):
    destination: str = Field(min_length=1, max_length=160)
    start_date: date
    day_count: int = Field(ge=1, le=7)

    @field_validator("destination")
    @classmethod
    def normalize_destination(cls, value: str) -> str:
        return " ".join(value.strip().split())


class SourceReference(BaseModel):
    source_id: str = Field(min_length=1, max_length=80)
    title: str = Field(min_length=1, max_length=240)
    url: HttpUrl
    snippet: str | None = Field(
        default=None,
        max_length=SOURCE_REFERENCE_SNIPPET_MAX_LENGTH,
    )
    provider: str = "tavily"
    retrieval_query: str = Field(default="", max_length=500)
    supports_opening_hours: bool = False


class SearchResult(BaseModel):
    source_id: str = Field(min_length=1, max_length=80)
    title: str = Field(min_length=1, max_length=240)
    url: HttpUrl
    snippet: str | None = Field(default=None, max_length=SEARCH_SNIPPET_MAX_LENGTH)
    score: float | None = None
    supports_opening_hours: bool = False


class ConversationTurn(BaseModel):
    """A bounded transcript item kept only in the active browser session."""

    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=4000)
    source_references: list[SourceReference] = Field(default_factory=list, max_length=8)


class ChatSearchDecision(BaseModel):
    """The only model-authorized search request the Chat role can make."""

    should_search: bool = False
    query: str = Field(default="", max_length=400)
    message: str = Field(default="", max_length=2000)


class TavilyToolRequest(BaseModel):
    """A bounded request consumed only by the shared Tavily graph tool node."""

    owner: Literal["planner", "chat"]
    query: str = Field(min_length=1, max_length=400)
    max_results: int = Field(ge=1, le=8)


class PlaceRecommendation(BaseModel):
    place_id: str = Field(min_length=1, max_length=80)
    name: str = Field(min_length=1, max_length=160)
    description: str = Field(min_length=1, max_length=1000)
    source_references: list[SourceReference] = Field(min_length=1)
    visit_minutes_estimate: int = Field(default=90, ge=15)
    travel_minutes_estimate: int = Field(default=20, ge=0)
    opening_hours: str | None = None
    opening_hours_verified: bool = False


class ScheduleEntry(BaseModel):
    id: str = Field(min_length=1, max_length=80)
    day_index: int = Field(ge=1, le=7)
    start_time: time
    end_time: time
    place: PlaceRecommendation
    notes: str | None = Field(default=None, max_length=1000)


class SightseeingPlan(BaseModel):
    plan_id: str = Field(min_length=1, max_length=80)
    destination: str = Field(min_length=1, max_length=160)
    start_date: date
    day_count: int = Field(ge=1, le=7)
    entries: list[ScheduleEntry] = Field(default_factory=list)
    summary: str = Field(default="", max_length=2000)
    revision: int = Field(default=1, ge=1)


def visible_schedule_entries(plan: SightseeingPlan) -> list[ScheduleEntry]:
    """Return entries in the same chronological order shown to the user."""

    return sorted(
        plan.entries,
        key=lambda entry: (
            entry.day_index,
            entry.start_time,
            entry.end_time,
            entry.id,
        ),
    )


def visible_schedule_context(
    plan: SightseeingPlan | None,
) -> list[dict[str, str | int]]:
    """Give agents an unambiguous, zero-based view of the current itinerary."""

    if plan is None:
        return []
    return [
        {
            "index": index,
            "entry_id": entry.id,
            "place_name": entry.place.name,
            "day_index": entry.day_index,
            "start_time": entry.start_time.isoformat(),
            "end_time": entry.end_time.isoformat(),
        }
        for index, entry in enumerate(visible_schedule_entries(plan))
    ]


class ValidationIssue(BaseModel):
    code: str = Field(min_length=1, max_length=80)
    message: str = Field(min_length=1, max_length=500)
    severity: IssueSeverity = IssueSeverity.ERROR
    entry_id: str | None = None


class PlannerProposal(BaseModel):
    """Model-authored plan fields before trusted search data is attached."""

    plan: SightseeingPlan = Field(
        description="Complete candidate itinerary for the requested plan change."
    )
    summary: str = Field(default="", max_length=2000)
    issues: list[ValidationIssue] = Field(default_factory=list)


class PlanCandidate(PlannerProposal):
    """Grounded proposal carrying provider-owned source provenance."""

    returned_source_urls: set[str] = Field(default_factory=set)
    returned_sources: list[SourceReference] = Field(default_factory=list)


class PlanChangeIntent(BaseModel):
    action: IntentAction = IntentAction.ORDINARY_CHAT
    user_message: str = Field(default="", max_length=4000)
    destination: str | None = Field(default=None, max_length=160)
    start_date: date | None = None
    day_count: int | None = Field(default=None, ge=1, le=7)
    day_count_delta: int | None = Field(default=None, ge=1, le=6)
    place_name: str | None = Field(default=None, max_length=160)
    replacement_place_name: str | None = Field(default=None, max_length=160)
    from_index: int | None = Field(default=None, ge=0)
    to_index: int | None = Field(default=None, ge=0)
    entry_id: str | None = Field(default=None, max_length=80)
    day_index: int | None = Field(default=None, ge=1, le=7)
    start_time: time | None = None
    end_time: time | None = None

    @property
    def mutates_plan(self) -> bool:
        return self.action is not IntentAction.ORDINARY_CHAT


class CoordinatorDecision(BaseModel):
    """Structured classification; Coordinator never proposes a plan."""

    intent: PlanChangeIntent
    requires_planner: bool = False
    response_hint: str = Field(default="", max_length=1000)
    session_summary: str = Field(default="", max_length=1200)


class ChatResponse(BaseModel):
    """User-facing Vietnamese response written by the Chat runtime role."""

    message: str = Field(min_length=1, max_length=2000)


class AgentResponse(BaseModel):
    status: ResponseStatus
    message: str
    current_plan: SightseeingPlan | None = None
    committed: bool = False
    intent: PlanChangeIntent | None = None
    validation_issues: list[ValidationIssue] = Field(default_factory=list)
    graph_steps: int = Field(default=0, ge=0)
    search_calls: int = Field(default=0, ge=0)
    repair_attempts: int = Field(default=0, ge=0)
    source_references: list[SourceReference] = Field(default_factory=list, max_length=8)
    metadata: dict[str, Any] = Field(default_factory=dict)
