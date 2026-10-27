"""Session-only Streamlit itinerary and chat page."""

from __future__ import annotations

from datetime import datetime
from html.parser import HTMLParser
from urllib.parse import urlparse

import streamlit as st
from pydantic import ValidationError

from grounded_travel_planner.contracts import (
    AgentResponse,
    ConversationTurn,
    ResponseStatus,
    SightseeingPlan,
    TripRequest,
    visible_schedule_entries,
)
from grounded_travel_planner.conversation import MAX_CONVERSATION_TURNS
from grounded_travel_planner.i18n import localized_issue_message
from grounded_travel_planner.service import TravelPlannerService
from grounded_travel_planner.ui.turn_runner import (
    PendingTurn,
    TurnCapacityExceeded,
    TurnRunner,
)
from grounded_travel_planner.visuals import (
    MAX_VISUAL_STOPS,
    PlaceVisual,
    VisualEnrichmentService,
)

_TEXT = {
    "vi": {
        "title": "Trợ lý lập lịch tham quan",
        "subtitle": "Coordinator + Planner + Chat · lịch chỉ lưu trong phiên · gợi ý có nguồn tham khảo",
        "language": "Ngôn ngữ",
        "new_trip": "Chuyến đi mới",
        "destination": "Điểm đến hoặc địa điểm",
        "start_date": "Ngày bắt đầu",
        "days": "Số ngày",
        "create": "Tạo lịch tham quan",
        "pending": "Đang xử lý yêu cầu. Bạn có thể chuyển trang và quay lại sau.",
        "busy": "Hệ thống đang xử lý quá nhiều yêu cầu. Vui lòng thử lại sau.",
        "current": "Lịch trình hiện tại",
        "starts": "bắt đầu",
        "photos": "Ảnh được tra cứu cho {count} điểm đầu; các điểm còn lại vẫn có trong lịch trình bên dưới.",
        "day": "Ngày",
        "no_stops": "Chưa có địa điểm nào trong ngày này.",
        "stop": "Điểm",
        "photo_alt": "Ảnh địa điểm {place}",
        "photo": "Ảnh",
        "view_image": "Xem ảnh gốc và giấy phép",
        "photo_missing": "Chưa có ảnh đã xác minh nguồn và giấy phép.",
        "visit": "Tham quan ước tính",
        "travel": "Di chuyển ước tính",
        "minutes": "phút",
        "hours": "Giờ mở cửa",
        "unverified": "chưa xác minh",
        "details": "Chi tiết kiểm tra",
        "steps": "Bước xử lý",
        "searches": "Lần tìm kiếm",
        "repairs": "Lần sửa lại",
        "chat_hint": "Nhắn tin để sửa lịch, ví dụ: 'Chuyển điểm 1 sang 11:00 ngày 1', 'Đổi thứ tự điểm 2 và 3', hoặc 'Thay Imperial City bằng một địa điểm khác'. Số thứ tự điểm được tính trên toàn bộ lịch trình.",
        "chat": "Trò chuyện",
        "chat_input": "Nhắn tin hoặc yêu cầu thay đổi lịch trình",
        "invalid": "Thông tin chuyến đi không hợp lệ",
        "create_message": "Hãy tạo lịch trình tham quan {days} ngày tại {destination}, bắt đầu ngày {date}.",
    },
    "en": {
        "title": "Sightseeing itinerary assistant",
        "subtitle": "Coordinator + Planner + Chat · itinerary stored only in this session · sourced suggestions",
        "language": "Language",
        "new_trip": "New trip",
        "destination": "Destination or place",
        "start_date": "Start date",
        "days": "Days",
        "create": "Create itinerary",
        "pending": "Your request is being processed. You can navigate away and return later.",
        "busy": "The service is handling too many requests. Please try again shortly.",
        "current": "Current itinerary",
        "starts": "starts",
        "photos": "Photos are being looked up for the first {count} stops; remaining stops are still listed below.",
        "day": "Day",
        "no_stops": "No places are scheduled for this day.",
        "stop": "Stop",
        "photo_alt": "Photo of {place}",
        "photo": "Photo",
        "view_image": "View original image and licence",
        "photo_missing": "No photo with verified source and licence is available.",
        "visit": "Estimated visit",
        "travel": "Estimated travel",
        "minutes": "minutes",
        "hours": "Opening hours",
        "unverified": "unverified",
        "details": "Validation details",
        "steps": "Graph steps",
        "searches": "Searches",
        "repairs": "Repair attempts",
        "chat_hint": "Send a message to change the itinerary, for example: 'Move stop 1 to 11:00 on day 1', 'Swap stops 2 and 3', or 'Replace Imperial City with another place'. Stop numbers span the whole itinerary.",
        "chat": "Chat",
        "chat_input": "Message or request an itinerary change",
        "invalid": "Trip details are invalid",
        "create_message": "Create a {days}-day sightseeing itinerary in {destination}, starting on {date}.",
    },
}


