from datetime import date, time

from grounded_travel_planner.agents.chat import ChatAgent
from grounded_travel_planner.agents.planner import PlannerAgent
from grounded_travel_planner.contracts import (
    ChatResponse,
    ChatSearchDecision,
    IntentAction,
    PlaceRecommendation,
    PlanCandidate,
    PlanChangeIntent,
    ScheduleEntry,
    SightseeingPlan,
    SourceReference,
    TripRequest,
)


class PromptRecorder:
    model_name = "test-model"

    def __init__(self) -> None:
        self.prompts: list[str] = []

    def generate_structured(self, prompt, schema, *, metadata=None):
        self.prompts.append(prompt)
        if schema is ChatResponse:
            return ChatResponse(message="Đã cập nhật lịch trình.")
        raise AssertionError(f"Unexpected schema: {schema.__name__}")


def sample_plan() -> SightseeingPlan:
    evidence = SourceReference(
        source_id="source-a",
        title="Official visitor guide",
        url="https://travel.example/attraction",
        snippet="UNIQUE_SOURCE_SNIPPET " + "x" * 900,
        retrieval_query="visitor information",
    )
    place = PlaceRecommendation(
        place_id="place-a",
        name="Museum",
        description="A local history museum.",
        source_references=[evidence],
    )
    later = ScheduleEntry(
        id="entry-later",
        day_index=1,
        start_time=time(14),
        end_time=time(15),
        place=place,
    )
    earlier = later.model_copy(
        update={"id": "entry-earlier", "start_time": time(9), "end_time": time(10)}
    )
    return SightseeingPlan(
        plan_id="plan-a",
        destination="Hue",
        start_date=date(2026, 11, 1),
        day_count=1,
        entries=[later, earlier],
        summary="A day in Hue.",
    )


def test_planner_prompt_deduplicates_request_and_prior_source_payload() -> None:
    plan = sample_plan()
    source = plan.entries[0].place.source_references[0]
    prompt = PlannerAgent(PromptRecorder())._proposal_prompt(
        intent=PlanChangeIntent(
            action=IntentAction.REORDER_PLACES,
            user_message="MOVE THIS VERBATIM MESSAGE",
            from_index=0,
            to_index=1,
        ),
        request=TripRequest(
            destination="Hue", start_date=date(2026, 11, 1), day_count=1
        ),
        current_plan=plan,
        session_summary="The user prefers cultural stops.",
        sources=[source],
        repair_issues=[],
        language="vi",
    )

    assert "Trip bounds: destination=Hue; start_date=2026-11-01; day_count=1" in prompt
    assert "MOVE THIS VERBATIM MESSAGE" not in prompt
    assert prompt.count("UNIQUE_SOURCE_SNIPPET") == 2
    assert '"visible_index":0' in prompt
    assert '"visible_index":1' in prompt
    assert '"source_references"' in prompt
    assert prompt.count("https://travel.example/attraction") == 2
    assert '"retrieval_query":"visitor information"' in prompt
    assert "Returned sources: []" in prompt


def test_chat_prompt_uses_visible_plan_summary_without_full_plan_json() -> None:
    model = PromptRecorder()
    plan = sample_plan()
    candidate = PlanCandidate(plan=plan, summary="Đã đổi thứ tự hai điểm.")

    response = ChatAgent(model).respond(
        decision=ChatSearchDecision(should_search=True, query="Hue museum"),
        message="Sắp xếp lại giúp tôi.",
        intent=PlanChangeIntent(action=IntentAction.REORDER_PLACES),
        candidate=candidate,
        committed=True,
        current_plan=plan,
        issues=[],
        response_hint="",
        session_summary="",
        sources=[],
        search_failed=False,
        metadata={"thread_id": "thread-prompt-test"},
        language="vi",
    )

    assert response.message == "Đã cập nhật lịch trình."
    prompt = model.prompts[0]
    assert "Current visible itinerary:" in prompt
    assert "Planner summary: Đã đổi thứ tự hai điểm." in prompt
    assert "Validated committed plan" not in prompt
    assert "UNIQUE_SOURCE_SNIPPET" not in prompt
    assert "at most three concise sentences" in prompt
