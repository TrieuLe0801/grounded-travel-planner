from __future__ import annotations

from datetime import date, time
from pathlib import Path

from streamlit.testing.v1 import AppTest

from grounded_travel_planner.contracts import (
    AgentResponse,
    PlaceRecommendation,
    ResponseStatus,
    ScheduleEntry,
    SightseeingPlan,
    SourceReference,
    ValidationIssue,
)

APP_PATH = Path(__file__).parent / "fixtures" / "streamlit_fake_app.py"


def _plan() -> SightseeingPlan:
    source = SourceReference(
        source_id="source_ui",
        title="Imperial City Hue visitor information",
        url="https://travel.example/hue/imperial-city",
        snippet="Imperial City Hue visitor information",
        retrieval_query="Imperial City Hue",
    )
    place = PlaceRecommendation(
        place_id="place_ui",
        name="Imperial City",
        description="A sourced historic-place recommendation.",
        source_references=[source],
        visit_minutes_estimate=90,
        travel_minutes_estimate=20,
        opening_hours="unverified",
    )
    return SightseeingPlan(
        plan_id="plan_ui",
        destination="Hue",
        start_date=date(2026, 11, 1),
        day_count=2,
        entries=[
            ScheduleEntry(
                id="entry_ui",
                day_index=1,
                start_time=time(9),
                end_time=time(10, 30),
                place=place,
            )
        ],
        summary="A grounded two-day plan.",
    )


class FakeService:
    def create_session(self) -> str:
        return "thread-ui"

    def handle_turn(self, **kwargs) -> AgentResponse:
        current_plan = kwargs.get("current_plan")
        if "overlap" in kwargs["message"]:
            return AgentResponse(
                status=ResponseStatus.REJECTED,
                message="The previous plan was preserved.",
                current_plan=current_plan,
                validation_issues=[
                    ValidationIssue(
                        code="schedule_overlap",
                        message="The requested edit overlaps another entry.",
                    )
                ],
                graph_steps=8,
                repair_attempts=1,
            )
        return AgentResponse(
            status=ResponseStatus.COMMITTED,
            message="The validated sightseeing plan was updated.",
            current_plan=_plan(),
            committed=True,
            graph_steps=5,
            search_calls=1,
        )


def _page_text(app: AppTest) -> str:
    values: list[str] = []
    for collection in (
        "title",
        "caption",
        "subheader",
        "markdown",
        "success",
        "warning",
        "info",
    ):
        for item in getattr(app, collection):
            value = getattr(item, "value", "")
            if value:
                values.append(str(value))
    return "\n".join(values)


def test_app_loads_without_live_provider_calls() -> None:
    app = AppTest.from_file(APP_PATH).run(timeout=10)

    assert "Grounded Sightseeing Planner" in _page_text(app)
    assert app.text_input[0].label == "Destination or place"
    assert app.number_input[0].value == 2


def test_create_and_failed_chat_edit_render_canonical_plan() -> None:
    app = AppTest.from_file(APP_PATH).run(timeout=10)
    app.text_input[0].set_value("Hue")
    submit = next(button for button in app.button if "Create" in button.label)
    submit.click().run(timeout=10)

    text = _page_text(app)
    assert "validated sightseeing plan was updated" in text
    assert "Current plan · revision 1" in text
    assert "Estimated visit: 90 min" in text
    assert "Opening hours: unverified" in text
    assert "https://travel.example/hue/imperial-city" in text

    app.chat_input[0].set_value("make an overlap").run(timeout=10)
    text = _page_text(app)
    assert "previous plan was preserved" in text
    assert "schedule_overlap" in text
    assert "Current plan · revision 1" in text
