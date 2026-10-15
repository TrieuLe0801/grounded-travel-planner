"""Planner agent; the only runtime role allowed to search or propose plans."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from grounded_travel_planner.config import RuntimeConfig
from grounded_travel_planner.contracts import (
    IntentAction,
    PlanCandidate,
    PlanChangeIntent,
    SearchResult,
    SightseeingPlan,
    SourceReference,
    TripRequest,
    ValidationIssue,
)
from grounded_travel_planner.providers import PlaceSearchProvider, StructuredChatModel
from utils.ids import new_id

_SEARCH_ACTIONS = {
    IntentAction.CREATE_TRIP,
    IntentAction.ADD_PLACE,
    IntentAction.REPLACE_PLACE,
}


@dataclass(frozen=True)
class PlannerResult:
    candidate: PlanCandidate
    search_calls: int


class PlannerAgent:
    """Create or revise a candidate; it never commits canonical state."""

    role = "planner"

    def __init__(
        self,
        model: StructuredChatModel,
        search: PlaceSearchProvider,
        config: RuntimeConfig,
    ) -> None:
        self._model = model
        self._search = search
        self._config = config

    @property
    def model_name(self) -> str:
        return self._model.model_name

    def requires_search(
        self,
        intent: PlanChangeIntent,
        *,
        is_repair: bool = False,
    ) -> bool:
        return intent.action in _SEARCH_ACTIONS and not is_repair

    def propose(
        self,
        *,
        intent: PlanChangeIntent,
        request: TripRequest,
        current_plan: SightseeingPlan | None,
        thread_id: str,
        metadata: Mapping[str, str],
        repair_issues: list[ValidationIssue] | None = None,
        retained_sources: list[SourceReference] | None = None,
    ) -> PlannerResult:
        search_calls = 0
        query = self._search_query(intent, request)
        sources = list(retained_sources or [])
        if not sources and current_plan is not None:
            sources = self._sources_from_plan(current_plan)
        if self.requires_search(intent, is_repair=bool(repair_issues)):
            if self._config.search_call_limit < 1:
                raise RuntimeError("Search call limit prevents grounded research")
            search_results = self._search.search_places(
                query,
                max_results=8,
                thread_id=thread_id,
            )
            search_calls = 1
            new_sources = [self._to_source(item, query) for item in search_results]
            combined = {str(source.url).rstrip("/"): source for source in sources}
            combined.update(
                {str(source.url).rstrip("/"): source for source in new_sources}
            )
            sources = list(combined.values())

        prompt = self._proposal_prompt(
            intent=intent,
            request=request,
            current_plan=current_plan,
            sources=sources,
            repair_issues=repair_issues or [],
        )
        proposed = self._model.generate_structured(
            prompt,
            PlanCandidate,
            metadata=metadata,
        )
        candidate = self._ground_candidate(
            proposed,
            request=request,
            current_plan=current_plan,
            sources=sources,
        )
        return PlannerResult(candidate=candidate, search_calls=search_calls)

    def _search_query(self, intent: PlanChangeIntent, request: TripRequest) -> str:
        place = intent.replacement_place_name or intent.place_name or "attractions"
        return f"{place} {request.destination} sightseeing official visitor information"

    def _to_source(self, result: SearchResult, query: str) -> SourceReference:
        return SourceReference(
            source_id=result.source_id,
            title=result.title,
            url=result.url,
            snippet=result.snippet,
            retrieval_query=query,
            supports_opening_hours=result.supports_opening_hours,
        )

    def _sources_from_plan(self, plan: SightseeingPlan) -> list[SourceReference]:
        unique: dict[str, SourceReference] = {}
        for entry in plan.entries:
            for source in entry.place.source_references:
                unique[str(source.url).rstrip("/")] = source
        return list(unique.values())

    def _proposal_prompt(
        self,
        *,
        intent: PlanChangeIntent,
        request: TripRequest,
        current_plan: SightseeingPlan | None,
        sources: list[SourceReference],
        repair_issues: list[ValidationIssue],
    ) -> str:
        source_payload = [source.model_dump(mode="json") for source in sources]
        current_payload = (
            current_plan.model_dump(mode="json") if current_plan is not None else None
        )
        issue_payload = [issue.model_dump(mode="json") for issue in repair_issues]
        return (
            "Propose one candidate city sightseeing plan. Use only source URLs "
            "and source IDs in the supplied search results. Never invent opening "
            "hours. Use opening_hours='unverified' and false unless a supplied "
            "source explicitly supports hours. All visit and travel minute fields "
            "are estimates. Do not overlap schedule entries and keep day_index "
            "within the requested day count. Apply the requested edit to the prior "
            "plan when present.\n"
            f"Request: {request.model_dump_json()}\n"
            f"Intent: {intent.model_dump_json()}\n"
            f"Current plan: {current_payload}\n"
            f"Returned sources: {source_payload}\n"
            f"Repair issues: {issue_payload}"
        )

    def _ground_candidate(
        self,
        proposed: PlanCandidate,
        *,
        request: TripRequest,
        current_plan: SightseeingPlan | None,
        sources: list[SourceReference],
    ) -> PlanCandidate:
        allowed = {str(source.url).rstrip("/"): source for source in sources}
        if proposed.plan is None:
            return proposed.model_copy(update={"returned_source_urls": set(allowed)})
        grounded_entries = []
        for entry in proposed.plan.entries:
            grounded_refs: list[SourceReference] = []
            for reference in entry.place.source_references:
                actual = allowed.get(str(reference.url).rstrip("/"))
                if actual is not None:
                    grounded_refs.append(actual)
                else:
                    grounded_refs.append(reference)
            hours_supported = any(
                reference.supports_opening_hours for reference in grounded_refs
            )
            place_updates = {"source_references": grounded_refs}
            if not entry.place.opening_hours_verified or not hours_supported:
                place_updates.update(
                    {
                        "opening_hours": "unverified",
                        "opening_hours_verified": False,
                    }
                )
            place = entry.place.model_copy(update=place_updates)
            grounded_entries.append(entry.model_copy(update={"place": place}))
        revision = 1 if current_plan is None else current_plan.revision + 1
        plan_id = current_plan.plan_id if current_plan is not None else new_id("plan")
        plan = proposed.plan.model_copy(
            update={
                "plan_id": plan_id,
                "destination": request.destination,
                "start_date": request.start_date,
                "day_count": request.day_count,
                "entries": grounded_entries,
                "revision": revision,
            }
        )
        return proposed.model_copy(
            update={"plan": plan, "returned_source_urls": set(allowed)}
        )
