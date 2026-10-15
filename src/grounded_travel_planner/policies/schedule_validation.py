"""Schedule range, overlap and sourced-hours checks."""

from __future__ import annotations

from datetime import time
from itertools import pairwise

from grounded_travel_planner.contracts import SightseeingPlan, ValidationIssue


def _parse_daily_window(value: str) -> tuple[time, time] | None:
    try:
        opening, closing = (part.strip() for part in value.split("-", 1))
        return time.fromisoformat(opening), time.fromisoformat(closing)
    except (TypeError, ValueError):
        return None


def validate_schedule(plan: SightseeingPlan) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    entries_by_day: dict[int, list] = {}
    for entry in plan.entries:
        if entry.day_index < 1 or entry.day_index > plan.day_count:
            issues.append(
                ValidationIssue(
                    code="entry_day_out_of_range",
                    message=f"Entry {entry.id} is outside the selected trip days.",
                    entry_id=entry.id,
                )
            )
        if entry.start_time >= entry.end_time:
            issues.append(
                ValidationIssue(
                    code="invalid_entry_time",
                    message=f"Entry {entry.id} must start before it ends.",
                    entry_id=entry.id,
                )
            )
        if entry.place.opening_hours_verified and entry.place.opening_hours:
            window = _parse_daily_window(entry.place.opening_hours)
            if window is None:
                issues.append(
                    ValidationIssue(
                        code="invalid_opening_hours",
                        message=(
                            f"Verified hours for {entry.place.name} must use "
                            "HH:MM-HH:MM."
                        ),
                        entry_id=entry.id,
                    )
                )
            elif entry.start_time < window[0] or entry.end_time > window[1]:
                issues.append(
                    ValidationIssue(
                        code="opening_hours_conflict",
                        message=f"Entry {entry.id} conflicts with known opening hours.",
                        entry_id=entry.id,
                    )
                )
        entries_by_day.setdefault(entry.day_index, []).append(entry)

    for entries in entries_by_day.values():
        ordered = sorted(entries, key=lambda item: (item.start_time, item.end_time))
        for previous, current in pairwise(ordered):
            if current.start_time < previous.end_time:
                issues.append(
                    ValidationIssue(
                        code="schedule_overlap",
                        message=(
                            f"Entries {previous.id} and {current.id} overlap on "
                            f"day {current.day_index}."
                        ),
                        entry_id=current.id,
                    )
                )
    return issues
