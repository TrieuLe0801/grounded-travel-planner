# ADR 0004 — New sightseeing webapp scope and two runtime agents

Date: 2026-10-14
Status: Accepted
Supersedes: ADR 0002 and ADR 0003 for product/runtime scope.

## Context

The user explicitly discarded the old POC plan and defined a new simple webapp.
The confirmed input is a destination/place, concrete start date and day count.
AI searches for information, proposes sightseeing places and an itinerary, and
supports chat edits. State is kept only in the current app session.

The user requires LangChain, LangGraph, Tavily, LangSmith and at least two
runtime agents, and selected `gpt-5.5` for both agents. These choices replace
the previous fixture-only, single-agent-first scope and optional model/tracing.

## Decision

- Use LangChain for model, agent, tool and structured-output integrations.
- Use LangGraph for state, routing, delegation and bounded processing.
- Start with two runtime agents: Coordinator chats, clarifies and delegates;
  Planner searches through Tavily, proposes plans and updates existing plans.
- Use `gpt-5.5` for both; verify account/endpoint access when integrating.
- Check candidate schedules and source references in code before committing
  changes to the canonical current plan.
- Support chat rescheduling, reordering and adding/removing/replacing places.
- Trace every chat turn, agents and tool calls through LangSmith, propagating
  the session `thread_id` through root and child runs.
- Keep app state session-only. LangSmith trace retention is independent of
  session lifetime and does not provide app resume.
- Require real model/search/tracing smoke checks for a working-app claim;
  automated behavior tests use mocked providers separately.
- Apply no previous deadline, fixed journey, budget/pricing contract, CLI gate,
  golden-set count or old completion percentage to this new scope.

The one-page Streamlit interface and initial call/repair limits in the
[implementation plan](../implementation-plan.md) remain implementation proposals.
ADR 0001's Python development tooling remains applicable. Its former runtime
single-agent-first references are superseded by this record.

## Alternatives considered

- Retain the old fixture-first scope: does not satisfy the new explicit request.
- One runtime agent: simpler, but does not satisfy the user's two-role design.
- More than two runtime agents: no additional product role has been required;
  keep the first version focused on Coordinator and Planner.
- Durable trip/chat storage: the user chose current-session state only.

## Consequences

The runtime has clear ownership of conversation and plan generation. Additional
model calls and delegation can increase latency and cost; limits and narrow
context handoff keep the first version manageable. Search results need relevance
checks; travel time is estimated and missing opening-hour evidence stays explicit.

## Review triggers

Review if the user changes the two-agent/model requirement, adds durable state
or a new provider, or introduces a product capability outside the current
[charter](../project-charter.md).
