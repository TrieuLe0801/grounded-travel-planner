"""AppTest coverage for session-local asynchronous planning turns."""

from __future__ import annotations

from datetime import date, time
from pathlib import Path
from threading import Event

from streamlit.testing.v1 import AppTest

from grounded_travel_planner.contracts import (
    AgentResponse,
    PlaceRecommendation,
    ResponseStatus,
    ScheduleEntry,
    SightseeingPlan,
    SourceReference,
)
from grounded_travel_planner.visuals import PlaceVisual

APP_PATH = Path(__file__).parent / "fixtures" / "streamlit_gated_async_app.py"


def _completed_plan() -> SightseeingPlan:
    source = SourceReference(
        source_id="async-ui-source",
        title="Imperial City information",
        url="https://travel.example/imperial-city",
        retrieval_query="Imperial City Hue",
    )
    place = PlaceRecommendation(
        place_id="async-ui-place",
        name="Imperial City",
        description="Nguồn tham khảo ngoại tuyến.",
        source_references=[source],
    )
    return SightseeingPlan(
        plan_id="async-ui-plan",
        destination="Hue",
        start_date=date(2026, 11, 1),
        day_count=1,
        entries=[
            ScheduleEntry(
                id="async-ui-entry",
                day_index=1,
                start_time=time(9),
                end_time=time(10, 30),
                place=place,
            )
        ],
    )


class GatedService:
    def __init__(self) -> None:
        self.entered = Event()
        self.release = Event()
        self.call_count = 0

    def reset(self) -> None:
        self.entered.clear()
        self.release.clear()
        self.call_count = 0

    def create_session(self) -> str:
        return "thread-async-ui"

    def handle_turn(self, **kwargs: object) -> AgentResponse:
        self.call_count += 1
        self.entered.set()
        assert self.release.wait(timeout=3)
        return AgentResponse(
            status=ResponseStatus.COMMITTED,
            message="Đã hoàn tất lịch trình nền.",
            current_plan=_completed_plan(),
            committed=True,
            graph_steps=5,
            search_calls=1,
        )


class FakeVisualService:
    def resolve(self, plan: SightseeingPlan) -> dict[str, PlaceVisual]:
        return {}


GATED_SERVICE = GatedService()


def _page_text(app: AppTest) -> str:
    return "\n".join(
        str(getattr(item, "value", ""))
        for collection in ("info", "success", "warning", "caption", "markdown")
        for item in getattr(app, collection)
        if getattr(item, "value", "")
    )


def test_pending_turn_survives_rerun_and_integrates_once() -> None:
    """An AppTest rerun stands in for leaving and returning to this page.

    AppTest does not provide multipage browser navigation, so this verifies the
    shared Streamlit session state through a whole-page rerun instead.
    """

    GATED_SERVICE.reset()
    app = AppTest.from_file(APP_PATH).run(timeout=10)
    app.text_input[0].set_value("Hue")
    submit = next(button for button in app.button if "Tạo lịch" in button.label)
    submit.click().run(timeout=10)

    assert GATED_SERVICE.entered.wait(timeout=1)
    assert GATED_SERVICE.call_count == 1
    assert app.session_state.pending_turn is not None
    assert app.session_state.current_plan is None
    assert len(app.session_state.conversation) == 1
    assert app.chat_input[0].disabled is True
    assert all(button.disabled for button in app.button)

    # This foreground rerun cannot resubmit the captured worker turn.
    app.run(timeout=10)
    assert GATED_SERVICE.call_count == 1
    assert app.session_state.pending_turn is not None
    assert app.session_state.current_plan is None
    assert "Đang xử lý yêu cầu" in _page_text(app)

    pending = app.session_state.pending_turn
    GATED_SERVICE.release.set()
    pending.future.result(timeout=10)
    app.run(timeout=10)

    assert GATED_SERVICE.call_count == 1
    assert app.session_state.pending_turn is None
    assert app.session_state.current_plan is not None
    assert app.session_state.current_plan.plan_id == "async-ui-plan"
    assert len(app.session_state.conversation) == 2
    assert app.session_state.conversation[1] == {
        "role": "assistant",
        "content": "Đã hoàn tất lịch trình nền.",
    }
    assert "Đã hoàn tất lịch trình nền." in _page_text(app)


def test_streamlit_conversation_keeps_only_twelve_messages() -> None:
    GATED_SERVICE.reset()
    GATED_SERVICE.release.set()
    app = AppTest.from_file(APP_PATH).run(timeout=10)
    app.session_state.conversation = [
        {"role": "user", "content": f"old-{index}"} for index in range(12)
    ]

    app.chat_input[0].set_value("new turn").run(timeout=10)
    pending = app.session_state.pending_turn
    if pending is not None:
        pending.future.result(timeout=10)
        app.run(timeout=10)

    assert len(app.session_state.conversation) == 12
    assert app.session_state.conversation[-2] == {
        "role": "user",
        "content": "new turn",
    }
    assert app.session_state.conversation[-1]["role"] == "assistant"
