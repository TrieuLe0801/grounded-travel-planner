"""User-facing Chat agent; graph policy owns any Tavily invocation."""

from __future__ import annotations

from collections.abc import Mapping

from grounded_travel_planner.contracts import (
    ChatResponse,
    ChatSearchDecision,
    PlanCandidate,
    PlanChangeIntent,
    SightseeingPlan,
    SourceReference,
    TavilyToolRequest,
    ValidationIssue,
    visible_schedule_context,
)
from grounded_travel_planner.i18n import Language, response_language_instruction
from grounded_travel_planner.providers import StructuredChatModel


class ChatAgent:
    """Write Vietnamese responses and request, but never run, one tool call."""

    role = "chat"

    def __init__(self, model: StructuredChatModel) -> None:
        self._model = model

    @property
    def model_name(self) -> str:
        return self._model.model_name

    def decide_search(
        self,
        *,
        message: str,
        intent: PlanChangeIntent | None,
        candidate: PlanCandidate | None,
        committed: bool,
        current_plan: SightseeingPlan | None,
        issues: list[ValidationIssue],
        response_hint: str,
        session_summary: str,
        metadata: Mapping[str, str],
        language: Language = "vi",
    ) -> ChatSearchDecision:
        return self._model.generate_structured(
            self._search_decision_prompt(
                message=message,
                intent=intent,
                session_summary=session_summary,
                current_plan=current_plan,
                committed=committed,
                candidate=candidate,
                issues=issues,
                response_hint=response_hint,
                language=language,
            ),
            ChatSearchDecision,
            metadata=metadata,
        )

    def tool_request(self, decision: ChatSearchDecision) -> TavilyToolRequest | None:
        if not decision.should_search or not decision.query.strip():
            return None
        return TavilyToolRequest(
            owner="chat", query=decision.query.strip(), max_results=5
        )

    def respond(
        self,
        *,
        decision: ChatSearchDecision,
        message: str,
        intent: PlanChangeIntent | None,
        candidate: PlanCandidate | None,
        committed: bool,
        current_plan: SightseeingPlan | None,
        issues: list[ValidationIssue],
        response_hint: str,
        session_summary: str,
        sources: list[SourceReference],
        search_failed: bool,
        metadata: Mapping[str, str],
        language: Language = "vi",
    ) -> ChatResponse:
        if not decision.should_search and decision.message.strip():
            return ChatResponse(message=decision.message.strip())
        issue_text = "; ".join(f"{issue.code}: {issue.message}" for issue in issues)
        if search_failed:
            search_status = "unavailable"
        elif sources:
            search_status = "results available"
        elif decision.should_search:
            search_status = "no results"
        else:
            search_status = "not performed"
        committed_context = ""
        if committed and candidate is not None and current_plan is not None:
            committed_context = (
                f"Planner summary: {candidate.summary}\n"
                f"Validated committed plan: {current_plan.model_dump_json()}\n"
            )
        elif not committed and current_plan is not None:
            committed_context = (
                f"Retained prior plan: {current_plan.model_dump_json()}\n"
            )
        prompt = (
            f"Respond entirely in natural {response_language_instruction(language)}. Preserve proper place names, "
            "times and source titles. Never claim an uncommitted candidate was "
            "applied. If validation failed, say the previous plan was preserved. "
            "Mention estimates and unverified hours when relevant.\n"
            f"User message: {message[:4000]}\n"
            f"Coordinator handoff summary: {session_summary[:1200]}\n"
            f"Current visible itinerary: {visible_schedule_context(current_plan)}\n"
            f"Intent: {intent.model_dump_json() if intent else 'unavailable'}\n"
            f"Committed: {committed}\nIssues: {issue_text or 'none'}\n"
            f"{committed_context}Hint: {response_hint[:1000]}\n"
            f"Chat search sources: {[source.model_dump(mode='json') for source in sources]}\n"
            f"Chat search status: {search_status}\n"
            "Ground factual current claims only in supplied Chat search sources. "
            "Never create URLs or citations. When search is unavailable or returns "
            "no usable sources, explicitly say current facts could not be verified."
        )
        response = self._model.generate_structured(
            prompt, ChatResponse, metadata=metadata
        )
        return response

    def _search_decision_prompt(self, **kwargs: object) -> str:
        message = str(kwargs["message"])[:4000]
        intent = kwargs["intent"]
        session_summary = str(kwargs["session_summary"])[:1200]
        current_plan = kwargs["current_plan"]
        committed = bool(kwargs["committed"])
        candidate = kwargs["candidate"]
        issues = kwargs["issues"]
        response_hint = str(kwargs["response_hint"])[:1000]
        language = kwargs.get("language", "vi")
        return (
            f"Write a concise {response_language_instruction(language)} response and decide whether one current web "
            "search is necessary. Search only for factual current travel information "
            "absent from the itinerary or handoff. Do not search casual conversation "
            "or plan edits handled by Planner. With no search, return should_search=false, "
            "empty query and final message. When no search is chosen, do not answer "
            "current factual claims absent from the supplied itinerary or handoff; say "
            "they could not be verified. With search, return true and one concise "
            "query; message may be empty. Never claim an uncommitted candidate was applied.\n"
            f"User message: {message}\n"
            f"Intent: {intent.model_dump_json() if intent else 'unavailable'}\n"
            f"Coordinator handoff summary: {session_summary}\n"
            f"Current visible itinerary: {visible_schedule_context(current_plan)}\n"
            f"Committed: {committed}\n"
            f"Planner summary: {candidate.summary if candidate else ''}\n"
            f"Issues: {[issue.message for issue in issues]}\nHint: {response_hint}"
        )
