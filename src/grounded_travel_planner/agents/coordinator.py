"""User-facing Coordinator agent; it never creates or commits plans."""

from __future__ import annotations

from collections.abc import Mapping

from grounded_travel_planner.contracts import (
    CoordinatorDecision,
    CoordinatorExplanation,
    IntentAction,
    PlanChangeIntent,
    SightseeingPlan,
    TripRequest,
    ValidationIssue,
)
from grounded_travel_planner.providers import StructuredChatModel


class CoordinatorAgent:
    """Classify turns, delegate mutations and explain the final graph result."""

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
            "replace_place, reorder_places, change_day or change_time. Do not "
            "invent a plan.\n"
            f"User message: {message[:4000]}\n"
            f"Structured request supplied: {request is not None}\n"
            f"Current plan exists: {current_plan is not None}"
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

    def explain(
        self,
        *,
        committed: bool,
        current_plan: SightseeingPlan | None,
        issues: list[ValidationIssue],
        response_hint: str,
        metadata: Mapping[str, str],
    ) -> str:
        issue_text = "; ".join(f"{issue.code}: {issue.message}" for issue in issues)
        prompt = (
            "Explain the validated result to the user concisely. Never claim a "
            "candidate was applied when committed is false. If validation failed, "
            "say the previous plan was preserved. Mention that visit/travel times "
            "are estimates and hours are unverified when relevant.\n"
            f"Committed: {committed}\n"
            f"Current plan exists: {current_plan is not None}\n"
            f"Issues: {issue_text or 'none'}\n"
            f"Hint: {response_hint[:1000]}"
        )
        explanation = self._model.generate_structured(
            prompt,
            CoordinatorExplanation,
            metadata=metadata,
        )
        return explanation.message
