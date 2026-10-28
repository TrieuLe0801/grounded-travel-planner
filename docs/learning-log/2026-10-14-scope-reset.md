# Learning Log - 2026-10-14 Scope Reset

## Deterministic Trip Shortening — 2026-10-27

- The user reported that reducing trip duration returned the safe Planner
  failure response. Recent prompt optimization had removed source references
  from each prior-plan entry, while shortening validation requires retained
  entries and their nested source data to remain unchanged.
- The Planner now creates a deterministic shortened candidate from the current
  plan, preserving retained-day entries and full source data while dropping
  entries after the new final day. This edit requires no model call or search.
  Other model-backed prompts again keep source references attached to their
  entries without duplicating them in the separate source list.
- A graph-level offline regression verifies commit, exact retained entry/source
  preservation, and zero searches/repairs. Full host tests: 117 passed; isort,
  Black, flake8, Ruff and diff check passed. The running Compose container has
  not been recreated because replacement clears session-only plans.

## User Decision — Model Identifiers from Environment — 2026-10-27

- The user directed that model names live in environment variables and runtime
  code only load them. Removed provider model identifiers and model-name
  defaults from the Python runtime. Coordinator, Planner, Chat and Ollama
  fallback identifiers are required environment values; JSON-schema-mode model
  identifiers use `GTP_OPENAI_JSON_SCHEMA_MODELS`. Missing role/fallback names
  now fail configuration instead of silently selecting a model.
- The OpenAI adapter receives its JSON-schema model list from `RuntimeConfig`.
  `.env.example` and README document the environment settings; the optional
  Compose model initializer no longer embeds a model identifier. Test fixtures
  now use synthetic identifiers.

## Native Ollama MLX Fallback — 2026-10-27

- Updated the native macOS Ollama app to v0.40.10 from the official release.
  Its published SHA-256 matched, and macOS verified the app code signature.
- Pulled `qwen3.5:4b-mlx`. Structured output succeeded on the host and from the
  app container at `host.docker.internal`; an intentionally invalid OpenAI key
  also triggered one structured MLX response from the app container.
  `ollama ps` reported runner `mlx` and `100% GPU`.
- The app image was rebuilt and recreated with the MLX fallback model in `.env`.
  It reached healthy status and the root returned HTTP 200. Removed
  `qwen2.5:3b` from the native Ollama store and CPU container model volume, then
  stopped the CPU container. App recreation cleared session-only state; the
  previous Ollama app remains as a temporary local backup.
- No test suite was run for the environment-only model-name refactor. Isort,
  Black, flake8, Ruff and diff checks passed; the rebuilt app resolved all model
  names and the schema-mode list from `.env` and remained healthy. The
  preceding fallback change had passed 113 host tests before this refactor.

## Agent Prompt Latency And Token Optimization — 2026-10-27

- Following the OpenAI latency guide, removed repeated Planner prompt data:
  the prior schedule is serialized once in chronological user-visible order,
  source references are supplied in a separate trusted list, and the prompt no
  longer repeats the raw user message embedded in intent or the whole request
  object. Chat now uses the visible schedule and Planner summary instead of
  repeating full plan JSON. Coordinator, Planner and Chat are directed to keep
  generated summaries/responses concise.
- Two focused offline regressions passed; Ruff, Black and `git diff --check`
  passed. No live before/after usage or latency benchmark was run. Full pytest
  collection is blocked by other dirty `config.py` and `service.py` changes in
  the shared worktree (missing model constants in tests and a recursive model
  factory); these files were left untouched.
- OpenAI reference: https://developers.openai.com/api/docs/guides/latency-optimization

## OpenAI Model Call Timeout — 2026-10-27

- The user reported Planner model substitutions timing out. The adapter applied
  one 20-second timeout to every OpenAI model call, so switching model names did
  not change the time limit.
- Increased the per-request timeout to 60 seconds. A fresh live graph run with
  the current `gpt-6.1-terra` Planner completed in 41.3 seconds total and
  committed four Huế entries with no validation issues. The 113-test suite,
  isort, Black, flake8, Ruff and diff check passed. The rebuilt app is healthy;
  root and graph image return HTTP 200. Recreating the app cleared session-only
  state.

## User Decision — Fall Back on Any OpenAI API Error — 2026-10-27

- The user asked for immediate Ollama fallback whenever the OpenAI API raises
  an error. The OpenAI-configured role wrapper now catches any OpenAI SDK
  `OpenAIError`, including HTTP 400/404, and makes one Ollama structured-output
  attempt with the same prompt, schema and trace metadata. Local validation and
  application errors still propagate without switching providers; explicit
  Ollama roles remain Ollama-only. ADR 0010 records this policy amendment.
