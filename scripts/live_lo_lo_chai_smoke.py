"""Live add-place gate using a sourced existing stop and one chat edit."""

from __future__ import annotations

import json
from datetime import date, time

from grounded_travel_planner.adapters.search import TavilyPlaceSearchProvider
from grounded_travel_planner.contracts import (
    PlaceRecommendation,
    ScheduleEntry,
    SightseeingPlan,
    SourceReference,
)
from grounded_travel_planner.policies.change_validation import _place_name_matches
from grounded_travel_planner.service import TravelPlannerService

REQUESTED_PLACE = "L\u00f4 L\u00f4 Ch\u1ea3i"


def main() -> int:
    service = TravelPlannerService.from_environment()
    thread_id = service.create_session()
    query = "Dong Van Old Quarter Ha Giang visitor information"
    results = TavilyPlaceSearchProvider().search_places(
        query, max_results=5, thread_id=thread_id
    )
    seed_result = next(
        (
            result
            for result in results
            if "dong van" in f"{result.title} {result.snippet or ''}".casefold()
        ),
        None,
    )
    if seed_result is None:
        print(json.dumps({"status": "seed_source_unavailable"}))
        return 1

    source = SourceReference(
        source_id=seed_result.source_id,
        title=seed_result.title,
        url=seed_result.url,
        snippet=seed_result.snippet,
        retrieval_query=query,
        supports_opening_hours=seed_result.supports_opening_hours,
    )
    current = SightseeingPlan(
        plan_id="live-add-smoke",
        destination="Ha Giang",
        start_date=date(2026, 11, 1),
        day_count=2,
        revision=1,
        entries=[
            ScheduleEntry(
                id="dong-van-old-quarter",
                day_index=1,
                start_time=time(9),
                end_time=time(10, 30),
                place=PlaceRecommendation(
                    place_id="dong-van-old-quarter",
                    name="Dong Van Old Quarter",
                    description="An existing sourced stop in the smoke plan.",
                    source_references=[source],
                    opening_hours="unverified",
                ),
            )
        ],
    )
    response = service.handle_turn(
        thread_id=thread_id,
        message=f"Hãy thêm {REQUESTED_PLACE} vào ngày 2 của lịch trình.",
        current_plan=current,
    )
    updated = response.current_plan
    names = [entry.place.name for entry in updated.entries] if updated else []
    added = any(_place_name_matches(name, REQUESTED_PLACE) for name in names)
    old_stop_preserved = "Dong Van Old Quarter" in names
    revision_advanced = updated is not None and updated.revision == 2
    success = bool(
        response.committed and added and old_stop_preserved and revision_advanced
    )
    print(
        json.dumps(
            {
                "status": response.status.value,
                "committed": response.committed,
                "intent_action": (
                    response.intent.action.value if response.intent else None
                ),
                "intent_place": response.intent.place_name if response.intent else None,
                "assistant_message": response.message,
                "entry_names": names,
                "revision": updated.revision if updated else None,
                "added_requested_place": added,
                "old_stop_preserved": old_stop_preserved,
                "graph_steps": response.graph_steps,
                "search_calls": response.search_calls,
                "repair_attempts": response.repair_attempts,
                "issue_codes": [issue.code for issue in response.validation_issues],
                "verified": success,
            },
            ensure_ascii=True,
            indent=2,
        )
    )
    return 0 if success else 1


if __name__ == "__main__":
    raise SystemExit(main())
