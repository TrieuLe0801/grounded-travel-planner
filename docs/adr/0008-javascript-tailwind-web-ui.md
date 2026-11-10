# ADR 0008 - JavaScript and Tailwind Web Interface

Status: Accepted
Date: 2026-10-16
Supersedes: the Streamlit presentation choice in ADR 0006

## Context

The user requested a more polished UI/UX built with JavaScript and Tailwind,
using the project-local UI/UX Pro Max guidance and its Vietnamese reference.
The existing Streamlit UI owns its DOM and rerun cycle, which limits the control
needed for a cohesive responsive interface and client-side interaction.

The Coordinator/Planner runtime, validation rules, source provenance, and one
canonical session plan remain the active product architecture.

## Decision

Use a JavaScript frontend with Tailwind for the itinerary, chat, and read-only
graph inspection. Serve it on the same origin as a thin Python HTTP adapter.
The adapter invokes `TravelPlannerService` and returns typed, presentation-safe
data. It does not reproduce planning or validation logic in JavaScript.

Keep conversation and the current plan only in a bounded in-memory session on
the server. Use an opaque browser session token. A turn captures the current
plan when submitted; at most one turn may run in a session at a time. Commit its
result only after the existing runtime validation succeeds. A rejected turn
retains the previous plan. Server restart or session expiry ends that session.

Keep source URLs, photo credit/license, estimated durations, and unverified
opening hours visible. The graph view remains read-only and must not invoke a
planning turn. No geographic route map is reintroduced.

Retain the existing Streamlit implementation during migration so the new UI can
be verified against its behavior before it becomes the primary entry point.

## Consequences

- The web runtime adds a JavaScript build and a Python HTTP adapter.
- The frontend owns presentation state; Python owns the canonical plan and
  provider execution.
- Offline tests need to cover session isolation, pending turns, rejected edits,
  sources, and accessibility-relevant UI states.
- This decision does not authorize persistent accounts, databases, or a change
  to the two runtime agents.

## Review Triggers

- Persistent or multi-instance session storage is required.
- The frontend starts making plan decisions instead of presenting server state.
- The user requests another web framework or deployment architecture.
