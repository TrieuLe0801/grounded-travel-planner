# Project Charter

Status: Active
Last updated: 2026-10-23

## Product

Grounded Travel Planner is a city/place sightseeing webapp. A user enters a
destination or place, a concrete start date and a day count from 1 to 7. The app
creates one current itinerary and lets the user chat to add constraints or make
bounded changes such as add, remove, replace, reorder, extend or shorten the
trip, change days and change times.

The UI and assistant default to Vietnamese and provide an English option. The
selected language is stored in the current session and captured when a turn is
submitted, so switching languages does not reset the plan, transcript or
pending work. New model-authored responses and itinerary prose follow that
captured language. User messages, place names, source titles and provider source
data retain their original text; internal intent codes, source evidence and
validation rules remain language-independent.

The itinerary also presents source-attributed place photos when available;
missing imagery leaves the text itinerary usable. A separate read-only page
shows an image of the compiled LangGraph architecture.

The current interface uses JavaScript and Tailwind on the same origin as a thin
Python HTTP adapter. The earlier Streamlit interface remains available during
migration; the Coordinator/Planner/Chat runtime and validation rules are shared.

## Runtime Scope

The runtime has three roles:

- Coordinator: classifies the request in either supported language, reads
  bounded recent session history and produces a short handoff summary in the
  selected language for downstream roles.
- Planner: proposes every plan change and emits a typed search request when
  grounded plan recommendations need Tavily research.
- Chat: writes the final response in the selected language after deterministic
  policy nodes decide whether a candidate can be committed. When current facts
  are needed and search budget remains, Chat may request one Tavily search and
  cite only provider-returned sources; it never proposes or mutates the plan.
- `tavily_tool`: one shared LangGraph node executes typed search requests from
  Planner or Chat. It is the only runtime node that calls the search provider,
  and returns sources only to the requesting role.

`GTP_MODEL_PROVIDER` explicitly selects the global `openai` (the default) or
`ollama` fallback. `GTP_COORDINATOR_PROVIDER`, `GTP_PLANNER_PROVIDER` and
`GTP_CHAT_PROVIDER` optionally override that provider by role. The three model
variables select their respective role models; OpenAI defaults are `gpt-5.5`
for Coordinator, `gpt-5.4-mini` for Planner and `gpt-4.1` for Chat. The default
`.env.example` does not require a local server. Ollama must be selected
explicitly and does not silently fall back to OpenAI. The webapp keeps only
session-local state. It does not use LangSmith traces as state storage.

The webapp keeps the canonical plan, at most 12 conversation messages and a
rolling summary of at most 1,200 characters in session-only state. Coordinator
prompts receive at most eight recent messages of 600 characters each plus the
summary. Planner and Chat receive the summary and task-specific plan context,
not the raw transcript. Reloading the JavaScript page rehydrates the transcript
from the same in-memory session; reset creates a new isolated session. The app
does not use LangSmith traces as state storage.

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
- Chat can change trip length in either direction within the 1–7 day bound.
  Each added day needs a grounded stop. Shortening keeps stops on retained days
  and removes or reschedules stops from days beyond the new duration before
  committing the updated itinerary.
- Do not mutate the canonical plan from a background worker. Integrate a
  completed result only in its originating UI session.
- Changing language changes UI labels and the locale for future turns; it does
  not translate stored user messages, existing plan text, place names or source
  metadata, and it does not change an already-running turn's captured locale.
- Ordinary chat should not mutate the plan or perform unnecessary search.
- Bound every turn to 8 graph steps, 2 shared Planner/Chat Tavily calls and 1
  repair attempt. Chat skips search when the remaining graph steps cannot fit
  the tool node and its final response.
- Keep provider secrets out of model prompts, traces, logs and tracked files.
- Visual enrichment never changes or blocks the validated current plan. Do not
  invent photos; show image creator, license and source-page credit.

## Non-Goals

- Persistent user accounts or database storage.
- More runtime travel-specialist agents before this three-role vertical slice is
  executable and verified.
- Offline fixture claims represented as live sourced recommendations.
- Production booking, payments or reservation workflow.
