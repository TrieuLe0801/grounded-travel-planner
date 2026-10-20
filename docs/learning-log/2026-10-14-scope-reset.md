# Learning Log - 2026-10-14 Scope Reset

The active repository scope was reset from the older three-week POC to a
city/place sightseeing webapp.

The initial two-role and single-model decisions below describe the 2026-10-14
baseline. ADR 0009 and the 2026-10-17 entry at the end record the current
three-role runtime and role-specific model policy.

## Decisions Recorded

- The current product is a session-only Streamlit travel-planning webapp.
- Runtime roles are limited to Coordinator and Planner for the first vertical
  slice.
- Planner is the only runtime role that may call Tavily search and propose plan
  mutations.
- Coordinator is user-facing and explains only validated committed results.
- The requested default model is exactly `gpt-5.5`.
- External model, search and trace providers stay behind typed interfaces.
- LangSmith traces are observability data and not application state.
- On 2026-10-16 the user selected Vietnamese as the default language for
  webapp chat requests and replies. Proper place names and source titles remain
  as provided by users and search results.
- The Vietnamese UI and fallback paths passed AppTest/pytest (40 total tests).
  A live Vietnamese add request inside the container committed revision 2 and
  produced a Vietnamese assistant reply with one search and no repair.
- On 2026-10-16 the user requested source-backed place images, a mapped route
  view, and a car moving to a clicked itinerary stop. ADR 0005 keeps these
  presentation features separate from the canonical plan and two-agent graph.
- The UI/UX Pro Max Codex skill was installed project-locally as version
  `2.15.0`. The visual itinerary passed 48 host/container tests and live
  Commons/Wikipedia metadata checks for two Hue landmarks. A fake-DOM
  JavaScript run confirmed click, reduced motion and interruption behavior;
  real-browser visual inspection remains open.
- Later on 2026-10-16 the user requested a separate page with an image of the
  compiled runtime graph, then explicitly requested removal of the itinerary
  route map shown in their screenshot. ADR 0006 supersedes the map/car portion
  of ADR 0005. Source-attributed place photos remain in the itinerary.
- The new graph page and photo-only itinerary passed focused offline tests.
  After the `get_graph_image()` integration, 47 tests passed in both host and
  Docker test runs. The rebuilt Compose
  container reached healthy status at `127.0.0.1:8503`. A previously commented
  source-place matching check was restored after the full suite exposed its
  failure; the remaining project lint and formatting checks then passed.
- The graph page now uses the PNG bytes returned by
  `TravelPlannerService.get_graph_image()` as requested. The existing local SVG
  renderer remains a fallback when Mermaid image rendering is unavailable.
- The user then requested temporary removal of `source_place_mismatch` because
  its token overlap caused repeated false rejections. URL provenance and the
  remaining deterministic source/hour checks stay enabled. Do not restore this
  issue code until a better relevance matcher is accepted.
- The user reported that navigating away from chat abandoned a synchronous
  planning turn. ADR 0007 moves `handle_turn()` to a bounded background worker,
  stores one pending Future in the originating session and polls it immediately
  on page return plus once per second while chat stays open. The worker receives
  copied inputs and never mutates Session State.
- Nine focused async/UI tests simulated leaving and returning through a
  whole-page rerun; the full host and Docker suites passed 50 tests. Streamlit
  AppTest cannot exercise actual sidebar navigation, so a real-browser
  cross-page check remains.
- On 2026-10-17 ADR 0008's JavaScript/Tailwind interface was completed as the
  current web UI. React presents responsive itinerary/chat, read-only graph,
  and optional Commons photos with creator/license/source. A thin FastAPI
  adapter keeps a canonical plan in an opaque server session and exposes
  revision-bound visual metadata without blocking a planning turn.
