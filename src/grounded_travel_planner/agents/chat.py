"""User-facing Chat agent; it only writes a response after graph policy runs."""

from __future__ import annotations

from collections.abc import Mapping

from grounded_travel_planner.contracts import (
    ChatResponse,
    PlanChangeIntent,
    SightseeingPlan,
    ValidationIssue,
)
from grounded_travel_planner.providers import StructuredChatModel


class ChatAgent:
    """Write Vietnamese responses without searching, proposing or committing plans."""

    role = "chat"

    def __init__(self, model: StructuredChatModel) -> None:
        self._model = model

    @property
    def model_name(self) -> str:
        return self._model.model_name

    def respond(
        self,
        *,
        message: str,
        intent: PlanChangeIntent | None,
        committed: bool,
        current_plan: SightseeingPlan | None,
        issues: list[ValidationIssue],
        response_hint: str,
        metadata: Mapping[str, str],
    ) -> str:
        issue_text = "; ".join(f"{issue.code}: {issue.message}" for issue in issues)
        prompt = (
            "Respond entirely in natural Vietnamese, regardless of the user's "
            "input language. Preserve proper place names, times and source "
            "titles. Explain the validated result concisely. Never claim a "
            "candidate was applied when committed is false. If validation failed, "
            "say the previous plan was preserved. Mention that visit/travel times "
            "are estimates and hours are unverified when relevant.\n"
            f"User message: {message[:4000]}\n"
            f"Intent: {intent.model_dump_json() if intent else 'unavailable'}\n"
            f"Committed: {committed}\n"
            f"Current plan exists: {current_plan is not None}\n"
            f"Issues: {issue_text or 'none'}\n"
            f"Hint: {response_hint[:1000]}"
        )
        response = self._model.generate_structured(
            prompt,
            ChatResponse,
            metadata=metadata,
        )
        return response.message