def _labels() -> dict[str, str]:
    return _TEXT[st.session_state.get("language", "vi")]


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
    st.session_state.setdefault("session_summary", "")
    st.session_state.setdefault("last_response", None)
    st.session_state.setdefault("visuals_by_revision", {})
    st.session_state.setdefault("pending_turn", None)
    st.session_state.setdefault("language", "vi")


def _reset_session(service: TravelPlannerService) -> None:
    st.session_state.thread_id = service.create_session()
    st.session_state.current_plan = None
    st.session_state.conversation = []
    st.session_state.session_summary = ""
    st.session_state.last_response = None
    st.session_state.visuals_by_revision = {}
    st.session_state.pending_turn = None


def _record_submitted_turn(user_message: str) -> None:
    """Show submitted text at once while its bounded worker is running."""

    st.session_state.conversation.append({"role": "user", "content": user_message})
    st.session_state.conversation = st.session_state.conversation[
        -MAX_CONVERSATION_TURNS:
    ]


def _record_completed_turn(response: AgentResponse) -> None:
    """Commit a worker result once it has returned to the UI session."""

    assistant_turn: dict[str, object] = {
        "role": "assistant",
        "content": response.message,
    }
    if response.source_references:
        assistant_turn["source_references"] = [
            source.model_dump(mode="json") for source in response.source_references
        ]
    st.session_state.conversation.append(assistant_turn)
    st.session_state.conversation = st.session_state.conversation[
        -MAX_CONVERSATION_TURNS:
    ]
    if (
        response.status is ResponseStatus.COMMITTED
        and response.current_plan is not None
    ):
        st.session_state.current_plan = response.current_plan
        st.session_state.visuals_by_revision = {}
    st.session_state.last_response = response
    st.session_state.session_summary = str(
        response.metadata.get("session_summary", st.session_state.session_summary)
    )[:1200]


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
        session_summary=st.session_state.session_summary,
        conversation_history=[
            ConversationTurn(**turn) for turn in st.session_state.conversation[-12:]
        ],
        language=st.session_state.language,
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
    st.info(_labels()["pending"])


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
    labels = _labels()
    st.subheader(f"{labels['current']} · v{plan.revision}")
    st.caption(
        f"{plan.destination} · {labels['starts']} {plan.start_date.isoformat()} · "
        f"{plan.day_count} {labels['days'].lower()}"
    )
    if plan.summary:
        st.write(plan.summary)
    numbered_entries = list(enumerate(visible_schedule_entries(plan), start=1))
    if len(numbered_entries) > MAX_VISUAL_STOPS:
        st.caption(labels["photos"].format(count=MAX_VISUAL_STOPS))
    visuals = _visuals_for_plan(plan, visual_service)
    for day_index in range(1, plan.day_count + 1):
        st.markdown(f"### {labels['day']} {day_index}")
        day_entries = [
            (position, entry)
            for position, entry in numbered_entries
            if entry.day_index == day_index
        ]
        if not day_entries:
            st.caption(labels["no_stops"])
            continue
        for position, entry in day_entries:
            place = entry.place
            with st.expander(
                f"{labels['stop']} {position} · {entry.start_time.strftime('%H:%M')}–"
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
                        alt=visual.image_alt
                        or labels["photo_alt"].format(place=place.name),
                        width="stretch",
                    )
                    st.text(
                        f"{labels['photo']}: {_plain_credit(visual.image_credit)} · "
                        f"{_plain_credit(visual.image_license)}"
                    )
                    st.link_button(labels["view_image"], image_page)
                else:
                    st.caption(labels["photo_missing"])
                st.caption(
                    f"{labels['visit']}: {place.visit_minutes_estimate} {labels['minutes']} · "
                    f"{labels['travel']}: {place.travel_minutes_estimate} {labels['minutes']}"
                )
                hours = (
                    place.opening_hours
                    if place.opening_hours_verified
                    else labels["unverified"]
                )
                st.caption(f"{labels['hours']}: {hours}")
                for source in place.source_references:
                    st.markdown(f"- [{source.title}]({source.url})")


