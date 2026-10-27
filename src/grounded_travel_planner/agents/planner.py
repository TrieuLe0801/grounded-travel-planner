"""Planner agent; it proposes grounded candidates from graph-provided sources."""

from __future__ import annotations

import json
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
    visible_schedule_entries,
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
        if intent.action is IntentAction.SHORTEN_TRIP:
            return self._shorten_candidate(
                request=request,
                current_plan=current_plan,
                language=language,
            )
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

    def _shorten_candidate(
        self,
        *,
        request: TripRequest,
        current_plan: SightseeingPlan | None,
        language: Language,
    ) -> PlanCandidate:
        """Build the deterministic shortening proposal inside the Planner role.

        Reducing a trip only removes stops on days beyond the validated target.
        It needs no model-authored content or new research, and copying retained
        entries directly preserves their exact schedule, place, and source data.
        """

        if current_plan is None or request.day_count >= current_plan.day_count:
            raise ValueError("A valid shorter current plan is required.")
        entries = [
            entry
            for entry in current_plan.entries
            if entry.day_index <= request.day_count
        ]
        removed_count = len(current_plan.entries) - len(entries)
        if language == "vi":
            summary = (
                f"Đã rút lịch trình còn {request.day_count} ngày; "
                f"giữ nguyên các điểm trong ngày còn lại và bỏ {removed_count} điểm "
                "thuộc ngày đã xóa."
            )
        else:
            summary = (
                f"Shortened the itinerary to {request.day_count} days, preserving "
                f"retained-day stops and removing {removed_count} stops from "
                "dropped days."
            )
        plan = current_plan.model_copy(
            update={
                "day_count": request.day_count,
                "entries": entries,
                "summary": summary,
                "revision": current_plan.revision + 1,
            }
        )
        sources = self._sources_from_plan(plan)
        return PlanCandidate(
            plan=plan,
            summary=summary,
            returned_source_urls={str(source.url) for source in sources},
            returned_sources=sources,
        )

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
        current_payload = _planner_plan_context(current_plan)
        issue_payload = [issue.model_dump(mode="json") for issue in repair_issues]
        plan_source_urls = _plan_source_urls(current_plan)
        source_payload = [
            {
                "source_id": source.source_id,
                "title": source.title,
                "url": str(source.url),
                "snippet": source.snippet,
                "supports_opening_hours": source.supports_opening_hours,
            }
            for source in sources
            if str(source.url).rstrip("/") not in plan_source_urls
        ]
        return (
            "Propose one complete candidate city sightseeing plan. For every "
            "plan-changing request, return the full plan object; never omit it "
            "or return null. Use only source URLs "
            "and source IDs in the supplied sources. Never invent opening "
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
            "Keep summaries to one sentence, place descriptions to two short "
            "sentences, and schedule notes brief. For extend_trip, preserve all existing entries and add a grounded "
            "stop on every newly added day. For shorten_trip, copy every entry "
            "on retained days exactly, including nested source_references and "
            "all source data; only drop entries beyond the new final day.\n"
            f"Trip bounds: destination={request.destination}; start_date={request.start_date}; day_count={request.day_count}\n"
            f"Intent: {intent.model_dump_json(exclude={'user_message'}, exclude_none=True)}\n"
            f"Coordinator handoff summary: {session_summary[:1200]}\n"
            f"Current plan (chronological; visible_index is the user-facing stop number): {json.dumps(current_payload, ensure_ascii=False, separators=(',', ':'))}\n"
            "Returned sources: "
            f"{json.dumps(source_payload, ensure_ascii=False, separators=(',', ':'))}\n"
            "Repair issues: "
            f"{json.dumps(issue_payload, ensure_ascii=False, separators=(',', ':'))}"
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


def _plan_source_urls(plan: SightseeingPlan | None) -> set[str]:
    """Return normalized URLs already attached to entries in the current plan."""

    if plan is None:
        return set()
    return {
        str(source.url).rstrip("/")
        for entry in plan.entries
        for source in entry.place.source_references
    }


def _planner_plan_context(plan: SightseeingPlan | None) -> dict[str, object] | None:
    """Serialize the prior plan once, in visible order, with exact entry evidence."""

    if plan is None:
        return None
    payload = plan.model_dump(mode="json", exclude={"entries"})
    entries: list[dict[str, object]] = []
    for index, entry in enumerate(visible_schedule_entries(plan)):
        item = entry.model_dump(mode="json")
        item["visible_index"] = index
        entries.append(item)
    payload["entries"] = entries
    return payload
