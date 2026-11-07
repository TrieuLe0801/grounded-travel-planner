from __future__ import annotations

from collections.abc import Mapping
from datetime import date
from typing import TypeVar

import pytest
from pydantic import BaseModel

from grounded_travel_planner.agents.chat import ChatAgent
from grounded_travel_planner.agents.coordinator import CoordinatorAgent
from grounded_travel_planner.agents.planner import PlannerAgent
from grounded_travel_planner.contracts import (
    ChatResponse,
    ChatSearchDecision,
    ConversationTurn,
    CoordinatorDecision,
    IntentAction,
    PlanChangeIntent,
    TripRequest,
)
from grounded_travel_planner.i18n import authored_content_language_instruction

T = TypeVar("T", bound=BaseModel)


class PromptModel:
    model_name = "prompt-test-model"

    def __init__(self) -> None:
        self.prompts: list[str] = []

    def generate_structured(
        self,
        prompt: str,
        schema: type[T],
        *,
        metadata: Mapping[str, str] | None = None,
    ) -> T:
        del metadata
        self.prompts.append(prompt)
        if schema is CoordinatorDecision:
            return schema.model_validate(
                {"intent": {"action": IntentAction.ORDINARY_CHAT.value}}
            )
        if schema is ChatSearchDecision:
            return schema.model_validate(
                {"should_search": True, "query": "Hue current information"}
            )
        if schema is ChatResponse:
            return schema.model_validate({"message": "Locale response."})
        raise AssertionError(f"Unexpected model schema: {schema.__name__}")


@pytest.mark.parametrize(
    ("language", "other_language_text"),
    [("en", "Thêm một ngày ở Huế"), ("vi", "Add one day in Hue")],
)
def test_agent_prompts_keep_new_prose_in_selected_language(
    language: str, other_language_text: str
) -> None:
    coordinator_model = PromptModel()
    CoordinatorAgent(coordinator_model).classify(
        other_language_text,
        request=None,
        current_plan=None,
        metadata={},
        session_summary=other_language_text,
        conversation_history=[
            ConversationTurn(role="user", content=other_language_text)
        ],
        language=language,  # type: ignore[arg-type]
    )

    planner_model = PromptModel()
    planner_prompt = PlannerAgent(planner_model)._proposal_prompt(
        intent=PlanChangeIntent(
            action=IntentAction.ADD_PLACE,
            user_message=other_language_text,
            place_name="Hue Imperial City",
        ),
        request=TripRequest(
            destination="Huế",
            start_date=date(2026, 11, 1),
            day_count=1,
        ),
        current_plan=None,
        session_summary=other_language_text,
        sources=[],
        repair_issues=[],
        language=language,  # type: ignore[arg-type]
    )

    chat_model = PromptModel()
    chat = ChatAgent(chat_model)
    decision = chat.decide_search(
        message=other_language_text,
        intent=None,
        candidate=None,
        committed=False,
        current_plan=None,
        issues=[],
        response_hint=other_language_text,
        session_summary=other_language_text,
        metadata={},
        language=language,  # type: ignore[arg-type]
    )
    chat.respond(
        decision=decision,
        message=other_language_text,
        intent=None,
        candidate=None,
        committed=False,
        current_plan=None,
        issues=[],
        response_hint=other_language_text,
        session_summary=other_language_text,
        sources=[],
        search_failed=False,
        metadata={},
        language=language,  # type: ignore[arg-type]
    )

    instruction = authored_content_language_instruction(language)  # type: ignore[arg-type]
    prompts = [
        coordinator_model.prompts[0],
        planner_prompt,
        *chat_model.prompts,
    ]
    assert len(prompts) == 4
    for prompt in prompts:
        assert instruction in prompt
        assert other_language_text in prompt
