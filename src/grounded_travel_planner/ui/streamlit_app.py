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
    st.session_state.current_plan = response.current_plan
    st.session_state.last_response = response


def _render_plan(plan: SightseeingPlan) -> None:
    st.subheader(f"Current plan · revision {plan.revision}")
    st.caption(
        f"{plan.destination} · starts {plan.start_date.isoformat()} · "
        f"{plan.day_count} day(s)"
    )
    if plan.summary:
        st.write(plan.summary)
    for day_index in range(1, plan.day_count + 1):
        st.markdown(f"### Day {day_index}")
        day_entries = [entry for entry in plan.entries if entry.day_index == day_index]
        if not day_entries:
            st.caption("No scheduled places yet.")
            continue
        for entry in sorted(day_entries, key=lambda item: item.start_time):
            place = entry.place
            with st.expander(
                f"{entry.start_time.strftime('%H:%M')}–"
                f"{entry.end_time.strftime('%H:%M')} · {place.name}",
                expanded=True,
            ):
                st.write(place.description)
                st.caption(
                    f"Estimated visit: {place.visit_minutes_estimate} min · "
                    f"Estimated travel: {place.travel_minutes_estimate} min"
                )
                hours = (
                    place.opening_hours
                    if place.opening_hours_verified
                    else "unverified"
                )
                st.caption(f"Opening hours: {hours}")
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
        with st.expander("Validation details", expanded=True):
            for issue in response.validation_issues:
                st.write(f"{issue.code}: {issue.message}")
    st.caption(
        f"Graph steps: {response.graph_steps} · Searches: "
        f"{response.search_calls} · Repairs: {response.repair_attempts}"
    )


def main(service: TravelPlannerService | None = None) -> None:
    runtime_service = service or get_service()
    _ensure_session(runtime_service)

    st.set_page_config(page_title="Grounded Sightseeing Planner", layout="wide")
    st.title("Grounded Sightseeing Planner")
    st.caption(
        "Coordinator + Planner · session-only state · sourced place recommendations"
    )
    if st.button("New trip"):
        _reset_session(runtime_service)
        st.rerun()

    with st.form("trip_request"):
        destination = st.text_input("Destination or place", placeholder="Hue")
        start_date = st.date_input(
            "Start date",
            value=datetime.now().astimezone().date(),
        )
        day_count = st.number_input(
            "Number of days", min_value=1, max_value=7, value=2, step=1
        )
        submitted = st.form_submit_button("Create sightseeing plan")

    if submitted:
        try:
            request = TripRequest(
                destination=destination,
                start_date=start_date,
                day_count=int(day_count),
            )
            message = (
                f"Create a {request.day_count}-day sightseeing plan for "
                f"{request.destination} starting {request.start_date.isoformat()}."
            )
            response = runtime_service.handle_turn(
                thread_id=st.session_state.thread_id,
                message=message,
                current_plan=st.session_state.current_plan,
                request=request,
            )
            _record_turn(message, response)
        except ValidationError as error:
            st.error(f"Invalid trip request: {error.errors()[0]['msg']}")

    response: AgentResponse | None = st.session_state.last_response
    if response is not None:
        _render_response(response)
    plan: SightseeingPlan | None = st.session_state.current_plan
    if plan is not None:
        _render_plan(plan)

    if st.session_state.conversation:
        st.subheader("Conversation")
        for turn in st.session_state.conversation:
            with st.chat_message(turn["role"]):
                st.write(turn["content"])

    user_message = st.chat_input("Ask or request a plan change")
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