- Focused fallback tests passed 18 and the full host suite passed 113. Isort,
  Black, flake8, Ruff and `git diff --check` passed. The expanded fallback is
  included in the rebuilt runtime; a successful live turn used OpenAI, so this
  new fallback coverage was not invoked in that run.

## Terra Planner Schema Compatibility — 2026-10-27

- The first live full-turn check exposed OpenAI HTTP 400: Pydantic emitted
  `format: uri` for `SourceReference.url`, which the model's structured-output
  schema rejected. The Planner therefore had no candidate plan to commit.
- The Terra adapter now removes only that unsupported schema format before
  submission. It still validates the returned mapping with the original
  `PlannerProposal` Pydantic type, including `HttpUrl` checks. If Planner fails,
  the graph returns a localized code-owned message and skips Chat generation,
  preventing an unsupported text-only itinerary from appearing as a result.
- The full 111-test suite, isort, Black, flake8, Ruff and diff check passed. The
  rebuilt Compose app is healthy and returns HTTP 200 for the root and graph
  image. A live Huế turn committed a four-entry plan with source references on
  all entries. The prior Terra-specific schema warning did not appear in the
  app logs. Recreating the app cleared session-only state.

## User Decision — Replace Slow Planner Model — 2026-10-27

- The user reported that `gpt-5.4-mini` is too slow and its context window
  is too limited for Planner. The new Planner OpenAI default is
  `gpt-6.1-terra`; Coordinator, Chat and Ollama fallback remain unchanged.
- OpenAI Docs lists 1,050,000 context tokens for Terra and 400,000 for the
  previous Mini model. Terra uses `reasoning_effort="none"` and JSON-schema
  structured output in this app. Its native tool calling needs the Responses
  API, while the app's Tavily request is handled by its graph node.
- This decision changes the model ceiling, not the session summary, transcript
  or Tavily bounds. Focused tests passed 70, the full suite passed 111, and
  isort, Black, Ruff and diff check passed. Repo-wide flake8 retains three
  pre-existing F841 findings. A small direct live structured call succeeded
  in 3.91 seconds; LangChain bound the full Planner schema offline. The
  rebuilt app is healthy, resolves Terra with Ollama `qwen2.5:3b` fallback,
  and serves root/graph at HTTP 200. Recreating it cleared session-only
  state. Full-turn latency remains unverified.

## User Decision — Restore Committed Code, Keep Ollama Fallback — 2026-10-27

- The user requested a return to the old code while retaining Ollama as a
  backup when OpenAI fails. Commit `8aea1a9` already contains the accepted
  OpenAI-to-Ollama fallback from `e1392ed`.
- Restored the post-commit Planner latency, compact output, day/time edit and
  timeout-refactor changes to that committed baseline. The OpenAI adapter
  still uses a 20-second timeout and makes one Ollama fallback attempt after
  qualifying API failures.
- The uncommitted day/time preservation fix was part of the rollback. The
  observed multi-entry day-move data-loss issue is therefore unresolved in
  the restored code. All 110 tests, isort, Black, Ruff and diff check passed;
  full flake8 still reports three pre-existing F841 findings in
  `artifacts/presentations/update_deck.py`. No container rebuild or live
  provider turn is claimed.

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

## Trip-Day Boundary Follow-Up — 2026-10-23 (Superseded)

- New-trip proposals now ignore the prior session itinerary and start at
  revision 1, preventing entries from a longer prior itinerary from leaking
  into a newly selected shorter trip.
- A request to move a stop to a day beyond the trip length now stops before
  Planner and displays a localized explanation.
- `git diff --check` passed and the rebuilt Compose container reached healthy
  status. Regression tests and live provider checks were not run.

## User Amendment — Bidirectional Chat Trip-Length Changes — 2026-10-23

- The user clarified that trip duration changes must work both ways through
  chat: adding days updates the full schedule, and removing days shortens and
  updates the full schedule.
- Each added day must contain a grounded stop. Shortening preserves stops on
  retained days and may remove or reschedule existing stops from removed days;
  it does not create unsupported new places.
- `shorten_trip` uses an absolute target or a positive relative count of days to
  remove. Both directions keep the 1–7 day bound and use validate-before-commit.
- Code and durable project records are updated; the Compose image rebuilt and
  the container reached healthy status. Regression tests and live provider
  checks were not run.

## Trip-Length Verification And Local Rebuild — 2026-10-26

- Added regression checks that require a stop on each added day and reject
  changed retained stops or invented stops when shortening. Updated older UI
  and Vietnamese fallback assertions to match existing app wording.
- The 92-test host suite and Docker test target passed. Ruff, Black and isort
  passed; flake8 passed for app and test code. The all-repo flake8 command still
  reports three unused variables in ignored `artifacts/presentations/` scripts.
- The Compose runtime image rebuilt and the app container reached healthy
  status on `127.0.0.1:8503`. The root endpoint returned HTTP 200 and
  `/api/graph/image` returned HTTP 200 with an image/png response.
