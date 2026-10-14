# UI Plan — Sightseeing Webapp

Last updated: 2026-10-14
Status: Proposed interface for the accepted new product scope.

See [the charter](project-charter.md) and [implementation plan](implementation-plan.md)
for current requirements. The former UI plan is a
[historical snapshot](archive/2026-10-14/ui-plan.md).

## One-page layout

Streamlit is the current proposal:

1. Form: destination/place, concrete start date and number of sightseeing days.
2. Current itinerary: suggested places, reasons, dates, time slots, estimated
   duration/travel, source links and unverified information.
3. Chat: ordinary conversation with Coordinator and requests to move, add,
   remove or replace places.

UI submits initial requests/chat turns to the same LangGraph workflow. Domain
validation and Tavily access remain outside rendering code.

## Session and tracing behavior

Keep the current graph state and chat in the current browser session, isolated
from other sessions. A new/lost session starts empty. With Streamlit, refreshing
the page can reset Session State; communicate that behavior.

Show that conversations are traced with LangSmith. Traces may outlive the app
session according to service configuration; they do not restore a trip.

## Result behavior

- Show safe processing status such as searching, planning and checking.
- Render the canonical committed plan alongside the conversation.
- Explain what changed after a successful edit.
- On clarification, conflicts or provider failures, explain the issue and retain
  the prior plan as a reference rather than claiming the edit succeeded.
- Clearly distinguish estimated timing and source-supported facts.
- Keep credentials and internal reasoning out of the user interface.

## Verification targets

Cover initial planning, ordinary chat, each edit type, conflicting edits,
provider failures and session isolation. Confirm that model/tool calls occur
only on explicit submit/chat events, not every rerender.

## References

- [Streamlit forms](https://docs.streamlit.io/develop/api-reference/execution-flow/st.form)
- [Streamlit chat](https://docs.streamlit.io/develop/api-reference/chat)
- [Session State](https://docs.streamlit.io/develop/api-reference/caching-and-state/st.session_state)
