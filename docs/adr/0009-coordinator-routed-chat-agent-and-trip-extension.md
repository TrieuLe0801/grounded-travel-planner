# ADR 0009 - Coordinator-Routed Chat Agent And Trip Extension

Status: Accepted
Date: 2026-10-17

## Context

The initial runtime combined turn routing and user-facing response generation
inside Coordinator. Chat edits also had no explicit way to extend the trip
duration. When a model proposed an entry on a newly requested day, the graph
rebuilt the effective request with the current plan's old `day_count`; grounding
then forced the candidate back to that duration and schedule validation emitted
`entry_day_out_of_range`.

The user requested a separate chat node and limited Coordinator to distributing
work.

## Decision

Use three runtime roles behind the configured LangChain model boundary, with
role-specific defaults:

- Coordinator classifies each turn and selects the graph route.
- Planner remains the only role that searches Tavily or proposes plan changes.
- Chat produces the final Vietnamese response for ordinary conversation and for
  validated or rejected plan changes. Chat never proposes or commits a plan.

Coordinator uses `gpt-5.5` for high-confidence routing. Planner and Chat use
`gpt-5.4-mini` by default. The smaller model supports structured output and
tool-oriented agent workflows while reducing latency and cost for the higher
volume proposal and response calls. A role-specific configuration override is
available for provider testing and future model changes; the legacy
`RuntimeConfig.model_name` remains the Coordinator setting.

The LangGraph `chat_respond` node performs the deterministic commit decision and
then delegates response wording to Chat. It replaces the former combined
`finalize` behavior, so the bounded repair path remains within eight graph
steps.

Add an explicit trip-extension intent. An absolute target day count or a
relative positive day increment is resolved against the canonical current plan
before Planner runs. The resolved request must remain within the existing 1-7
day product bound. Extending a trip requires a grounded entry in the added day
range and preserves the existing itinerary; invalid candidates preserve the
previous plan.

## Consequences

- Ordinary conversation routes from Coordinator directly to Chat without
  search or plan mutation.
- Plan changes route from Coordinator through deterministic input validation to
  Planner, candidate validation and Chat.
- Extending a trip searches once for grounded recommendations. Repair does not
  add another search.
- Coordinator no longer writes the final user-facing explanation.
- Trace metadata continues to use one `thread_id` across Coordinator, Planner,
  Chat, tools and validation nodes.

## Superseded Decision

This ADR supersedes ADR 0004 only where ADR 0004 requires exactly two runtime
roles and assigns user-facing explanation to Coordinator. ADR 0004's Planner
ownership, provider boundaries, validate-before-commit rules and source-policy
amendment remain accepted.

## User Amendment — 2026-10-19

When using OpenAI without a local model server, Chat defaults to `gpt-4.1`;
Coordinator remains `gpt-5.5` and Planner remains `gpt-5.4-mini`. Each role can
still select an Ollama model through its `.env` provider and model variables.
An explicitly selected but unavailable Ollama provider does not silently route
the request to OpenAI.

## User Amendment — 2026-10-19 (superseded in part by ADR 0011)

The user authorized Chat to request Tavily search when current facts are needed.
The original Planner-only search statement is superseded only for this bounded
Chat use: Planner remains the only role that proposes plan changes and searches
to ground those proposals. Chat search supports its response only, does not
change plan state, and shares the per-turn limit of two calls. ADR 0011 defines
the session-history and Coordinator-summary handoff; ADR 0012 defines the
shared graph tool node that executes both roles' search requests.

## User Amendment — 2026-10-23 — Bidirectional Trip-Length Changes

Chat may both extend and shorten the current trip, with the duration kept within
the existing 1–7 day bound. Coordinator uses `extend_trip` for additions and
`shorten_trip` for reductions; an absolute duration uses `day_count`, while a
relative change uses a positive `day_count_delta` interpreted according to the
action.

An extension searches for grounded recommendations and must add at least one
grounded stop to every newly added day while preserving prior entries. A
shortening does not need new research: Planner preserves stops on retained days
and removes stops from dropped days, or may reschedule an existing stop into a
retained day. It cannot invent new stops or alter their source data. Both
changes pass the existing validate-before-commit checks; a rejected candidate
keeps the prior itinerary.