def _render_response(response: AgentResponse) -> None:
    labels = _labels()
    if response.status is ResponseStatus.COMMITTED:
        st.success(response.message)
    elif response.status is ResponseStatus.UNCHANGED:
        st.info(response.message)
    else:
        st.warning(response.message)
    if response.validation_issues:
        with st.expander(labels["details"], expanded=True):
            for issue in response.validation_issues:
                message = localized_issue_message(
                    issue.code,
                    issue.message,
                    st.session_state.get("language", "vi"),
                )
                st.write(f"{issue.code}: {message}")
    st.caption(
        f"{labels['steps']}: {response.graph_steps} · {labels['searches']}: "
        f"{response.search_calls} · {labels['repairs']}: {response.repair_attempts}"
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

    labels = _labels()
    st.set_page_config(page_title=labels["title"], layout="wide")
    st.selectbox(
        labels["language"],
        options=("vi", "en"),
        format_func=lambda value: "Tiếng Việt" if value == "vi" else "English",
        index=0 if st.session_state.language == "vi" else 1,
        key="language",
    )
    labels = _labels()
    st.title(labels["title"])
    st.caption(labels["subtitle"])
    turn_pending = st.session_state.pending_turn is not None
    if st.button(labels["new_trip"], disabled=turn_pending):
        _reset_session(runtime_service)
        st.rerun()

    with st.form("trip_request"):
        destination = st.text_input(
            labels["destination"], placeholder="Huế", disabled=turn_pending
        )
        start_date = st.date_input(
            labels["start_date"],
            value=datetime.now().astimezone().date(),
            disabled=turn_pending,
        )
        day_count = st.number_input(
            labels["days"],
            min_value=1,
            max_value=7,
            value=2,
            step=1,
            disabled=turn_pending,
        )
        submitted = st.form_submit_button(labels["create"], disabled=turn_pending)

    if submitted:
        try:
            request = TripRequest(
                destination=destination,
                start_date=start_date,
                day_count=int(day_count),
            )
            message = labels["create_message"].format(
                days=request.day_count,
                destination=request.destination,
                date=request.start_date.isoformat(),
            )
            _submit_turn(
                turn_runner,
                runtime_service,
                message=message,
                request=request,
            )
            st.rerun()
        except ValidationError:
            st.error(labels["invalid"])
        except TurnCapacityExceeded:
            st.error(labels["busy"])

    response: AgentResponse | None = st.session_state.last_response
    if response is not None:
        _render_response(response)
    plan: SightseeingPlan | None = st.session_state.current_plan
    if plan is not None:
        _render_plan(plan, runtime_visual_service)
        st.caption(labels["chat_hint"])

    if st.session_state.conversation:
        st.subheader(labels["chat"])
        for turn in st.session_state.conversation:
            with st.chat_message(turn["role"]):
                st.write(turn["content"])
                for source in turn.get("source_references", []):
                    st.link_button(source["title"], source["url"])

    user_message = st.chat_input(labels["chat_input"], disabled=turn_pending)
    if user_message:
        try:
            _submit_turn(turn_runner, runtime_service, message=user_message)
            st.rerun()
        except TurnCapacityExceeded:
            st.error(labels["busy"])

    _poll_pending_turn()


if __name__ == "__main__":
    main()
