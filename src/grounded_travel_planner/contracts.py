"""Typed contracts shared by UI, graph, agents and providers."""

from datetime import date, time
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, HttpUrl, field_validator


class IntentAction(str, Enum):
    ORDINARY_CHAT = "ordinary_chat"
    CREATE_TRIP = "create_trip"
    ADD_PLACE = "add_place"
    REMOVE_PLACE = "remove_place"
    REPLACE_PLACE = "replace_place"
    REORDER_PLACES = "reorder_places"
    CHANGE_DAY = "change_day"
    CHANGE_TIME = "change_time"


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
    snippet: str | None = Field(default=None, max_length=1000)
    provider: str = "tavily"
    retrieval_query: str = Field(default="", max_length=500)
    supports_opening_hours: bool = False


class SearchResult(BaseModel):
    source_id: str = Field(min_length=1, max_length=80)
    title: str = Field(min_length=1, max_length=240)
    url: HttpUrl
    snippet: str | None = Field(default=None, max_length=1000)
    score: float | None = None
    supports_opening_hours: bool = False


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


class PlanCandidate(BaseModel):
    plan: SightseeingPlan | None = None
    summary: str = Field(default="", max_length=2000)
    issues: list[ValidationIssue] = Field(default_factory=list)
    returned_source_urls: set[str] = Field(default_factory=set)
    returned_sources: list[SourceReference] = Field(default_factory=list)


class PlanChangeIntent(BaseModel):
    action: IntentAction = IntentAction.ORDINARY_CHAT
    user_message: str = Field(default="", max_length=4000)
    destination: str | None = Field(default=None, max_length=160)
    start_date: date | None = None
    day_count: int | None = Field(default=None, ge=1, le=7)
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


class CoordinatorExplanation(BaseModel):
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
    metadata: dict[str, Any] = Field(default_factory=dict)
