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
from grounded_travel_planner.visuals import PlaceVisual

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
        description="Một địa điểm lịch sử có nguồn tham khảo.",
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
                id="entry_day_two",
                day_index=2,
                start_time=time(8),
                end_time=time(9, 30),
                place=place,
            ),
            ScheduleEntry(
                id="entry_ui",
                day_index=1,
                start_time=time(9),
                end_time=time(10, 30),
                place=place,
            ),
        ],
        summary="Lịch tham quan hai ngày có nguồn tham khảo.",
    )


def _edited_plan() -> SightseeingPlan:
    plan = _plan().model_copy(deep=True)
    plan.revision = 2
    edited_entry = next(entry for entry in plan.entries if entry.id == "entry_ui")
    edited_entry.start_time = time(11)
    edited_entry.end_time = time(12, 30)
    plan.summary = "Imperial City được chuyển sang 11:00."
    return plan


class FakeService:
    def create_session(self) -> str:
        return "thread-ui"

    def handle_turn(self, **kwargs) -> AgentResponse:
        current_plan = kwargs.get("current_plan")
        if "trùng lịch" in kwargs["message"]:
            return AgentResponse(
                status=ResponseStatus.REJECTED,
                message="Lịch trình trước đó đã được giữ nguyên.",
                current_plan=current_plan,
                validation_issues=[
                    ValidationIssue(
                        code="schedule_overlap",
                        message="Thay đổi này trùng thời gian với một điểm khác.",
                    )
                ],
                graph_steps=8,
                repair_attempts=1,
            )
        if current_plan is not None:
            return AgentResponse(
                status=ResponseStatus.COMMITTED,
                message="Đã chuyển Imperial City sang 11:00.",
                current_plan=_edited_plan(),
                committed=True,
                graph_steps=5,
            )
        return AgentResponse(
            status=ResponseStatus.COMMITTED,
            message="Lịch tham quan đã được cập nhật sau khi kiểm tra.",
            current_plan=_plan(),
            committed=True,
            graph_steps=5,
            search_calls=1,
        )


class FakeVisualService:
    """Offline visual metadata for Streamlit AppTest."""

    def resolve(self, plan: SightseeingPlan) -> dict[str, PlaceVisual]:
        return {
            "entry_ui": PlaceVisual(
                place_name="Imperial City",
                image_url="https://upload.wikimedia.org/example/imperial-city.jpg",
                image_page_url="https://commons.wikimedia.org/wiki/File:Imperial_City.jpg",
                image_credit="Example photographer",
                image_license="CC BY-SA 4.0",
                image_alt="Imperial City in Hue",
            ),
            "entry_day_two": PlaceVisual(
                place_name="Imperial City",
            ),
        }


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
        "text",
    ):
        for item in getattr(app, collection):
            value = getattr(item, "value", "")
            if value:
                values.append(str(value))
    return "\n".join(values)


def _imperial_city_start_time(app: AppTest) -> time:
    return next(
        entry.start_time
        for entry in app.session_state.current_plan.entries
        if entry.id == "entry_ui"
    )


def test_app_loads_without_live_provider_calls() -> None:
    app = AppTest.from_file(APP_PATH).run(timeout=10)

    assert "Trợ lý lập lịch tham quan" in _page_text(app)
    assert app.text_input[0].label == "Điểm đến hoặc địa điểm"
    assert app.number_input[0].value == 2


def test_create_and_failed_chat_edit_render_canonical_plan() -> None:
    app = AppTest.from_file(APP_PATH).run(timeout=10)
    app.text_input[0].set_value("Hue")
    submit = next(button for button in app.button if "Tạo lịch" in button.label)
    submit.click().run(timeout=10)

    text = _page_text(app)
    assert "Lịch tham quan đã được cập nhật" in text
    assert "Lịch trình hiện tại · phiên bản 1" in text
    assert "Tham quan ước tính: 90 phút" in text
    assert "Giờ mở cửa: chưa xác minh" in text
    assert "https://travel.example/hue/imperial-city" in text
    assert "Nhắn tin để sửa lịch" in text
    assert "Ảnh: Example photographer · CC BY-SA 4.0" in text
    assert "Chưa có ảnh đã xác minh nguồn và giấy phép." in text
    assert "Bản đồ lộ trình" not in text
    assert "Tọa độ điểm" not in text
    assert app.get("iframe") == []
    assert ("plan_ui", 1) in app.session_state.visuals_by_revision
    assert any("Điểm 1" in item.label for item in app.get("expander"))
    assert any("Điểm 2 · 08:00" in item.label for item in app.get("expander"))

    app.chat_input[0].set_value("Chuyển điểm 1 sang 11:00 ngày 1").run(timeout=10)
    text = _page_text(app)
    assert "Đã chuyển Imperial City sang 11:00" in text
    assert "Lịch trình hiện tại · phiên bản 2" in text
    assert "Imperial City được chuyển sang 11:00" in text
    assert any("11:00–12:30" in item.label for item in app.get("expander"))
    assert app.session_state.current_plan.revision == 2
    assert _imperial_city_start_time(app) == time(11)
    assert ("plan_ui", 2) in app.session_state.visuals_by_revision
    assert ("plan_ui", 1) not in app.session_state.visuals_by_revision

    app.chat_input[0].set_value("Đổi giờ để trùng lịch").run(timeout=10)
    text = _page_text(app)
    assert "Lịch trình trước đó đã được giữ nguyên" in text
    assert "schedule_overlap" in text
    assert "Lịch trình hiện tại · phiên bản 2" in text
    assert any("11:00–12:30" in item.label for item in app.get("expander"))
    assert app.session_state.current_plan.revision == 2
    assert _imperial_city_start_time(app) == time(11)
    assert len(app.session_state.visuals_by_revision) == 1
