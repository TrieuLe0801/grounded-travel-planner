# Project Charter

Status: Active
Last updated: 2026-10-14

## Product

Grounded Travel Planner is a city/place sightseeing webapp. A user enters a
destination or place, a concrete start date and a day count from 1 to 7. The app
creates one current itinerary and lets the user chat to add constraints or make
bounded changes such as add, remove, replace, reorder, day changes and time
changes.

## Runtime Scope

The runtime starts with exactly two roles:

- Coordinator: owns user-facing chat, intent classification, delegation and the
  final explanation.
- Planner: proposes every plan change and calls Tavily search through a typed
  provider interface.

Both roles use the configured LangChain model boundary with the requested
default model name `gpt-5.5`. The webapp keeps only session-local state. It does
not use LangSmith traces as state storage.

## Invariants

- Accept destination/place, a concrete start date and a selected day count.
- Search for actual information before sourced recommendations are claimed.
- Never fabricate source URLs, opening hours or tool results.
- Source references must originate from normalized search results and match the
  recommended place.
- Label estimated visit/travel times and unverified opening hours.
- Validate input, schedule range, overlaps and known opening-hour conflicts
  before committing a candidate.
- Preserve the previous current plan when validation fails.
- Ordinary chat should not mutate the plan or perform unnecessary search.
- Bound every turn to 8 graph steps, 2 search calls and 1 repair attempt.
- Keep provider secrets out of model prompts, traces, logs and tracked files.

## Non-Goals

- Persistent user accounts or database storage.
- More runtime travel-specialist agents before the two-agent vertical slice is
  executable and verified.
- Offline fixture claims represented as live sourced recommendations.
- Production booking, payments or reservation workflow.
