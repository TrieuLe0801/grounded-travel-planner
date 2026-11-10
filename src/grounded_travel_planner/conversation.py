"""Bounded, session-only conversation context for runtime handoffs."""

from __future__ import annotations

from grounded_travel_planner.contracts import ConversationTurn

MAX_CONVERSATION_TURNS = 12
MAX_TURN_CONTENT = 2000
MAX_SESSION_SUMMARY = 1200


def bounded_history(turns: list[ConversationTurn]) -> list[ConversationTurn]:
    """Copy the newest turns with deterministic per-turn and total bounds."""

    return [
        turn.model_copy(
            update={
                "content": turn.content[:MAX_TURN_CONTENT],
                "source_references": turn.source_references[:8],
            },
            deep=True,
        )
        for turn in turns[-MAX_CONVERSATION_TURNS:]
    ]


def bounded_summary(value: str | None) -> str:
    """Keep a rolling handoff summary small enough for all role prompts."""

    return (value or "").strip()[:MAX_SESSION_SUMMARY]


def history_prompt(turns: list[ConversationTurn]) -> list[dict[str, str]]:
    """Return only role/content fields for prompt context, never citation snippets."""

    return [
        {"role": turn.role, "content": turn.content[:600]}
        for turn in bounded_history(turns)[-8:]
    ]
