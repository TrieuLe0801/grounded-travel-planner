# ADR 0004 - City Sightseeing Two-Agent Runtime

Status: Accepted
Date: 2026-10-14

## Context

The active product is now a city/place sightseeing planner. The previous POC
roadmap is historical. The runtime needs grounded recommendations, bounded
graph execution, a canonical current plan and explicit validation before state
mutation.

## Decision

Use LangGraph for the application runtime with exactly two initial runtime
agents:

- Coordinator classifies user turns, delegates when a plan mutation is needed
  and explains the result.
- Planner searches Tavily and proposes all candidate plans or edits.

Use LangChain for the model boundary and structured output. Both roles use the
requested default model name `gpt-5.5` through injectable provider interfaces.
Use typed search and trace interfaces so Tavily, OpenAI and LangSmith details do
not leak into UI or policy code.

Commit a candidate plan only after deterministic input, schedule and source
validation pass. Preserve the previous plan when validation fails.

## Consequences

- More runtime specialist roles are out of scope until the two-agent vertical
  slice is executable and tested.
- Missing provider credentials return safe failures rather than fabricated
  recommendations.
- Opening hours are marked unverified unless a provider result explicitly
  supports them.
- Tests can mock providers without live model, search or tracing services.

## Review Triggers

- The product adds persistence or cross-session memory.
- The team adds a runtime role beyond Coordinator and Planner.
- The model name or provider changes.
- Live search evidence requires richer source provenance than Tavily results
  provide.
