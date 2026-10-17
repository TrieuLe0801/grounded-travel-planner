"""Session-only Streamlit itinerary and chat page."""

from __future__ import annotations

from datetime import datetime
from html.parser import HTMLParser
from urllib.parse import urlparse

import streamlit as st
from pydantic import ValidationError

from grounded_travel_planner.contracts import (
    AgentResponse,
    ResponseStatus,
    SightseeingPlan,
    TripRequest,
    visible_schedule_entries,
)
from grounded_travel_planner.service import TravelPlannerService
from grounded_travel_planner.ui.turn_runner import PendingTurn, TurnRunner
from grounded_travel_planner.visuals import (
    MAX_VISUAL_STOPS,
    PlaceVisual,
    VisualEnrichmentService,
)


class _CreditTextParser(HTMLParser):
    """Extract readable creator text from Wikimedia's HTML metadata."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []

    def handle_data(self, data: str) -> None:
        self.parts.append(data)


def _plain_credit(value: str) -> str:
    parser = _CreditTextParser()
    parser.feed(value)
    return " ".join(" ".join(parser.parts).split())[:300]


@st.cache_resource
def get_service() -> TravelPlannerService:
    """Cache provider clients only; the service stores no user plan state."""

    return TravelPlannerService.from_environment()


@st.cache_resource
def get_visual_service() -> VisualEnrichmentService:
    """Cache the client; per-plan view state stays in this UI session."""

    return VisualEnrichmentService.from_environment()


@st.cache_resource
def get_turn_runner() -> TurnRunner:
    """Share a bounded worker pool; pending turns remain session-local."""

    return TurnRunner()


def _ensure_session(service: TravelPlannerService) -> None:
    if "thread_id" not in st.session_state:
        st.session_state.thread_id = service.create_session()
    st.session_state.setdefault("current_plan", None)
    st.session_state.setdefault("conversation", [])
    st.session_state.setdefault("last_response", None)
    st.session_state.setdefault("visuals_by_revision", {})
    st.session_state.setdefault("pending_turn", None)


def _reset_session(service: TravelPlannerService) -> None:
    st.session_state.thread_id = service.create_session()
    st.session_state.current_plan = None
    st.session_state.conversation = []
    st.session_state.last_response = None
    st.session_state.visuals_by_revision = {}
    st.session_state.pending_turn = None


def _record_submitted_turn(user_message: str) -> None:
    """Show submitted text at once while its bounded worker is running."""

    st.session_state.conversation.append({"role": "user", "content": user_message})


def _record_completed_turn(response: AgentResponse) -> None:
    """Commit a worker result once it has returned to the UI session."""

    st.session_state.conversation.append(
        {"role": "assistant", "content": response.message}
    )
    if (
        response.status is ResponseStatus.COMMITTED
        and response.current_plan is not None
    ):
        st.session_state.current_plan = response.current_plan
        st.session_state.visuals_by_revision = {}
    st.session_state.last_response = response


def _submit_turn(
    runner: TurnRunner,
    service: TravelPlannerService,
    *,
    message: str,
    request: TripRequest | None = None,
) -> None:
    """Capture the canonical plan and enqueue exactly one session turn."""

    if st.session_state.pending_turn is not None:
        return
    st.session_state.pending_turn = runner.submit(
        service,
        thread_id=st.session_state.thread_id,
        message=message,
        current_plan=st.session_state.current_plan,
        request=request,
    )
    _record_submitted_turn(message)


def _collect_completed_turn() -> bool:
    """Integrate one completed result and report whether state changed."""

    pending: PendingTurn | None = st.session_state.pending_turn
    if pending is None:
        return False
    response = TurnRunner.collect(pending)
    if response is None:
        return False
    active: PendingTurn | None = st.session_state.pending_turn
    if active is None or active.token != pending.token:
        return False
    st.session_state.pending_turn = None
    _record_completed_turn(response)
    return True


@st.fragment(run_every=1.0)
def _poll_pending_turn() -> None:
    """Integrate a completed worker result without blocking page navigation."""

    if _collect_completed_turn():
        st.rerun()
    if st.session_state.pending_turn is None:
        return
    st.info("Đang xử lý yêu cầu. Bạn có thể chuyển trang và quay lại sau.")


def _safe_external_url(value: str | None) -> str | None:
    if not value:
        return None
    parsed = urlparse(value)
    if parsed.scheme == "https" and parsed.hostname and not parsed.username:
        return value
    return None


def _visuals_for_plan(
    plan: SightseeingPlan, visual_service: VisualEnrichmentService
) -> dict[str, PlaceVisual]:
    """Enrich only once per plan revision inside this browser session."""

    key = (plan.plan_id, plan.revision)
    cache = st.session_state.visuals_by_revision
    if key not in cache:
        try:
            cache[key] = visual_service.resolve(plan)
        except (OSError, ValueError, RuntimeError):
            cache[key] = {}
    return cache[key]


def _render_plan(
    plan: SightseeingPlan, visual_service: VisualEnrichmentService
) -> None:
    st.subheader(f"Lịch trình hiện tại · phiên bản {plan.revision}")
    st.caption(
        f"{plan.destination} · bắt đầu {plan.start_date.isoformat()} · "
        f"{plan.day_count} ngày"
    )
    if plan.summary:
        st.write(plan.summary)
    numbered_entries = list(enumerate(visible_schedule_entries(plan), start=1))
    if len(numbered_entries) > MAX_VISUAL_STOPS:
        st.caption(
            f"Ảnh được tra cứu cho {MAX_VISUAL_STOPS} điểm đầu; "
            "các điểm còn lại vẫn có trong lịch trình bên dưới."
        )
    visuals = _visuals_for_plan(plan, visual_service)
    for day_index in range(1, plan.day_count + 1):
        st.markdown(f"### Ngày {day_index}")
        day_entries = [
            (position, entry)
            for position, entry in numbered_entries
            if entry.day_index == day_index
        ]
        if not day_entries:
            st.caption("Chưa có địa điểm nào trong ngày này.")
            continue
        for position, entry in day_entries:
            place = entry.place
            with st.expander(
                f"Điểm {position} · {entry.start_time.strftime('%H:%M')}–"
                f"{entry.end_time.strftime('%H:%M')} · {place.name}",
                expanded=True,
            ):
                st.write(place.description)
                visual = visuals.get(entry.id)
                image_url = _safe_external_url(visual.image_url) if visual else None
                image_page = (
                    _safe_external_url(visual.image_page_url) if visual else None
                )
                if (
                    image_url
                    and image_page
                    and visual.image_credit
                    and visual.image_license
                ):
                    st.image(
                        image_url,
                        alt=visual.image_alt or f"Ảnh địa điểm {place.name}",
                        width="stretch",
                    )
                    st.text(
                        f"Ảnh: {_plain_credit(visual.image_credit)} · "
                        f"{_plain_credit(visual.image_license)}"
                    )
                    st.link_button("Xem ảnh gốc và giấy phép", image_page)
                else:
                    st.caption("Chưa có ảnh đã xác minh nguồn và giấy phép.")
                st.caption(
                    f"Tham quan ước tính: {place.visit_minutes_estimate} phút · "
                    f"Di chuyển ước tính: {place.travel_minutes_estimate} phút"
                )
                hours = (
                    place.opening_hours
                    if place.opening_hours_verified
                    else "chưa xác minh"
                )
                st.caption(f"Giờ mở cửa: {hours}")
                for source in place.source_references:
                    st.markdown(f"- [{source.title}]({source.url})")


def _render_response(response: AgentResponse) -> None:
    if response.status is ResponseStatus.COMMITTED:
        st.success(response.message)
    elif response.status is ResponseStatus.UNCHANGED:
        st.info(response.message)
    else:
        st.warning(response.message)
    if response.validation_issues:
        with st.expander("Chi tiết kiểm tra", expanded=True):
            for issue in response.validation_issues:
                st.write(f"{issue.code}: {issue.message}")
    st.caption(
        f"Bước xử lý: {response.graph_steps} · Lần tìm kiếm: "
        f"{response.search_calls} · Lần sửa lại: {response.repair_attempts}"
    )


def main(
    service: TravelPlannerService | None = None,
    visual_service: VisualEnrichmentService | None = None,
) -> None:
    runtime_service = service or get_service()
    runtime_visual_service = visual_service or get_visual_service()
    turn_runner = get_turn_runner()
    _ensure_session(runtime_service)
    if _collect_completed_turn():
        st.rerun()

    st.set_page_config(page_title="Trợ lý lập lịch tham quan", layout="wide")
    st.title("Trợ lý lập lịch tham quan")
    st.caption(
        "Coordinator + Planner + Chat · lịch chỉ lưu trong phiên · "
        "gợi ý có nguồn tham khảo"
    )
    turn_pending = st.session_state.pending_turn is not None
    if st.button("Chuyến đi mới", disabled=turn_pending):
        _reset_session(runtime_service)
        st.rerun()

    with st.form("trip_request"):
        destination = st.text_input(
            "Điểm đến hoặc địa điểm", placeholder="Huế", disabled=turn_pending
        )
        start_date = st.date_input(
            "Ngày bắt đầu",
            value=datetime.now().astimezone().date(),
            disabled=turn_pending,
        )
        day_count = st.number_input(
            "Số ngày",
            min_value=1,
            max_value=7,
            value=2,
            step=1,
            disabled=turn_pending,
        )
        submitted = st.form_submit_button("Tạo lịch tham quan", disabled=turn_pending)

    if submitted:
        try:
            request = TripRequest(
                destination=destination,
                start_date=start_date,
                day_count=int(day_count),
            )
            message = (
                f"Hãy tạo lịch trình tham quan {request.day_count} ngày tại "
                f"{request.destination}, bắt đầu ngày {request.start_date.isoformat()}."
            )
            _submit_turn(
                turn_runner,
                runtime_service,
                message=message,
                request=request,
            )
            st.rerun()
        except ValidationError as error:
            st.error(f"Thông tin chuyến đi không hợp lệ: {error.errors()[0]['msg']}")

    response: AgentResponse | None = st.session_state.last_response
    if response is not None:
        _render_response(response)
    plan: SightseeingPlan | None = st.session_state.current_plan
    if plan is not None:
        _render_plan(plan, runtime_visual_service)
        st.caption(
            "Nhắn tin để sửa lịch, ví dụ: 'Chuyển điểm 1 sang 11:00 ngày 1', "
            "'Đổi thứ tự điểm 2 và 3', hoặc 'Thay Imperial City bằng một địa "
            "điểm khác'. Số thứ tự điểm được tính trên toàn bộ lịch trình."
        )

    if st.session_state.conversation:
        st.subheader("Trò chuyện")
        for turn in st.session_state.conversation:
            with st.chat_message(turn["role"]):
                st.write(turn["content"])

    user_message = st.chat_input(
        "Nhắn tin hoặc yêu cầu thay đổi lịch trình", disabled=turn_pending
    )
    if user_message:
        _submit_turn(turn_runner, runtime_service, message=user_message)
        st.rerun()

    _poll_pending_turn()


if __name__ == "__main__":
    main()