- No new live model, Tavily or LangSmith turn was run for this verification.

## Temporary ngrok Sharing — 2026-10-26

- The user requested a public tunnel to the locally running app and will supply
  the needed `.env` variable. The app was healthy at `127.0.0.1:8503` and its
  root endpoint returned HTTP 200 before tunnel setup.
- Added an opt-in Compose ngrok service targeting `app:8000`, with only
  `NGROK_AUTHTOKEN` passed to that container. The official image was pulled;
  `docker compose --profile ngrok config --quiet` passed.
- After the token was added to the ignored `.env`, the ngrok container started
  and logged its public HTTPS URL. External requests returned 200 for `/` and
  `/api/graph/image`; `POST /api/session` returned 201, and a cookie-backed
  `GET /api/session` returned 200. A bare session GET returned the expected 401.
- Compose recreated the app when `.env` changed. The new app reached healthy
  status, but prior in-memory sessions were lost. No model, Tavily or LangSmith
  turn was invoked during tunnel verification.
- The user then requested that ngrok be turned off. `docker compose --profile
  ngrok stop ngrok` stopped only the tunnel; `docker compose ps` still showed
  the app healthy, and its local root endpoint returned HTTP 200.

## Invalid OpenAI Key Diagnosis — 2026-10-26

- Replayed the user's exact two-day Hà Giang request against the local Compose
  service. The configured OpenAI Coordinator returned HTTP 401 with provider
  code `token_invalidated`. No Planner or Tavily call occurred; the date and
  request text were not the cause of this failure.
- The prior generic fallback hid the provider error. Coordinator now emits a
  stable authentication issue, and Chat response handling returns a localized
  code-owned explanation without calling the failed model again. It preserves
  the canonical plan and does not expose the provider exception to the UI.
- Two mocked locale cases were added. All 94 host and Docker tests passed;
  focused Black, isort, Ruff and app/test flake8 checks passed. The runtime
  image was rebuilt; the running container was left intact to preserve its
  session-only state. A new valid `OPENAI_API_KEY` is required for live planning.

## User Decision — Automatic Ollama Fallback — 2026-10-26

- The user requested Ollama when the OpenAI API is unavailable. Roles assigned
  to OpenAI now try one local Ollama structured-output call after an OpenAI API
  failure, using a separately configured Ollama model. Explicit Ollama roles
  remain Ollama-only.
- The prompt, schema and trace metadata remain the same across that retry;
  graph, search and repair limits and validate-before-commit still apply. If
  both providers fail, the previous plan remains current and the app gives a
  safe error. ADR 0010 records the changed provider policy.
- The host had Ollama 0.9.0 and `qwen2.5:3b` installed but its server was
  initially stopped. After starting it, a live call with an intentionally
  invalid OpenAI key returned a structured Ollama response. A full live Hue
  turn with the same invalid key committed with three Tavily citations, one
  search, zero repairs and six graph steps. LangSmith was not checked.
- Sixteen new fallback cases and updated provider-construction assertions
  contributed to 110 passing host tests. isort, Black, flake8, Ruff and
  `git diff --check` passed. The Compose runtime image built successfully. The
  one-shot image also committed a Hue plan through host Ollama with one entry,
  one Tavily search, no repair and no validation issues. The running app was
  initially left intact. At the user's subsequent request, Compose recreated
  it from image
  `sha256:29d02ba30f145eab4731c980f3cef38d353560acbe81e6b4a26d27b509ca8097`.
  It reached healthy status; the root and graph PNG returned HTTP 200 and
  session creation returned 201. Existing in-memory sessions were cleared.
  The earlier ngrok stop state was restored after it appeared running during
  preflight; the app remained healthy.

## User Decision — Apple M1 Inference — 2026-10-26

- The user observed that no Ollama container was running. The opt-in Compose
  `ollama` service was started and became healthy; `ollama-init` exited 0 after
  pulling `qwen2.5:3b` (1.9 GB) into the named model volume. The app reached
  `http://ollama:11434` and an invalid-key live Hue turn committed one entry
  with one Tavily search, zero repairs and no validation issues.
- The user then requested use of the Apple M1 chip. The Ollama Linux container
  reported `100% CPU`, consistent with Ollama's documented lack of Apple GPU
  passthrough in Docker Desktop. Native Ollama on macOS reported `100% GPU`.
- The ignored `.env` now sets
  `GTP_COMPOSE_OLLAMA_BASE_URL=http://host.docker.internal:11434`. Compose
  recreated the app and it reached healthy status. The app container reached
  the host Ollama endpoint and returned a structured response through the
  OpenAI-to-Ollama fallback with an intentionally invalid OpenAI key. Ollama.app
  was opened to own the native server. The Ollama container remains healthy as
  an idle CPU option; its model was unloaded. Ngrok was stopped again.

