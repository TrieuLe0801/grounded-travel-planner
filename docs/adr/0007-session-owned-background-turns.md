# ADR 0007 - Session-Owned Background Turns

Status: Accepted
Date: 2026-10-16

## Context

The Streamlit itinerary page called `TravelPlannerService.handle_turn()`
synchronously. Navigating to the graph page while a model/search turn was
running abandoned the page run that would have received the result, so the user
could not continue waiting and collect the response in the chat session.

## Decision

Run each blocking planning turn on a bounded in-process `ThreadPoolExecutor`.
Capture a deep copy of the session thread ID, message, canonical plan and trip
request before submission. The worker may call the service but must never read
or write Streamlit Session State.

Store one typed pending turn, including its unique token and `Future`, in the
originating Streamlit session. The chat page polls the Future through a
one-second Streamlit fragment and immediately on a full-page return. Only the UI
session that owns the pending turn may integrate its result. It appends the user
message at submission time, appends the assistant response exactly once after
completion, and changes the canonical plan only for a committed response.

Allow at most one in-flight turn per session. Disable new-trip, trip-form and
chat submission controls while it is pending. Do not claim that cancellation
stops an already executing Python thread.

## Consequences

- A planning turn continues when the user navigates between Streamlit pages in
  the same browser session.
- The shared worker pool is bounded to four threads; plans, conversations and
  pending-turn references remain isolated in Session State.
- Worker failures return a safe Vietnamese provider-error response and preserve
  the captured plan.
- Restarting the Streamlit process or losing the browser session still loses
  pending work because persistence remains out of scope.
- Streamlit AppTest verifies whole-page reruns and exact-once integration but
  cannot automate real sidebar multipage navigation.

## Review Triggers

- Durable accounts, job queues or cross-process deployment are introduced.
- More than one concurrent plan mutation per session is required.
- Provider calls need enforceable cancellation or wall-clock deadlines.