- The initial container build exposed a missing static-dist path after package
  installation; an explicit runtime path fixed it. The rebuilt container
  became healthy at `127.0.0.1:8503` and returned HTTP 200 for the page,
  generated JS/CSS assets and graph API. Host and Docker test targets each
  passed 54 pytest cases;
  frontend typecheck/build, isort, Black, flake8 and Ruff. Real-browser layout
  and navigation QA remains pending because the browser surface was unavailable.
- On 2026-10-17 an overlong model-authored
  `PlanCandidate.returned_sources[].snippet` exposed that provider-owned source
  inventory was still part of the Planner structured-output schema. The model
  now returns a `PlannerProposal` containing only plan, summary and issues;
  trusted source URLs and references are attached afterward by grounding.
  Tavily prompt snippets remain capped at 1,000 characters and grounded
  `SourceReference` snippets now allow up to 4,000 characters.
- Later on 2026-10-17, the user requested that the JavaScript graph page show
  the PNG from `get_graph_image()` and keep it within the page. The adapter now
  serves that image at a read-only endpoint; the UI constrains its width and
  viewport height, and requests the existing SVG only when PNG rendering fails.
  A local adapter check returned 24,241 PNG bytes with HTTP 200; the SVG fallback
  also returned HTTP 200.
- On 2026-10-17, the runtime model policy was split by role. Coordinator keeps
  `gpt-5.5` for routing, while Planner and Chat default to `gpt-5.4-mini` for
  lower-cost, higher-volume structured proposal and response calls. The
  role-specific settings remain behind `RuntimeConfig` and the typed model
  adapter; historical live `gpt-5.5` evidence remains unchanged.
- The same day, the user moved response generation out of Coordinator into a
  dedicated Chat node and requested a fix for extending an itinerary by chat.
  `extend_trip` now resolves a target duration from an absolute count or a
  positive increment before Planner runs. Invalid bounds stop before search;
  valid extensions preserve existing entries and require a grounded entry in
  the added days. The host and Docker suites passed 64 tests, and the rebuilt
  runtime reached healthy status on port 8503.
- A follow-up exposed that Chat received only a boolean indicating whether a
  plan existed, despite the typed Planner candidate remaining in graph state.
  The Chat handoff now includes the Planner summary and validated committed plan.
  Rejected candidates are omitted; Chat receives the validation issues and the
  retained prior plan instead. Focused tests passed 44 cases, while the full host,
  Docker build-stage and offline Docker suites each passed 64. The rebuilt
  runtime became healthy and returned HTTP 200 for the app and graph PNG.
- On 2026-10-18, the user requested configurable local Ollama support. ADR
  0010 selects explicit `openai`/`ollama` provider configuration, a global
  fallback with optional per-role overrides, and three role-model variables.
  The offline implementation uses the typed
  `ChatOllama` structured-output adapter and an opt-in Compose profile that
  persists pulled weights. Native Ollama 0.9.0 then pulled `qwen2.5:3b` on the
  Mac M1, passed a structured-output call and committed a one-day Hue plan with
  two entries, one Tavily search and no repair or validation issues. LangSmith
  found 25 matching runs, all with the same `thread_id`. Detailed evidence is
  `docs/experiments/2026-10-18-ollama-local-smoke.md`.
- Later on 2026-10-18, the user selected OpenAI `gpt-5.5` for Coordinator and
  local Ollama `qwen3:4b` for Planner and Chat. Per-role provider overrides now
  preserve the global provider as a backward-compatible fallback. The native
  mixed-provider smoke loaded `qwen3:4b`, passed direct structured output, and
  committed a one-day Hue plan with four entries, one Tavily search, no repair
  and no validation issues. LangSmith returned 25 matching runs (seven root,
  18 child), all carrying the smoke `thread_id`. The Docker Compose profile and
  local chat-edit flow remain unverified. The full pytest suite passed 78 tests;
  isort, Black, flake8, Ruff, lockfile, Compose configuration and JSON/diff
  checks also passed. Compose subsequently separated its app endpoint from the
  direct-host endpoint: `GTP_COMPOSE_OLLAMA_BASE_URL` defaults to host Ollama,
  while the opt-in profile requires explicit `http://ollama:11434` routing. The
  recreated Compose app passed a native-host `qwen3:4b` structured call and a
  fresh HTTP Hue turn committed four entries with one search and no repair; the
  internal Compose profile and local chat-edit flow remain unverified.
