# ADR 0003: Use Streamlit for the POC UI

Date: 2026-09-22
Status: Superseded by ADR 0004 on 2026-10-14

This is a historical decision. Chat is core in the new product scope. See
[ADR 0004](0004-city-sightseeing-webapp.md) and the [current UI plan](../ui-plan.md).

## Context

The POC needs a small UI that can be completed inside the three-week delivery
window. The input and output contracts are structured rather than chat-first.
Streamlit and Chainlit were evaluated using their official documentation.

## Decision

- Add one minimal Streamlit page to P0 in Week 3.
- Use `st.form` for trip input and `st.session_state` only for the current
  request/result.
- Keep graph and domain rules outside the UI.
- Render the four workflow outcomes, itinerary, costs, evidence and gaps.
- Add at least two headless UI checks with Streamlit `AppTest`.
- Keep the CLI as a fallback and debugging path.
- Do not add Chainlit, FastAPI, authentication, persistence, multipage UI,
  custom components or deployment during the POC.

## Why not Chainlit now

Chainlit provides useful chat lifecycle hooks, `AskUserMessage`, visible steps,
streaming and an official LangGraph integration. Those capabilities become more
valuable when conversational clarification is the primary UX. For the current
structured form/result workflow, they introduce an async and message-oriented
surface without reducing core implementation work.

## Consequences

### Positive

- Fast path from typed request/result objects to a demoable UI.
- Structured itinerary, costs and sources can be rendered directly.
- Headless UI testing is available through `AppTest`.

### Negative

- Session State is not durable and can reset with the browser connection.
- The POC will not demonstrate a fully conversational agent UX.
- Streamlit reruns require disciplined separation between UI and graph logic.

## Review triggers

Review this decision when:

- free-text conversational input becomes a product requirement;
- clarification must pause and resume as a chat across browser sessions;
- visible agent steps/streaming are more important than structured forms;
- authentication or persistent chat history enters scope.

## References

- `docs/ui-plan.md`
- [Streamlit forms](https://docs.streamlit.io/develop/api-reference/execution-flow/st.form)
- [Streamlit AppTest](https://docs.streamlit.io/develop/api-reference/app-testing)
- [Chainlit AskUserMessage](https://docs.chainlit.io/api-reference/ask/ask-for-input)
- [Chainlit LangGraph integration](https://docs.chainlit.io/integrations/langchain)
