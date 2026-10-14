# UI Plan — Streamlit for the Three-Week POC

Last updated: 2026-09-22
Status: Accepted

## Recommendation

Use **Streamlit** for the POC UI.

The current product contract is form-first: origin, destination, dates,
traveler counts and optional budget are structured fields. The output is also
structured: outcome, itinerary, cost, evidence and data gaps. Streamlit maps
directly to that interaction without adding a conversational event layer.

Keep **Chainlit** as a post-POC option if the product later becomes chat-first or
if visible agent steps, token streaming and conversational clarification become
the primary experience.

## Streamlit versus Chainlit

| Criterion | Streamlit | Chainlit | POC decision |
|---|---|---|---|
| Structured trip input | Native widgets and `st.form` batch submission | Chat settings/widgets are possible, but the main model is message-driven | Streamlit |
| Result presentation | Flexible cards, tabs, tables, metrics and expanders | Strong message/step presentation | Streamlit |
| Clarification UX | Render validation errors and preserve current form values | `AskUserMessage` is a natural conversational pause | Streamlit for POC; Chainlit later |
| LangGraph integration | Invoke the graph through a thin Python adapter | Official LangChain/LangGraph integration and callback handler | Either works |
| Session state | `st.session_state` across reruns in one browser session | Chat lifecycle and user session | Streamlit is sufficient |
| Resume after reload | Not guaranteed; Session State is tied to the WebSocket | Full resume requires authentication and data persistence | Out of scope for both |
| Automated UI tests | Official `streamlit.testing.v1.AppTest` | Testing/debugging support exists, but the POC would add another async surface | Streamlit |
| Three-week delivery risk | Low for a one-page form/result app | Higher because the app becomes chat/event/async-first | Streamlit |

## Minimal UI scope

One page only.

### Input form

- Origin: fixed/selectable TP.HCM.
- Destination: fixed/selectable Đà Nẵng.
- Start and end dates.
- Adult and child counts.
- Optional budget in VND.
- `Tạo kế hoạch` submit button.

Use `st.form` so inputs are sent to the Python backend together on submit.

### Execution status

- Show a running status while the graph executes.
- Do not expose hidden prompts or internal chain-of-thought.
- May show safe node labels such as validate, research fixtures and validate
  plan.

### Result rendering

- Outcome banner:
  - success for `PLAN_READY`;
  - info/warning for `NEEDS_CLARIFICATION`;
  - warning for `RESEARCH_INCOMPLETE`;
  - error for `PLAN_UNAVAILABLE`.
- Trip summary and assumptions.
- Day-by-day itinerary.
- Accommodation and food/place recommendations.
- Cost breakdown and total/range estimate.
- Sources/fixture IDs.
- Data gaps or validation errors.

### Session behavior

Use `st.session_state` only for:

- the latest submitted request;
- the latest graph result;
- a generated local `thread_id` if the optional in-memory clarification flow is
  implemented.

Do not treat Streamlit Session State as durable persistence. Reloading or losing
the WebSocket can reset it.

## Integration boundary

```text
Streamlit widgets
  -> UI adapter builds TripRequest
  -> graph.invoke(...) or graph.stream(...)
  -> typed TravelResult
  -> pure result-rendering functions
```

The UI must not duplicate date, budget, evidence or routing rules. Those remain
in domain/graph modules and are tested without Streamlit.

## File target

Suggested layout:

```text
src/grounded_travel_planner/ui/streamlit_app.py
src/grounded_travel_planner/ui/render.py
tests/ui/test_streamlit_app.py
```

Run locally:

```bash
uv run streamlit run src/grounded_travel_planner/ui/streamlit_app.py
```

## UI acceptance checks

- App starts without a model key or network access.
- Submitting the supported journey renders `PLAN_READY` sections.
- Missing/invalid dates render clarification errors and do not show a plan.
- Impossible budget renders `PLAN_UNAVAILABLE`.
- Fixture/source IDs and `synthetic_estimate` labels are visible.
- No business-rule implementation exists only in the UI layer.
- At least two Streamlit `AppTest` cases cover successful and invalid input.

## Explicit non-goals

- Chat interface or free-text trip parsing.
- Multipage navigation.
- Authentication or user accounts.
- Durable chat/session history.
- Custom React components, custom JavaScript or extensive CSS.
- Mobile-perfect responsive design.
- Public deployment.

## Delivery rule

Build the UI only after the graph and eight offline eval cases are stable. If
the graph is not green by the Week 3 feature freeze, keep the UI to the input
form, outcome banner and raw structured-result renderer; do not add visual
polish or chat behavior.

## Official references

- [Streamlit forms](https://docs.streamlit.io/develop/api-reference/execution-flow/st.form)
- [Streamlit Session State](https://docs.streamlit.io/develop/api-reference/caching-and-state/st.session_state)
- [Streamlit chat elements](https://docs.streamlit.io/develop/api-reference/chat)
- [Streamlit AppTest](https://docs.streamlit.io/develop/api-reference/app-testing)
- [Chainlit overview](https://docs.chainlit.io/get-started/overview)
- [Chainlit chat lifecycle](https://docs.chainlit.io/concepts/chat-lifecycle)
- [Chainlit AskUserMessage](https://docs.chainlit.io/api-reference/ask/ask-for-input)
- [Chainlit LangChain/LangGraph integration](https://docs.chainlit.io/integrations/langchain)
