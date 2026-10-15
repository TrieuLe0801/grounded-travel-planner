"""Verify that a candidate actually applies the delegated edit intent."""

from __future__ import annotations

from grounded_travel_planner.contracts import (
    IntentAction,
    PlanChangeIntent,
    SightseeingPlan,
    ValidationIssue,
)


def _entry_matches(entry, intent: PlanChangeIntent) -> bool:
    if intent.entry_id:
        return entry.id == intent.entry_id
    if intent.place_name:
        return entry.place.name.casefold() == intent.place_name.casefold()
    return False


def _target_entry(
    plan: SightseeingPlan,
    intent: PlanChangeIntent,
):
    return next(
        (entry for entry in plan.entries if _entry_matches(entry, intent)), None
    )


def _issue(message: str) -> list[ValidationIssue]:
    return [ValidationIssue(code="requested_change_not_applied", message=message)]


def validate_requested_change(
    intent: PlanChangeIntent | None,
    current_plan: SightseeingPlan | None,
    candidate_plan: SightseeingPlan,
) -> list[ValidationIssue]:
    if intent is None or intent.action in {
        IntentAction.ORDINARY_CHAT,
        IntentAction.CREATE_TRIP,
    }:
        return []
    if current_plan is None:
        return _issue("A current plan is required for this edit.")

    if intent.action is IntentAction.ADD_PLACE:
        if not intent.place_name:
            return _issue("The add-place request needs a place name.")
        added = any(
            entry.place.name.casefold() == intent.place_name.casefold()
            for entry in candidate_plan.entries
        )
        if not added or len(candidate_plan.entries) <= len(current_plan.entries):
            return _issue(f"Candidate did not add {intent.place_name}.")

    elif intent.action is IntentAction.REMOVE_PLACE:
        if not (intent.entry_id or intent.place_name):
            return _issue("The remove-place request needs an entry or place.")
        if _target_entry(candidate_plan, intent) is not None:
            return _issue("Candidate still contains the requested removal target.")

    elif intent.action is IntentAction.REPLACE_PLACE:
        if (
            not (intent.entry_id or intent.place_name)
            or not intent.replacement_place_name
        ):
            return _issue("The replace request needs old and replacement places.")
        replacement_present = any(
            entry.place.name.casefold() == intent.replacement_place_name.casefold()
            for entry in candidate_plan.entries
        )
        old_present = _target_entry(candidate_plan, intent) is not None
        if not replacement_present or old_present:
            return _issue("Candidate did not replace the requested place.")

    elif intent.action is IntentAction.REORDER_PLACES:
        if intent.from_index is None or intent.to_index is None:
            return _issue("The reorder request needs source and destination indices.")
        if not 0 <= intent.from_index < len(current_plan.entries):
            return _issue("The reorder source index is outside the current plan.")
        if not 0 <= intent.to_index < len(candidate_plan.entries):
            return _issue("The reorder destination index is outside the candidate.")
        moved_id = current_plan.entries[intent.from_index].id
        if candidate_plan.entries[intent.to_index].id != moved_id:
            return _issue("Candidate did not apply the requested reorder.")

    elif intent.action is IntentAction.CHANGE_DAY:
        if intent.day_index is None or not (intent.entry_id or intent.place_name):
            return _issue("The day-change request needs a target and day.")
        target = _target_entry(candidate_plan, intent)
        if target is None or target.day_index != intent.day_index:
            return _issue("Candidate did not apply the requested day change.")

    elif intent.action is IntentAction.CHANGE_TIME:
        if not (intent.entry_id or intent.place_name):
            return _issue("The time-change request needs a target entry or place.")
        target = _target_entry(candidate_plan, intent)
        if target is None:
            return _issue("Candidate no longer contains the requested time target.")
        if intent.start_time is not None and target.start_time != intent.start_time:
            return _issue("Candidate did not apply the requested start time.")
        if intent.end_time is not None and target.end_time != intent.end_time:
            return _issue("Candidate did not apply the requested end time.")

    return []