## User Decision — Testing-Agent Security Skill — 2026-10-27

- The user requested review of Cloudflare's `security-audit-skill` and a
  security capability for the project testing agent. Installed the upstream
  `security-audit` skill project-locally from main at
  `c1c8a8c1471069fb0e188eeaff69b8e8db6564a8`, including its MIT license.
  The testing agent now checks changed trust boundaries and loads the skill for
  explicit security review assignments.
- Cloudflare's full audit workflow requires independent verification and an
  OS-enforced sandbox for target-controlled execution. This task configured the
  agent; it did not run a codebase security audit or establish that the app has
  no vulnerabilities. ADR 0001 records the development-agent change. The
  skill validator, testing-agent TOML parser, both Node.js syntax checks and
  `git diff --check` passed. Application tests were not run for this
  configuration/documentation change.

## Scoped Security Review And Availability Fixes — 2026-10-27

- Before the requested commit/push, two read-only agent passes reviewed the
  pending code and adjacent HTTP, model, trace and UI trust boundaries. The
  testing pass found that four worker threads did not bound the shared queue:
  anyone able to create many browser sessions could submit one turn per
  session and retain unbounded queued work. The 60-second OpenAI timeout and
  one Ollama fallback attempt increase the duration of occupied slots.
- `TurnRunner` now reserves at most eight running/queued turns per process and
  releases each slot when its Future completes, even without a poll. The HTTP
  adapter rejects overload with a localized 429 before changing conversation,
  response or pending state; Streamlit displays a localized busy error.
- Independent retest found a second path through unlimited session creation.
  `SessionStore` now caps retained sessions at 1,024, expires idle sessions
  after one hour, retains only still-running turns during expiry, and replaces
  the prior session atomically on reset. New sessions receive a localized 503
  at capacity. A final local review caught completed but uncollected Futures
  that would otherwise avoid expiry; the regression now covers that case.
- Focused sandboxed tests passed 15 and the full suite passed 122. The test
  container had no network, a read-only target, a sanitized dummy environment,
  bounded CPU/memory/processes/files and a 180-second limit. Isort, Black,
  flake8, Ruff and `git diff --check` passed. No live model/search/tracing
  service or deployed endpoint was probed. The running app image was not
  recreated, so its existing session-only plans remain in memory.
- The ngrok tunnel was unexpectedly running despite the earlier stop decision.
  Stopped only its container; the app remained healthy. Public ingress abuse
  controls, HTTPS cookie transport and automatic LangChain trace retention
  remain deployment/privacy checks; this scoped review is not a complete
  codebase security audit.

## User Decision — Local-only Codex Tooling — 2026-10-28

- The user requested removal of `.codex/` from repository tracking while keeping
  its contents on this machine. Git now ignores the directory and its 80 tracked
  files were removed from the index with `git rm --cached`.
- The Docker test stage no longer copies the local hook; hook-specific tests skip
  when it is absent. Repository quality commands no longer require the optional
  local file. ADR 0001 records the amended tooling scope.
- Host pytest passed 111 tests; Docker test target passed 109 with one skipped
  hook module. Isort, Black, Ruff and diff checks passed. Repo-wide flake8 still
  reports three earlier F841 findings in `artifacts/presentations/update_deck.py`.

## User Amendment — Share Reviewed Codex Tooling — 2026-10-28

- The user clarified that project-wide `.codex` agents, hooks and skills should
  remain in the repository. Personal configuration and local state must not be
  pushed, including authentication, sessions, archived data, API keys, OAuth
  tokens, passwords, logs, caches, worktrees and management data.
- The prior staged deletion of 79 shared files was reversed. Only
  `.codex/config.toml` is staged for removal; its local copy remains. The broad
  `.codex/` ignore rule protects new local files from ordinary `git add`.
- The original Docker hook copy and hook test were restored because the hook is
  shared. The previous Docker result of 109 passed and 1 skipped describes the
  temporary local-only setup and is not evidence for this revised selection.
- A concurrent remote commit added testing and security guidance under
  `.codex/`. After merging, 102 shared files are tracked. The full tracked
  `.codex` set had zero high-confidence secret-pattern and sensitive-name hits;
  personal `config.toml` still exists locally and is ignored by Git.
- After merge, host pytest passed 122 tests. Isort, Black, Ruff, focused flake8,
  JSON parsing and diff checks passed. Full flake8 still reports the same three
  F841 findings in ignored `artifacts/presentations/update_deck.py`.

## User Decision — Generic Model Examples — 2026-10-28

- Remove the development-agent model column from README. Use
  `<YOUR_MODEL_NAME>` in `.env.example` and README setup commands instead of
  naming specific models. Detailed historical verification artifacts remain
  unchanged; README summaries no longer name the models used in those runs.
