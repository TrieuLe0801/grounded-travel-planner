"""Verify that a candidate actually applies the delegated edit intent."""

from __future__ import annotations

import unicodedata

from grounded_travel_planner.contracts import (
    IntentAction,
    PlanChangeIntent,
    SightseeingPlan,
    ValidationIssue,
    visible_schedule_entries,
)

_PLACE_DESCRIPTORS = {
    "area",
    "ban",
    "cultural",
    "community",
    "hamlet",
    "heritage",
    "lang",
    "site",
    "thon",
    "tourism",
    "village",
}


def _name_tokens(value: str) -> tuple[str, ...]:
    decomposed = unicodedata.normalize("NFKD", value.casefold()).replace("\u0111", "d")
    plain = "".join(char for char in decomposed if not unicodedata.combining(char))
    return tuple("".join(char if char.isalnum() else " " for char in plain).split())


def _place_name_matches(actual: str, requested: str) -> bool:
    """Match spelling variants and generic place descriptors, not other places."""

    actual_tokens = _name_tokens(actual)
    requested_tokens = _name_tokens(requested)
    if not actual_tokens or not requested_tokens:
        return False
    if actual_tokens == requested_tokens:
        return True
    if len(requested_tokens) < 2:
        return False
    if actual_tokens[: len(requested_tokens)] == requested_tokens:
        return set(actual_tokens[len(requested_tokens) :]) <= _PLACE_DESCRIPTORS
    if actual_tokens[-len(requested_tokens) :] == requested_tokens:
        return set(actual_tokens[: -len(requested_tokens)]) <= _PLACE_DESCRIPTORS
    return False


def _entry_matches(entry, intent: PlanChangeIntent) -> bool:
    if intent.entry_id:
        return entry.id == intent.entry_id
    if intent.place_name:
        return _place_name_matches(entry.place.name, intent.place_name)
    return False


def _target_entry(
    plan: SightseeingPlan,
    intent: PlanChangeIntent,
):
    return next(
        (entry for entry in plan.entries if _entry_matches(entry, intent)), None
    )


def _retains_current_places(
    current_plan: SightseeingPlan, candidate_plan: SightseeingPlan
) -> bool:
    remaining = list(candidate_plan.entries)
    for current in current_plan.entries:
        match_index = next(
            (
                index
                for index, candidate in enumerate(remaining)
                if _place_name_matches(candidate.place.name, current.place.name)
                or _place_name_matches(current.place.name, candidate.place.name)
            ),
            None,
        )
        if match_index is None:
            return False
        remaining.pop(match_index)
    return True


def _retains_current_entries(
    current_plan: SightseeingPlan, candidate_plan: SightseeingPlan
) -> bool:
    """Require extensions to retain each existing entry exactly by its stable ID."""

    candidate_by_id = {entry.id: entry for entry in candidate_plan.entries}
    return all(candidate_by_id.get(entry.id) == entry for entry in current_plan.entries)


