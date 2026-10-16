"""Explicit two-turn live gate for creating and then editing a plan by chat."""

from __future__ import annotations

import json
from datetime import date

from grounded_travel_planner.contracts import TripRequest
from grounded_travel_planner.service import TravelPlannerService


def main() -> int:
    service = TravelPlannerService.from_environment()
    thread_id = service.create_session()
    created = service.handle_turn(
        thread_id=thread_id,
        message="Create a one-day sourced sightseeing plan for Hue.",
        request=TripRequest(
            destination="Hue", start_date=date(2026, 11, 1), day_count=1
        ),
    )
    original = created.current_plan
    if not created.committed or original is None or not original.entries:
        print(
            json.dumps(
                {
                    "create_status": created.status.value,
                    "create_issue_codes": [
                        issue.code for issue in created.validation_issues
                    ],
                    "edit_status": "not_attempted",
                },
                indent=2,
            )
        )
        return 1

    target = original.entries[0]
    edited = service.handle_turn(
        thread_id=thread_id,
        message=(
            f"Remove {target.place.name} (entry ID {target.id}) from my itinerary. "
            "Keep the other visits."
        ),
        current_plan=original,
    )
    updated = edited.current_plan
    removed = updated is not None and all(
        entry.id != target.id for entry in updated.entries
    )
    preserved_other_entries = updated is not None and {
        entry.id for entry in updated.entries
    } == {entry.id for entry in original.entries if entry.id != target.id}
    revision_advanced = (
        updated is not None and updated.revision == original.revision + 1
    )
    same_thread = edited.metadata.get("thread_id") == thread_id
    within_limits = (
        edited.graph_steps <= service.config.graph_step_limit
        and edited.search_calls <= service.config.search_call_limit
        and edited.repair_attempts <= service.config.repair_attempt_limit
    )
    success = bool(
        edited.committed
        and removed
        and preserved_other_entries
        and revision_advanced
        and same_thread
        and within_limits
    )
    print(
        json.dumps(
            {
                "create_status": created.status.value,
                "create_revision": original.revision,
                "create_entries": len(original.entries),
                "edit_status": edited.status.value,
                "edit_committed": edited.committed,
                "edit_revision": updated.revision if updated else None,
                "edit_entries": len(updated.entries) if updated else None,
                "target_removed": removed,
                "other_entries_preserved": preserved_other_entries,
                "edit_graph_steps": edited.graph_steps,
                "edit_search_calls": edited.search_calls,
                "edit_repair_attempts": edited.repair_attempts,
                "edit_issue_codes": [issue.code for issue in edited.validation_issues],
                "same_thread": same_thread,
                "within_limits": within_limits,
                "verified": success,
            },
            indent=2,
        )
    )
    return 0 if success else 1


if __name__ == "__main__":
    raise SystemExit(main())