- On 2026-10-19, the user selected `qwen2.5:3b` in place of `qwen3:4b` for Planner and
  Chat. The Compose default pull list and local runtime configuration now use
  that smaller model. Its structured output passed inside the app container, and
  a fresh HTTP Hue request committed two entries with one search, no repair and
  no validation issues.
- Later on 2026-10-19, the user requested API/local model selection through
  `.env` and API defaults when no local model is serving. Per-role routing
  already supported this. This host has no Ollama CLI or configured
  `OLLAMA_BASE_URL`, so `.env` now selects OpenAI for all roles with
  `gpt-5.5` Coordinator, `gpt-5.4-mini` Planner and `gpt-4.1` Chat. The copied
  `.env.example` uses the same defaults and documents explicit local overrides.
  No automatic provider fallback was added; selecting an unavailable local
  model still returns a safe error rather than making an unexpected API call.
- Loading `.env` resolved the expected three model/provider assignments without
  a live API request. The focused suite passed 49 tests; the full host suite
  passed 82, and all formatting/lint/lock/diff checks passed. Docker was
  initially unavailable, then returned; the test image passed 82 tests and the
  rebuilt Compose app became healthy. The container reads the expected model
  assignments and both the root page and graph PNG endpoint returned HTTP 200.
  No live model API request was made.

## Evidence

- On 2026-10-19, a reported `Planner did not produce a candidate plan` result
  exposed that `PlannerProposal.plan` was optional. The structured schema now
  requires a complete plan, and Planner's prompt explicitly asks for one.
  Missing or null model output fails at the provider boundary and retains the
  prior plan. Four offline regression cases and the full 82-test suite passed,
  along with isort, Black, flake8 and Ruff. A separate rebuilt-image live Hue
  request using `qwen2.5:3b` committed two entries, one search and no repair.
  The already running app was not restarted so existing sessions remain intact.
- New charter and implementation plan describe the active product.
- ADR 0004 records the accepted two-agent runtime architecture.
- Phase 1A added the importable Coordinator/Planner runtime, typed provider
  boundaries and deterministic validators.
- Phase 1B added the session-only Streamlit form/chat adapter.
- Nineteen offline tests passed, including core routing/commit behavior and two
  Streamlit AppTests.
- The final live smoke committed a Hue plan with five Tavily-returned citations;
  all 14 matching LangSmith root/child runs carried the same `thread_id`.
- The Docker test target passed 19/19 tests on Linux/Python 3.10.22. The non-root
  Compose runtime reached health 200 and committed a live Hue plan from inside
  the container.
- On 2026-10-15 the user prioritized post-plan chat editing. The offline suite
  passed 39 tests, including eight versioned chat-edit cases and UI success/reject
  coverage. A live create-then-remove turn committed revision 2 on the same
  session and preserved the four untargeted stops.
- Added a separate, offline source-quality baseline with 16 manually labelled
  synthetic citations. The labels expose relevance and host-diversity metrics
  but do not measure live Tavily quality or change runtime commit rules.
- Migrated the original smoke to LangSmith v2 `runs.query()` and verified a
  live Hue run with 25 matching runs carrying the same `thread_id`.
- The Planner source-schema regression passed 33 focused tests and 56 full tests
  on both the host and a rebuilt offline Docker image. Formatting, lint, lockfile
  and diff checks passed; the rebuilt Compose runtime is healthy on port 8503.
- Coordinator routing, Chat response isolation and trip extension passed 44
  focused tests and 64 full host/Docker tests. Frontend typecheck/build and all
  Python quality gates passed. Live providers were not invoked for this change.