def _shortens_schedule(
    current_plan: SightseeingPlan,
    candidate_plan: SightseeingPlan,
    target_day_count: int,
) -> bool:
    """Keep stops on retained days and only reuse existing stops elsewhere."""

    current_by_id = {entry.id: entry for entry in current_plan.entries}
    candidate_by_id = {entry.id: entry for entry in candidate_plan.entries}
    if len(candidate_by_id) != len(candidate_plan.entries):
        return False
    if current_plan.entries and not candidate_plan.entries:
        return False
    for entry in current_plan.entries:
        if (
            entry.day_index <= target_day_count
            and candidate_by_id.get(entry.id) != entry
        ):
            return False
    for entry in candidate_plan.entries:
        previous = current_by_id.get(entry.id)
        if (
            previous is None
            or previous.place != entry.place
            or entry.day_index > target_day_count
        ):
            return False
    return True


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

    if intent.action is IntentAction.EXTEND_TRIP:
        target_day_count = intent.day_count
        if target_day_count is None and intent.day_count_delta is not None:
            target_day_count = current_plan.day_count + intent.day_count_delta
        if target_day_count is None or target_day_count <= current_plan.day_count:
            return _issue("The extension must increase the current day count.")
        if candidate_plan.day_count != target_day_count:
            return _issue("Candidate did not apply the requested trip extension.")
        if not _retains_current_entries(current_plan, candidate_plan):
            return _issue("Candidate must preserve existing stops when extending.")
        if not any(
            entry.day_index > current_plan.day_count for entry in candidate_plan.entries
        ):
            return _issue("Candidate needs a grounded entry in the added days.")
        populated_days = {entry.day_index for entry in candidate_plan.entries}
        missing_added_days = (
            set(range(current_plan.day_count + 1, target_day_count + 1))
            - populated_days
        )
        if missing_added_days:
            return _issue("Candidate needs a grounded stop on every added day.")
        return []

    if intent.action is IntentAction.SHORTEN_TRIP:
        target_day_count = intent.day_count
        if target_day_count is None and intent.day_count_delta is not None:
            target_day_count = current_plan.day_count - intent.day_count_delta
        if (
            target_day_count is None
            or not 1 <= target_day_count < current_plan.day_count
        ):
            return _issue(
                "The shortened trip must have fewer days than the current plan."
            )
        if candidate_plan.day_count != target_day_count:
            return _issue("Candidate did not apply the requested shorter duration.")
        if not _shortens_schedule(current_plan, candidate_plan, target_day_count):
            return _issue(
                "Candidate must keep retained-day stops and remove or reschedule "
                "stops from removed days."
            )
        return []

    if intent.action is IntentAction.ADD_PLACE:
        if not intent.place_name:
            return _issue("The add-place request needs a place name.")
        current_matches = sum(
            _place_name_matches(entry.place.name, intent.place_name)
            for entry in current_plan.entries
        )
        candidate_matches = sum(
            _place_name_matches(entry.place.name, intent.place_name)
            for entry in candidate_plan.entries
        )
        if (
            candidate_matches <= current_matches
            or len(candidate_plan.entries) <= len(current_plan.entries)
            or not _retains_current_places(current_plan, candidate_plan)
        ):
            return _issue(f"Candidate did not add {intent.place_name}.")

    elif intent.action is IntentAction.REMOVE_PLACE:
        if not (intent.entry_id or intent.place_name):
            return _issue("The remove-place request needs an entry or place.")
        if _target_entry(current_plan, intent) is None:
            return _issue("The requested removal target is not in the current plan.")
        if _target_entry(candidate_plan, intent) is not None:
            return _issue("Candidate still contains the requested removal target.")

    elif intent.action is IntentAction.REPLACE_PLACE:
        if (
            not (intent.entry_id or intent.place_name)
            or not intent.replacement_place_name
        ):
            return _issue("The replace request needs old and replacement places.")
        if _target_entry(current_plan, intent) is None:
            return _issue(
                "The requested replacement target is not in the current plan."
            )
        replacement_present = any(
            _place_name_matches(entry.place.name, intent.replacement_place_name)
            for entry in candidate_plan.entries
        )
        old_present = _target_entry(candidate_plan, intent) is not None
        if not replacement_present or old_present:
            return _issue("Candidate did not replace the requested place.")

    elif intent.action is IntentAction.REORDER_PLACES:
        if intent.from_index is None or intent.to_index is None:
            return _issue("The reorder request needs source and destination indices.")
        current_visible = visible_schedule_entries(current_plan)
        candidate_visible = visible_schedule_entries(candidate_plan)
        if not 0 <= intent.from_index < len(current_visible):
            return _issue("The reorder source index is outside the visible itinerary.")
        if not 0 <= intent.to_index < len(candidate_visible):
            return _issue("The reorder destination index is outside the candidate.")
        current_ids = [entry.id for entry in current_visible]
        candidate_ids = [entry.id for entry in candidate_visible]
        if len(current_ids) != len(candidate_ids) or set(current_ids) != set(
            candidate_ids
        ):
            return _issue("Candidate must preserve the same stops when reordering.")
        if current_ids == candidate_ids:
            return _issue("Candidate did not change the visible itinerary order.")
        moved_id = current_visible[intent.from_index].id
        moved_index = candidate_ids.index(moved_id)
        if moved_index == intent.from_index:
            return _issue(
                "Candidate did not move the requested stop in visible itinerary."
            )
        if moved_index != intent.to_index:
            return _issue("Candidate did not apply the requested reorder.")

    elif intent.action is IntentAction.CHANGE_DAY:
        if intent.day_index is None or not (intent.entry_id or intent.place_name):
            return _issue("The day-change request needs a target and day.")
        current_target = _target_entry(current_plan, intent)
        if current_target is None:
            return _issue("The requested day-change target is not in the current plan.")
        if current_target.day_index == intent.day_index:
            return _issue("Candidate did not change the requested day.")
        target = _target_entry(candidate_plan, intent)
        if target is None or target.day_index != intent.day_index:
            return _issue("Candidate did not apply the requested day change.")

    elif intent.action is IntentAction.CHANGE_TIME:
        if not (intent.entry_id or intent.place_name):
            return _issue("The time-change request needs a target entry or place.")
        current_target = _target_entry(current_plan, intent)
        if current_target is None:
            return _issue(
                "The requested time-change target is not in the current plan."
            )
        if (
            intent.start_time is not None
            and current_target.start_time == intent.start_time
            and (intent.end_time is None or current_target.end_time == intent.end_time)
        ) or (
            intent.end_time is not None
            and current_target.end_time == intent.end_time
            and intent.start_time is None
        ):
            return _issue("Candidate did not change the requested time.")
        target = _target_entry(candidate_plan, intent)
        if target is None:
            return _issue("Candidate no longer contains the requested time target.")
        if intent.start_time is not None and target.start_time != intent.start_time:
            return _issue("Candidate did not apply the requested start time.")
        if intent.end_time is not None and target.end_time != intent.end_time:
            return _issue("Candidate did not apply the requested end time.")

    return []
