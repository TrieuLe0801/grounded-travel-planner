"""Deterministic, versioned acceptance cases for chat itinerary edits."""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any, TypeVar

import pytest
from pydantic import BaseModel

from grounded_travel_planner.agents import ChatAgent, CoordinatorAgent, PlannerAgent
from grounded_travel_planner.config import RuntimeConfig
from grounded_travel_planner.contracts import (
    ChatResponse,
    CoordinatorDecision,
    PlannerProposal,
    SearchResult,
    SightseeingPlan,
    TripRequest,
    visible_schedule_entries,
)
from grounded_travel_planner.service import TravelPlannerService

T = TypeVar("T", bound=BaseModel)
_EVAL_PATH = Path(__file__).parents[1] / "data" / "eval" / "chat-edit-v1.jsonl"


def _cases() -> list[dict[str, Any]]:
    return [json.loads(line) for line in _EVAL_PATH.read_text().splitlines() if line]


class _ScriptedModel:
    model_name = "gpt-5.5"

    def __init__(self, case: dict[str, Any]) -> None:
        self.case = case
        self.calls: list[str] = []

    def generate_structured(
        self,
        prompt: str,
        schema: type[T],
        *,
        metadata: Mapping[str, str] | None = None,
    ) -> T:
        del prompt, metadata
        self.calls.append(schema.__name__)
        if schema is CoordinatorDecision:
            return schema.model_validate(
                {
                    "intent": self.case["intent"],
                    "requires_planner": self.case["intent"]["action"]
                    != "ordinary_chat",
                    "response_hint": "fixture",
                }
            )
        if schema is ChatResponse:
            return schema.model_validate({"message": "fixture explanation"})
        if schema is PlannerProposal:
            return schema.model_validate(
                {
                    "plan": self.case["candidate_plan"],
                    "summary": "fixture candidate",
                }
            )
        raise AssertionError(f"Unexpected schema: {schema}")


class _FixtureSearch:
    def __init__(self, case: dict[str, Any]) -> None:
        self.results = [
            SearchResult.model_validate(result) for result in case["search_results"]
        ]
        self.calls: list[tuple[str, int, str]] = []

    def search_places(
        self, query: str, *, max_results: int, thread_id: str
    ) -> list[SearchResult]:
        self.calls.append((query, max_results, thread_id))
        return self.results


def _service_for(case: dict[str, Any]) -> tuple[TravelPlannerService, _FixtureSearch]:
    coordinator_model = _ScriptedModel(case)
    planner_model = _ScriptedModel(case)
    search = _FixtureSearch(case)
    config = RuntimeConfig()
    return (
        TravelPlannerService(
            CoordinatorAgent(coordinator_model),
            PlannerAgent(planner_model, search, config),
            ChatAgent(planner_model),
            config=config,
        ),
        search,
    )


@pytest.mark.parametrize("case", _cases(), ids=lambda case: case["id"])
def test_chat_edit_evaluation_case(case: dict[str, Any]) -> None:
    """Exercise observable commit, preservation and citation invariants offline."""
    assert case["version"] == "chat-edit-v1"
    current = SightseeingPlan.model_validate(case["current_plan"])
    original = current.model_copy(deep=True)
    service, search = _service_for(case)

    response = service.handle_turn(
        thread_id=f"eval-{case['id']}",
        message=case["message"],
        current_plan=current,
        request=TripRequest(
            destination=current.destination,
            start_date=current.start_date,
            day_count=current.day_count,
        ),
    )

    expected = case["expected"]
    assert response.status.value == expected["status"]
    assert response.committed is expected["committed"]
    assert response.search_calls == expected["search_calls"]
    assert response.repair_attempts == expected["repair_attempts"]
    assert len(search.calls) == expected["search_calls"]
    assert current == original
    assert response.current_plan is not None
    assert [entry.id for entry in response.current_plan.entries] == expected[
        "entry_ids"
    ]
    if "visible_entry_ids" in expected:
        assert [
            entry.id for entry in visible_schedule_entries(response.current_plan)
        ] == (expected["visible_entry_ids"])
    for field, value in expected.get("plan_values", {}).items():
        assert getattr(response.current_plan, field) == value

    if not response.committed:
        assert response.current_plan == original

    for entry_id, expected_values in expected.get("entry_values", {}).items():
        entry = next(
            entry for entry in response.current_plan.entries if entry.id == entry_id
        )
        for field, value in expected_values.items():
            assert getattr(entry, field) == value

    issue_codes = {issue.code for issue in response.validation_issues}
    assert set(expected.get("issue_codes", [])) <= issue_codes

    returned_urls = {str(result.url) for result in search.results}
    for assertion in expected.get("source_assertions", []):
        entry = next(
            entry
            for entry in response.current_plan.entries
            if entry.id == assertion["entry_id"]
        )
        source_urls = {str(source.url) for source in entry.place.source_references}
        assert assertion["url"] in source_urls
        source = next(
            source
            for source in entry.place.source_references
            if str(source.url) == assertion["url"]
        )
        assert assertion["title_includes"].casefold() in source.title.casefold()
        if assertion.get("returned_by_search"):
            assert assertion["url"] in returned_urls
        if "opening_hours" in assertion:
            assert entry.place.opening_hours == assertion["opening_hours"]
