# Project Charter

Status: Active
Last updated: 2026-11-14

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
validation rules remain language-independent. App-rendered dates follow the
selected UI locale, including month and weekday labels in the trip-start date
picker; date values remain ISO in session and API data.

The itinerary also presents source-attributed place photos when available;
missing imagery leaves the text itinerary usable. The compiled LangGraph
diagram remains available to developers through the graph API, but its
inspection page is hidden from the user interface.

The current interface uses JavaScript and Tailwind on the same origin as a thin
Python HTTP adapter. The earlier Streamlit interface remains available during
migration; the Coordinator/Planner/Chat runtime and validation rules are shared.

The public React entry is a bilingual introduction page. Visitors with an active
Auth0 browser session use SSO; visitors without one continue through the
existing Auth0 email one-time-code flow before the planner, chat, visuals, or
saved tours appear. FastAPI enforces sign-in on private API routes; the landing
page and static assets remain public. Each live planner session is bound to its
verified internal account UUID. See ADR 0021.

ADR 0023 adds application administrator access. Existing accounts remain active
after the explicit migration; new Auth0 identities wait for administrator
approval. An administrator can grant, block and regrant application access,
inspect LangSmith model token usage and cost by account. Blocking revokes account
sessions but does not delete saved tours or LangSmith traces. Auth0 still owns
credentials; live trip/chat state remains session-only.

The user can explicitly save a validated current tour and later review that
snapshot from the same browser. Saved tours use a separate database and owner
credential; they are read-only records of the plan and sources at save time.
An application commit alone does not save a tour. The live itinerary and chat
still belong to the current session.

Clicking Home starts a fresh trip session and returns to the itinerary start.
It clears the live plan, conversation and trip-form draft while preserving the
selected language, account and saved-tour archive.

ADR 0016 selects account-owned saved tours through Auth0 email OTP; ADR 0021
adds Auth0 session SSO with that email-code flow as fallback and requires
sign-in for planner use. The prior account-ownership implementation
and isolated migrations have offline evidence. The mandatory entry and
session-owner changes remain subject to current verification. The running
application remains on its earlier image until controlled rollout. Account
ownership does not persist live itinerary or chat state.

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

`GTP_MODEL_PROVIDER` selects the global `openai` (the default) or `ollama`
provider. `GTP_COORDINATOR_PROVIDER`, `GTP_PLANNER_PROVIDER` and
`GTP_CHAT_PROVIDER` optionally override that provider by role. The three model
variables select their respective role models; OpenAI defaults are `gpt-5.5`
for Coordinator, `gpt-6.1-terra` for Planner and `gpt-4.1` for Chat. The default
`.env.example` does not require a local server for normal OpenAI calls. When an
OpenAI API call fails, the same role tries the configured local Ollama fallback
model once. This path requires a reachable local server and installed model;
failure leaves the prior plan intact. A role explicitly assigned to Ollama
never falls back to OpenAI. The webapp keeps the live itinerary and
conversation in session-local state. Only user-approved saved tour snapshots
use durable storage. It does not use LangSmith traces as state storage.

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
- When creating a new itinerary, schedule at least one grounded stop on every
  selected day.
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
- Format app-rendered dates in the selected UI locale while keeping date values
  language-independent in session and API data.
- Ordinary chat should not mutate the plan or perform unnecessary search.
- Bound every turn to 8 graph steps, 2 shared Planner/Chat Tavily calls and 1
  repair attempt. Chat skips search when the remaining graph steps cannot fit
  the tool node and its final response.
- Keep provider secrets out of model prompts, traces, logs and tracked files.
- Visual enrichment never changes or blocks the validated current plan. Do not
  invent photos; show image creator, license and source-page credit.
- Only an explicit save action on a validated canonical plan creates a saved
  tour. Archive reads do not run agents/search or mutate the live plan. Every
  archive operation is scoped to a verified owner.
- The React planner requires a verified Auth0 account. FastAPI checks account
  ownership on every live planner session and session-backed operation; a
  missing or mismatched account cannot read or change another account's state.
- Private planner and saved-tour routes require active account access. Only an
  active administrator can manage account access or read account usage; changes
  require CSRF and leave an audit event. Missing LangSmith cost must not show
  zero; trace token/cost totals are observed figures, not provider invoices.

## Non-Goals

- Search-history storage and restoration of archived tours into an editable
  session. Account-owned saved tours are in scope under ADR 0016; their live
  rollout is pending. PostgreSQL snapshot storage remains under ADR 0015.
- More runtime travel-specialist agents before this three-role vertical slice is
  executable and verified.
- Offline fixture claims represented as live sourced recommendations.
- Production booking, payments or reservation workflow.