- Planner-to-Chat context regressions prove that committed replies receive the
  added entry and grounded source data, while rejected replies cannot see the
  rejected plan body. The host and both Docker test runs passed 64 tests; no
  live provider was invoked. The rebuilt Compose runtime reached healthy status.
- The JavaScript chat composer was then moved into a lower-right floating panel.
  The icon trigger opens it without leaving the itinerary or graph view, the
  input receives focus on open, Escape closes it, and the panel keeps pending,
  response and error feedback near the input. User and assistant turns are
  rendered as separate right/left conversation bubbles with role labels.
  Frontend typecheck/build passed; real-browser visual QA remains open.
- The JavaScript interface was then lightened from the previous dark palette to
  a light blue and navy system. A soft blue page background and white surfaces
  keep the app bright, while blue accents identify primary actions, links and
  focus states. Frontend typecheck/build passed; browser inspection was
  unavailable.

## Open Risks

- Live providers still require local credentials and network access.
- Tavily results may not include opening hours; those hours must remain labeled
  unverified.
- Live source provenance is verified, but source editorial quality and domain
  diversity are not yet scored.

## Integration Learnings

- Tavily content must be bounded before Pydantic validation; one live snippet
  exceeded 1,000 characters.
- Provider-owned grounding metadata must not be exposed as model-authored
  structured output. Otherwise Pydantic can reject an untrusted echoed source
  before Planner has a chance to replace it with normalized provider results.
- `ChatOpenAI.with_structured_output` needed `method="function_calling"` because
  strict response-format validation rejected Pydantic `HttpUrl`'s `uri` format.
- Search-call counters must advance at tool-attempt time, not only after a later
  model call succeeds.
- Edit validation must prove the requested add/remove/replace/reorder/day/time
  change was applied; generic schedule validity alone is not enough.
- Versioned uv derived-image tag names change with supported distro variants;
  copying a pinned uv binary into an official Python slim base was more robust.
- Container verification should cover both safe rejection and a successful live
  plan; provider reachability alone does not demonstrate commit behavior.
- Unverified hours are a permissible grounded data gap. Planner grounding must
  normalize them to `unverified`; only deterministic policy errors may block a
  commit, not advisory issues authored by the model.
- Reorder indices must match the chronological order visible in the UI;
  changing only the stored list order does not meet a user's reorder request.
- A repair must carry forward only trusted search/current-plan sources. Copying
  candidate references into that pool can launder a fabricated URL.
- Exact casefolded place-name comparison rejects benign Vietnamese accent and
  village-descriptor variants. Bound alias matching and ask Planner to retain
  the requested name; preserve old stops when validating an addition. The
  initial Lô Lô Chải live recheck hit OpenAI HTTP 429 `billing_not_active`.
  On 2026-10-16, a representative container flow added Lô Lô Chải, preserved
  the existing stop and committed revision 2 with one search and no repair.
- The Docker test stage must include versioned eval data and the smoke script
  imported by tests; excluding them from the build context caused collection
  errors even though host pytest passed.
- A final response agent needs the validated Planner outcome, rather than only a
  plan-exists flag. Passing the typed candidate only after commit and retaining
  the prior plan on rejection keeps response generation aligned with commit
  semantics without adding graph steps.

## User Decision — Bounded Session Context And Chat Search — 2026-10-19

- The user asked Chat to call Tavily through a bounded structured function-call
  decision when current information is needed. Planner remains the only role
  that proposes plan changes; the shared per-turn cap stays at two calls.
- Keep the active transcript in the existing session only (12 messages max).
  Coordinator reads at most eight recent messages, capped at 600 characters
  each, with a rolling 1,200-character summary. Planner and Chat receive that
  summary and task-specific context, not the raw transcript.
- Return actual Chat search citations in the assistant transcript. Search
  results do not enter the candidate plan or validation state. If there are no
  usable sources, Chat must say the current fact was not verified.
- Record redacted Tavily start/success/failure events with the same session
  `thread_id`; do not include user transcript, query or credential data.
