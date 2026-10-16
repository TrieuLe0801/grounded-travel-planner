"""One-page, session-only Streamlit adapter."""

from __future__ import annotations

from datetime import datetime

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


@st.cache_resource
def get_service() -> TravelPlannerService:
    """Cache provider clients only; the service stores no user plan state."""

    return TravelPlannerService.from_environment()


def _ensure_session(service: TravelPlannerService) -> None:
    if "thread_id" not in st.session_state:
        st.session_state.thread_id = service.create_session()
    st.session_state.setdefault("current_plan", None)
    st.session_state.setdefault("conversation", [])
    st.session_state.setdefault("last_response", None)


def _reset_session(service: TravelPlannerService) -> None:
    st.session_state.thread_id = service.create_session()
    st.session_state.current_plan = None
    st.session_state.conversation = []
    st.session_state.last_response = None


def _record_turn(user_message: str, response: AgentResponse) -> None:
    st.session_state.conversation.append({"role": "user", "content": user_message})
    st.session_state.conversation.append(
        {"role": "assistant", "content": response.message}
    )
    if (
        response.status is ResponseStatus.COMMITTED
        and response.current_plan is not None
    ):
        st.session_state.current_plan = response.current_plan
    st.session_state.last_response = response


def _render_plan(plan: SightseeingPlan) -> None:
    st.subheader(f"Lịch trình hiện tại · phiên bản {plan.revision}")
    st.caption(
        f"{plan.destination} · bắt đầu {plan.start_date.isoformat()} · "
        f"{plan.day_count} ngày"
    )
    if plan.summary:
        st.write(plan.summary)
    numbered_entries = list(enumerate(visible_schedule_entries(plan), start=1))
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


def main(service: TravelPlannerService | None = None) -> None:
    runtime_service = service or get_service()
    _ensure_session(runtime_service)

    st.set_page_config(page_title="Trợ lý lập lịch tham quan", layout="wide")
    st.title("Trợ lý lập lịch tham quan")
    st.caption(
        "Coordinator + Planner · lịch chỉ lưu trong phiên · gợi ý có nguồn tham khảo"
    )
    if st.button("Chuyến đi mới"):
        _reset_session(runtime_service)
        st.rerun()

    with st.form("trip_request"):
        destination = st.text_input("Điểm đến hoặc địa điểm", placeholder="Huế")
        start_date = st.date_input(
            "Ngày bắt đầu",
            value=datetime.now().astimezone().date(),
        )
        day_count = st.number_input(
            "Số ngày", min_value=1, max_value=7, value=2, step=1
        )
        submitted = st.form_submit_button("Tạo lịch tham quan")

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
            response = runtime_service.handle_turn(
                thread_id=st.session_state.thread_id,
                message=message,
                current_plan=st.session_state.current_plan,
                request=request,
            )
            _record_turn(message, response)
        except ValidationError as error:
            st.error(f"Thông tin chuyến đi không hợp lệ: {error.errors()[0]['msg']}")

    response: AgentResponse | None = st.session_state.last_response
    if response is not None:
        _render_response(response)
    plan: SightseeingPlan | None = st.session_state.current_plan
    if plan is not None:
        _render_plan(plan)
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

    user_message = st.chat_input("Nhắn tin hoặc yêu cầu thay đổi lịch trình")
    if user_message:
        response = runtime_service.handle_turn(
            thread_id=st.session_state.thread_id,
            message=user_message,
            current_plan=st.session_state.current_plan,
        )
        _record_turn(user_message, response)
        st.rerun()


if __name__ == "__main__":
    main()
