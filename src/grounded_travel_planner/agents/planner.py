"""Planner agent; it proposes grounded candidates from graph-provided sources."""

from __future__ import annotations

from collections.abc import Mapping

from grounded_travel_planner.contracts import (
    IntentAction,
    PlanCandidate,
    PlanChangeIntent,
    PlannerProposal,
    SightseeingPlan,
    SourceReference,
    TavilyToolRequest,
    TripRequest,
    ValidationIssue,
    visible_schedule_context,
)
from grounded_travel_planner.i18n import Language, response_language_instruction
from grounded_travel_planner.providers import StructuredChatModel
from utils.ids import new_id

_SEARCH_ACTIONS = {
    IntentAction.CREATE_TRIP,
    IntentAction.ADD_PLACE,
    IntentAction.REPLACE_PLACE,
    IntentAction.EXTEND_TRIP,
}


class PlannerAgent:
    """Create or revise a candidate; it never commits canonical state."""

    role = "planner"

    def __init__(self, model: StructuredChatModel) -> None:
        self._model = model

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
        metadata: Mapping[str, str],
        session_summary: str = "",
        repair_issues: list[ValidationIssue] | None = None,
        retained_sources: list[SourceReference] | None = None,
        language: Language = "vi",
    ) -> PlanCandidate:
        # A new-trip request starts a fresh itinerary. Reusing the previous
        # session plan can leak stops scheduled beyond the newly selected day
        # count; _ground_candidate then resets day_count and those stale entries
        # fail schedule validation.
        planning_context = (
            None if intent.action is IntentAction.CREATE_TRIP else current_plan
        )
        sources = self._sources_from_plan(planning_context) if planning_context else []
        for source in retained_sources or []:
            if all(
                str(source.url).rstrip("/") != str(item.url).rstrip("/")
                for item in sources
            ):
                sources.append(source)
        prompt = self._proposal_prompt(
            intent=intent,
            request=request,
            current_plan=planning_context,
            session_summary=session_summary,
            sources=sources,
            repair_issues=repair_issues or [],
            language=language,
        )
        proposed = self._model.generate_structured(
            prompt,
            PlannerProposal,
            metadata=metadata,
        )
        candidate = self._ground_candidate(
            proposed,
            request=request,
            current_plan=planning_context,
            sources=sources,
        )
        return candidate

    def search_query(self, intent: PlanChangeIntent, request: TripRequest) -> str:
        place = intent.replacement_place_name or intent.place_name or "attractions"
        return f"{place} {request.destination} sightseeing official visitor information"

    def tool_request(
        self, intent: PlanChangeIntent, request: TripRequest
    ) -> TavilyToolRequest | None:
        """Request grounded research; the graph tool node performs the call."""

        if not self.requires_search(intent):
            return None
        return TavilyToolRequest(
            owner="planner", query=self.search_query(intent, request), max_results=8
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
        session_summary: str,
        sources: list[SourceReference],
        repair_issues: list[ValidationIssue],
        language: Language,
    ) -> str:
        source_payload = [source.model_dump(mode="json") for source in sources]
        current_payload = (
            current_plan.model_dump(mode="json") if current_plan is not None else None
        )
        issue_payload = [issue.model_dump(mode="json") for issue in repair_issues]
        return (
            "Propose one complete candidate city sightseeing plan. For every "
            "plan-changing request, return the full plan object; never omit it "
            "or return null. Use only source URLs "
            "and source IDs in the supplied search results. Never invent opening "
            "hours. Use opening_hours='unverified' and false unless a supplied "
            "source explicitly supports hours. All visit and travel minute fields "
            "are estimates. Write user-visible plan summaries, place descriptions "
            f"and schedule notes in {response_language_instruction(language)}; preserve proper names and source "
            "titles as supplied. Do not overlap schedule entries. Use 1-based "
            "day_index values and keep every entry within "
            "1 <= day_index <= request.day_count. For create_trip, create a new "
            "itinerary from scratch; never reuse entries from an earlier plan. "
            "For other edits, apply the requested change to the prior "
            "plan when present. Preserve existing entry IDs and stops for "
            "add_place. Name an added place exactly as intent.place_name and a "
            "replacement exactly as intent.replacement_place_name; put alternate "
            "spellings or location descriptors in its description. For "
            "reorder_places, from_index and to_index are "
            "zero-based positions in the chronological itinerary shown to the user, "
            "sorted by day, start time, end time, then entry ID. A reorder must "
            "change that visible chronological order; changing only the entries "
            "list is insufficient.\n"
            "For extend_trip, preserve all existing entries and add a grounded "
            "stop on every newly added day. For shorten_trip, keep entries on "
            "retained days unchanged and remove entries after the new final day. "
            "You may move an existing stop from a removed day into a retained "
            "day when it fits; do not invent a place or change its source data.\n"
            f"Request: {request.model_dump_json()}\n"
            f"Intent: {intent.model_dump_json()}\n"
            f"Coordinator handoff summary: {session_summary[:1200]}\n"
            f"Current plan: {current_payload}\n"
            f"Current visible itinerary: {visible_schedule_context(current_plan)}\n"
            f"Returned sources: {source_payload}\n"
            f"Repair issues: {issue_payload}"
        )

    def _ground_candidate(
        self,
        proposed: PlannerProposal,
        *,
        request: TripRequest,
        current_plan: SightseeingPlan | None,
        sources: list[SourceReference],
    ) -> PlanCandidate:
        allowed = {str(source.url).rstrip("/"): source for source in sources}
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
        return PlanCandidate(
            plan=plan,
            summary=proposed.summary,
            issues=proposed.issues,
            returned_source_urls=set(allowed),
            returned_sources=list(allowed.values()),
        )