- The offline tests cover the no-search, search, failure, citation, shared
  budget, bounded handoff, API hydration, reset and session-isolation paths.
  The first direct-call iteration had a live factual Chat request that made one
  Tavily call, returned five sources and produced `chat.search.*` LangSmith
  events with a matching `thread_id`. ADR 0012 later replaced that direct-call
  path with the shared graph node and `tool.tavily.*` events. The original smoke
  is preserved at `docs/experiments/2026-10-19-live-chat-search-smoke.md`.

## User Decision — Shared Tavily Graph Tool Node — 2026-10-19

- The user requested a graph tool node shared by Planner and Chat. Both roles
  now emit bounded `TavilyToolRequest`s; the single `tavily_tool` node owns all
  provider calls, increments the shared call budget before attempting search,
  and returns normalized sources only to the requesting role.
- LangSmith events use `tool.tavily.start/success/failure` with requester,
  count and session `thread_id`; event payloads omit query and conversation
  content.
- Keep the 8-node graph limit and one repair. Coordinator now performs
  deterministic input checks in its route node; candidate validation invokes
  at most one Planner repair. Chat skips search when there is no remaining room
  for the tool node and final response.
- Offline tests and one live request verified owner routing, failure/count
  behavior, plan isolation, and the new trace names. See ADR 0012 and
  `docs/experiments/2026-10-19-live-shared-tool-node-smoke.md`.

## Runtime Flow Cleanup — 2026-10-19

- A repository-wide usage check found two graph-state declarations, two agent
  config references, two one-field result wrappers and one service search
  reference with no runtime consumers. They were removed without changing the
  graph topology or provider boundary.
- The background Future still receives bounded deep copies of summary and chat
  history; `PendingTurn` no longer stores a second copy that no foreground code
  reads. It retains the captured plan needed for safe failure recovery.
- The HTTP adapter now uses the conversation module's shared transcript and
  summary limits instead of repeating the values `12` and `1200`.
- Regression coverage confirms exact Chat citations from the tool-owned source
  list, Planner repair behavior, worker input isolation, API session bounds and
  reset behavior. Focused tests passed 63 cases; the full host suite passed 90,
  and all Python formatting/lint gates passed.

## Development Agent And Skill Refinement — 2026-10-20

- The project-scoped Codex manager, planner, coding and testing instructions
  now reflect the actual Python/LangGraph, FastAPI, React/Tailwind, Compose and
  documentation stack. They preserve unrelated dirty hunks, treat subsequent
  user corrections as hard constraints, and distinguish static/offline evidence
  from browser, container and live-provider evidence.
- The delivery skill detects explicit commit/push intent and defaults to neither
  action without interrupting a completed change to request authorization.
- UI/UX Pro Max keeps its upstream catalog and adds a small repository overlay
  for Vietnamese chat, photo-only itinerary, read-only graph image, pending-turn
  navigation and current UI evidence rules.
- This was a configuration/documentation update only. Static parsing and diff
  checks were run; no application, frontend, container, browser or live-provider
  check is claimed.

## User Decision — Bilingual Webapp — 2026-10-20

- Add English as a selectable UI and assistant language while keeping Vietnamese
  as the default. Store the choice in the current session; changing it must not
  clear the itinerary, conversation, summary or pending turn. A pending turn
  uses the locale captured when it was submitted; new turns use the current
  selection.
- Apply the choice to React/Tailwind, Streamlit and its graph page, Coordinator
  summaries, Planner itinerary prose, Chat responses and code-owned fallbacks.
  Preserve user text, place names, existing plan/transcript content and source
  metadata without translation. Validation and source policies remain
  language-independent.
- ADR 0013 records the decision. Existing focused API/runner/chat-context checks
  passed 14 tests; `npm run check`, `npm run build`, Python compileall, flake8,
  Black, isort, Ruff, lock and diff checks passed. No browser, container or
  live-provider verification was run.
