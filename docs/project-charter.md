# Project Charter

Status: Active
Last updated: 2026-10-17

## Product

Grounded Travel Planner is a city/place sightseeing webapp. A user enters a
destination or place, a concrete start date and a day count from 1 to 7. The app
creates one current itinerary and lets the user chat to add constraints or make
bounded changes such as add, remove, replace, reorder, trip extension, day
changes and time changes.

The chat accepts Vietnamese requests and responds in Vietnamese by default.
Place names and source titles retain their original spelling; internal intent
codes, source evidence and validation rules remain language-independent.

The itinerary also presents source-attributed place photos when available;
missing imagery leaves the text itinerary usable. A separate read-only page
shows an image of the compiled LangGraph architecture.

The current interface uses JavaScript and Tailwind on the same origin as a thin
Python HTTP adapter. The earlier Streamlit interface remains available during
migration; the Coordinator/Planner/Chat runtime and validation rules are shared.

## Runtime Scope

The runtime has three roles:

- Coordinator: classifies the request and selects the graph route.
- Planner: proposes every plan change and calls Tavily search through a typed
  provider interface.
- Chat: writes the final Vietnamese response after deterministic policy nodes
  decide whether a candidate can be committed.

Coordinator defaults to `gpt-5.5`; Planner and Chat default to the lighter
`gpt-5.4-mini` through the configured LangChain model boundary. The webapp keeps
only session-local state. It does not use LangSmith traces as state storage.

Model/search turns run as bounded background jobs so they can continue while a
user navigates between app pages. Each session owns at most one pending turn and
integrates its result exactly once when the chat page polls or is reopened.

## Invariants

- Accept destination/place, a concrete start date and a selected day count.
- Search for actual information before sourced recommendations are claimed.
- Never fabricate source URLs, opening hours or tool results.
- Source references must originate from normalized search results. The
  `source_place_mismatch` token-overlap rule is temporarily disabled because it
  rejected valid sources; source relevance remains an evaluation metric.
- Label estimated visit/travel times and unverified opening hours.
- Validate input, schedule range, overlaps and known opening-hour conflicts
  before committing a candidate.
- Preserve the previous current plan when validation fails.
- Do not mutate the canonical plan from a background worker. Integrate a
  completed result only in its originating UI session.
- Ordinary chat should not mutate the plan or perform unnecessary search.
- Bound every turn to 8 graph steps, 2 search calls and 1 repair attempt.
- Keep provider secrets out of model prompts, traces, logs and tracked files.
- Visual enrichment never changes or blocks the validated current plan. Do not
  invent photos; show image creator, license and source-page credit.

## Non-Goals

- Persistent user accounts or database storage.
- More runtime travel-specialist agents before this three-role vertical slice is
  executable and verified.
- Offline fixture claims represented as live sourced recommendations.
- Production booking, payments or reservation workflow.
