"""User-facing Coordinator agent; it never creates or commits plans."""

from __future__ import annotations

from collections.abc import Mapping

from grounded_travel_planner.contracts import (
    CoordinatorDecision,
    IntentAction,
    PlanChangeIntent,
    SightseeingPlan,
    TripRequest,
    visible_schedule_context,
)
from grounded_travel_planner.providers import StructuredChatModel


class CoordinatorAgent:
    """Classify turns and route mutations; it never writes final responses."""

    role = "coordinator"

    def __init__(self, model: StructuredChatModel) -> None:
        self._model = model

    @property
    def model_name(self) -> str:
        return self._model.model_name

    def classify(
        self,
        message: str,
        *,
        request: TripRequest | None,
        current_plan: SightseeingPlan | None,
        metadata: Mapping[str, str],
    ) -> CoordinatorDecision:
        prompt = (
            "Classify the user turn for a city sightseeing planner. "
            "Use ordinary_chat for conversation that does not request a plan "
            "mutation. Plan mutations are create_trip, add_place, remove_place, "
            "replace_place, reorder_places, change_day, change_time or "
            "extend_trip. For Vietnamese requests such as 'thêm N ngày', use "
            "extend_trip and set day_count_delta to the positive N. For an "
            "absolute requested total, set extend_trip day_count instead. Do not "
            "invent a plan. Understand Vietnamese requests and preserve the "
            "user's place names and diacritics in the structured intent. "
            "Reorder from_index and to_index are zero-based "
            "positions in the chronological itinerary the user sees, sorted by "
            "day, start time, end time, then entry ID. When the user names a "
            "user-facing Stop N, set its internal index to N - 1 using the "
            "current visible itinerary.\n"
            f"User message: {message[:4000]}\n"
            f"Structured request supplied: {request is not None}\n"
            f"Current plan exists: {current_plan is not None}\n"
            f"Current visible itinerary: {visible_schedule_context(current_plan)}"
        )
        decision = self._model.generate_structured(
            prompt,
            CoordinatorDecision,
            metadata=metadata,
        )
        intent = decision.intent
        request_is_valid = bool(
            request is not None
            and request.destination.strip()
            and 1 <= request.day_count <= 7
        )
        if request_is_valid and request is not None and current_plan is None:
            intent = PlanChangeIntent(
                action=IntentAction.CREATE_TRIP,
                user_message=message,
                destination=request.destination,
                start_date=request.start_date,
                day_count=request.day_count,
            )
        requires_planner = intent.mutates_plan
        return decision.model_copy(
            update={"intent": intent, "requires_planner": requires_planner}
        )
