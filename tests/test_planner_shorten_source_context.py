"""Regression coverage for Planner context used by a trip-shortening edit."""

from __future__ import annotations

import json
from datetime import date, time

from grounded_travel_planner.agents.planner import PlannerAgent, _planner_plan_context
from grounded_travel_planner.contracts import (
    IntentAction,
    PlaceRecommendation,
    PlanChangeIntent,
    ScheduleEntry,
    SightseeingPlan,
    SourceReference,
    TripRequest,
)


class _PromptOnlyModel:
    model_name = "prompt-only-model"


def _source(source_id: str, url: str, snippet: str) -> SourceReference:
    return SourceReference(
        source_id=source_id,
        title=f"Source {source_id}",
        url=url,
        snippet=snippet,
        retrieval_query="Hue visitor information",
        supports_opening_hours=True,
    )


def _plan(source: SourceReference) -> SightseeingPlan:
    place = PlaceRecommendation(
        place_id="imperial-city",
        name="Imperial City",
        description="Historic citadel in Hue.",
        source_references=[source],
        opening_hours="08:00-17:30",
        opening_hours_verified=True,
    )
    return SightseeingPlan(
        plan_id="plan-hue",
        destination="Hue",
        start_date=date(2026, 11, 1),
        day_count=2,
        entries=[
            ScheduleEntry(
                id="day-one",
                day_index=1,
                start_time=time(9),
                end_time=time(11),
                place=place,
            )
        ],
        summary="Hue itinerary.",
    )


def test_shorten_context_keeps_exact_entry_sources_without_global_duplication() -> None:
    linked_source = _source(
        "linked-source",
        "https://travel.example/imperial-city",
        "LINKED_SOURCE_SNIPPET",
    )
    retained_source = _source(
        "retained-source",
        "https://travel.example/other",
        "RETAINED_SOURCE_SNIPPET",
    )
    current_plan = _plan(linked_source)

    context = _planner_plan_context(current_plan)
    assert context is not None
    assert context["entries"][0]["place"]["source_references"] == [
        linked_source.model_dump(mode="json")
    ]

    prompt = PlannerAgent(_PromptOnlyModel())._proposal_prompt(
        intent=PlanChangeIntent(action=IntentAction.SHORTEN_TRIP, day_count=1),
        request=TripRequest(
            destination="Hue", start_date=date(2026, 11, 1), day_count=1
        ),
        current_plan=current_plan,
        session_summary="Shorten the plan.",
        sources=[linked_source, retained_source],
        repair_issues=[],
        language="vi",
    )

    returned_sources = json.loads(
        prompt.split("Returned sources: ", 1)[1].split("\nRepair issues:", 1)[0]
    )
    assert returned_sources == [
        {
            "source_id": retained_source.source_id,
            "title": retained_source.title,
            "url": str(retained_source.url),
            "snippet": retained_source.snippet,
            "supports_opening_hours": retained_source.supports_opening_hours,
        }
    ]
    assert "LINKED_SOURCE_SNIPPET" in prompt
    assert "copy every entry on retained days exactly, including nested " in prompt
    assert "only drop entries beyond the new final day" in prompt
