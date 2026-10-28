# Project Status

Last updated: 2026-10-28

## Current Milestone

Milestone 1: executable city/place sightseeing vertical slice.

The active product scope is defined by `docs/project-charter.md` and
`docs/implementation-plan.md`. Older three-week POC artifacts remain historical
background only.

## Progress Snapshot

| Area | Status | Evidence |
|---|---|---|
| Scope reset | Complete | Charter, implementation plan, current log and ADR 0004/0009/0011/0012 |
| Runtime package | Complete | Coordinator/Planner/Chat graph, typed providers and validators |
| Streamlit app | Complete | Session-only itinerary/chat plus read-only graph page |
| Tests | 122 passed | Full offline suite in a network-disabled, read-only container with current runtime dependencies and local test tools |
| Live integration | Passed | OpenAI/Tavily/LangSmith smoke recorded under `docs/experiments/` |
| Local container | Passed | Test/runtime images, health, non-root and live provider checks |
| Chat editing | Passed | Trip extension plus eight prior offline eval cases and live two-turn smoke |
| Source quality evaluation | Offline baseline | 16 labelled synthetic citations; live relevance not measured |
| Vietnamese chat | Passed | Vietnamese AppTest/fallback and live add-place response |
| Visual itinerary | Complete | Source-backed photos; route map removed by user request |
| Graph inspection | Complete | PNG from `get_graph_image()` fits the Streamlit and JavaScript graph views; SVG fallback; offline coverage |
| Async page navigation | Implemented | Background Future, exact-once session integration; browser QA pending |
| JavaScript/Tailwind UI | Implemented | React itinerary/chat/graph, FastAPI session adapter, optional credited photos; browser QA pending |
| Configurable model provider | Passed on host and Compose app | Active mixed routing and an HTTP Compose-app Hue plan committed with OpenAI `gpt-5.5` Coordinator and Ollama `qwen2.5:3b` Planner/Chat |
| No-local API defaults | Historical Compose verification | Earlier container resolved to OpenAI `gpt-5.5` / `gpt-5.4-mini` / `gpt-4.1`; root and graph image returned HTTP 200 |
| Current Planner OpenAI default | Local app verified | `gpt-6.1-terra` with 60-second per-call timeout and JSON Schema URL validation; live full graph turn committed four sourced Huế entries in 41.3 seconds; 113 tests passed; app healthy, root/graph HTTP 200 |
| Shared Tavily tool node | Verified offline and with one live request | Planner/Chat route through one graph node; one live Chat call returned five sources and matching `tool.tavily.*` events; rebuilt Compose app healthy |
| Bilingual webapp | Implemented; build/static checks pass | Session-scoped Vietnamese/English preference; focused existing API/runner/chat-context suite 14 passed (no locale-specific test added); React build and Python static checks passed; browser QA not run |
| Chat trip duration | Offline verified; image built | Shortening now creates a deterministic Planner candidate from the current plan, preserving retained entries and their source data exactly; 117 host tests and Python quality gates pass. New image built; running container not recreated because it owns session-only plans |
| Temporary ngrok sharing | Verified, now stopped | Public root and graph PNG returned 200; session POST 201 and cookie-backed GET 200; app remains healthy locally |
| Invalid model key diagnosis | Reproduced; error handling verified offline | Exact Hà Giang request received OpenAI HTTP 401 `token_invalidated` before search; 94 host/Docker tests passed; runtime image rebuilt but running app retained its sessions |
| OpenAI to Ollama fallback | Deployed with native MLX fallback | Any OpenAI SDK `OpenAIError`, including HTTP 400/404, makes one Ollama attempt. A rebuilt app container returned structured output after an invalid-key OpenAI call through MLX |
| Apple M1 Ollama deployment | Native MLX GPU active | Ollama v0.40.10 runs the configured MLX model with runner `mlx` at `100% GPU`; the app reaches it through `host.docker.internal` and serves HTTP 200. `qwen2.5:3b` was removed from native and container stores; the CPU Ollama container is stopped |
| Model-name configuration | Environment-only identifiers | Runtime source contains no model identifiers; Coordinator, Planner, Chat, Ollama fallback and JSON-schema model selection load environment values and reject missing required names |
| Agent latency/token optimization | Prompt payloads reduced; offline tests passed | Planner now sends one chronological plan projection without duplicated source records/request text; Chat receives visible schedule and summary instead of full plan JSON. End-to-end latency and provider token usage have not been benchmarked |
| Turn and session capacity | Offline verified; running app image unchanged | At most eight queued/running turns and 1,024 retained sessions per process; idle sessions expire after one hour, including uncollected completed turns. HTTP returns 429/503 without changing the rejected session. 15 focused and 122 full sandboxed tests passed |

Planning progress is not implementation progress. Only executable artifacts and
actual checks count as completion evidence.

## Done

- Reviewed project `.codex/` tooling for sharing. The 102 agent, hook
  and skill files remain tracked; personal `.codex/config.toml` is removed from
  the index and preserved locally. Git ignores new `.codex/` state by default.
  Authentication, sessions, archived data, keys, tokens, passwords, logs,
  caches, worktrees and management data remain local. Verification for this
  revised selection: 122 host tests passed; isort, Black, Ruff and focused
  flake8 passed. Full flake8 retains three existing F841 findings in ignored
  presentation artifacts.

- Bounded the shared background turn queue to eight running/queued turns per
  process and the HTTP session store to 1,024 entries with one-hour idle
  expiry. Reset replaces the old session atomically. A completed Future
  releases its slot even when the browser never polls; overload returns a
  localized 429 or 503 before changing the rejected session, and Streamlit
  shows a localized busy message. A network-disabled, read-only container
  passed 15 focused and 122 full offline tests; isort,
  Black, flake8, Ruff and diff checks passed. The local app container was not
  recreated, preserving its current in-memory sessions. ADR 0007 records the
  queue decision. The security review was scoped to the pending changes and
  adjacent trust boundaries, not a full codebase audit.
- Added the project-local Cloudflare `security-audit` skill and connected it to
  the Codex testing agent for explicit security reviews. Routine testing now
  assesses changed trust boundaries and adds focused offline regressions when
  warranted. Full audits still require the skill's OS-enforced sandbox and
  independent verification; this configuration change is not an application
  security audit. ADR 0001 records the development workflow decision.
- Moved runtime model identifiers to environment configuration. Live service
  construction now requires the three role model variables and Ollama fallback
  model variable; `GTP_OPENAI_JSON_SCHEMA_MODELS` controls JSON-schema adapter
  selection without identifying models in source. Synthetic test names replace
  actual provider identifiers in fixtures. `.env` selects the current MLX
  fallback, and the Compose Ollama initializer no longer embeds a model name.
  Isort, Black, flake8, Ruff and diff checks passed; the test suite was not run
  for this environment refactor.
- Fixed trip shortening failures. The Planner now computes a shorter candidate
  from the validated current itinerary, keeping every retained-day entry and
  source reference byte-for-byte and removing stops only after the new final
  day. This avoids requiring a model to regenerate an unchanged full itinerary
  and its nested sources. The graph regression verifies a relative one-day
  reduction commits with zero search and repair calls. Full host suite: 117
  passed; isort, Black, flake8, Ruff and diff check passed. The local Compose
  app still runs the previous image; container recreation is deferred because
  it clears session-only plans.
- Switched this Mac's fallback deployment to native Ollama v0.40.10 and
  `qwen3.5:4b-mlx`. The official app ZIP matched its published SHA-256 and
  passed macOS code-signature verification. The model returned structured
  `ChatResponse` output on the host and from the app container; an invalid-key
  OpenAI attempt in the rebuilt app container also returned through MLX.
  `ollama ps` showed runner `mlx` at `100% GPU`. The app is healthy and its
  root returns HTTP 200. Removed `qwen2.5:3b` from native and container model
  stores, then stopped the idle CPU Ollama container. Recreating the app cleared
  its session-only state. The earlier Ollama.app is retained temporarily as a
  local backup.
- Reduced redundant agent prompt input and requested concise outputs. Planner
  serializes the existing schedule once in user-visible order, removes source
  references duplicated in the separate trusted source list, and omits the
  repeated raw user message/request object. Chat receives the visible itinerary
  and Planner summary instead of a second full-plan JSON payload. Coordinator,
  Planner and Chat are asked for concise summaries/responses. Two offline
  regressions pass; Ruff, Black and diff check pass. No live token or latency
  comparison was run. The model identifiers now load from environment, and the
  OpenAI adapter factory uses the configured structured-output model list.
- Raised the shared OpenAI per-request timeout from 20 to 60 seconds after the
  user reported model substitutions timing out. Current Planner remains
  `gpt-6.1-terra`; a live full graph run took 41.3 seconds and committed a
  four-entry sourced Huế plan without issues. The 113-test suite and all Python
  quality gates passed. The rebuilt Compose app is healthy; root and graph
  image return HTTP 200. Container recreation clears session-only state.
- Expanded OpenAI-to-Ollama fallback to every OpenAI SDK `OpenAIError`,
  including HTTP 400 and 404. The existing one-attempt wrapper still preserves
  prompt, schema and trace metadata; local validation and application errors
  do not switch providers. Focused fallback tests passed 18, full host tests
  passed 113, and isort, Black, flake8, Ruff and diff check passed. This change
  is deployed in the running app. An invalid-key call returned structured
  output through native MLX; HTTP 400/404 remain covered by offline cases.
- Fixed Terra plan creation: OpenAI rejected Pydantic's `format: uri` in the
  Planner JSON Schema with HTTP 400, so no candidate reached graph state. The
  Terra adapter now sends the same generated schema without only that format
  marker and validates output against the original Pydantic model locally.
  Planner failures now return a code-owned explanation without asking Chat to
  invent a text-only itinerary. The 111-test suite and all Python quality gates
  passed. A fresh Compose image is healthy; a live Huế request committed four
  entries and every entry has returned source references. Root and graph image
  returned HTTP 200. Recreating the app cleared session-only state.
- Replaced Planner's OpenAI default with `gpt-6.1-terra`, using JSON-schema
  structured output and `reasoning_effort="none"`. Coordinator, Chat and
  Ollama fallback behavior are unchanged. Focused tests passed 70; the full
  suite passed 111. Isort, Black, Ruff and diff check passed; repo-wide flake8
  retains three existing F841 findings in
  `artifacts/presentations/update_deck.py`. A direct live call returned a
  structured `ChatResponse` in 3.91 seconds, and the installed LangChain
  package bound the full Planner schema offline. The rebuilt app is healthy,
  resolves OpenAI `gpt-6.1-terra` with Ollama `qwen2.5:3b` fallback, and serves
  root/graph at HTTP 200. Recreating it cleared session-only state.
  End-to-end Planner latency is unmeasured.
- At the user's request, restored the uncommitted Planner latency, compact
  output, day/time edit and shared-timeout refactor work to commit `8aea1a9`.
  The committed OpenAI-first, one-attempt Ollama fallback remains in place.
  This rollback also removes the uncommitted day/time preservation fix; the
  known multi-entry day-move data-loss case remains unresolved in this code.
  The restored 110-test suite, isort, Black, Ruff and diff check passed.
  Repo-wide flake8 retains three pre-existing F841 errors in
  `artifacts/presentations/update_deck.py`. The running container has not
  been rebuilt from this rollback.
- Started the opt-in Ollama Compose profile and pulled `qwen2.5:3b` into its
  persistent volume. The app reached it at `http://ollama:11434`; a live
  invalid-key Hue turn committed one grounded entry with one Tavily search,
  no repair and no validation issues. That Linux container used CPU on this
  Apple M1 Mac. At the user's request, the app was then switched back to
  native Ollama at `http://host.docker.internal:11434`. A structured fallback
  call from the app succeeded, and host `ollama ps` showed `100% GPU`.
  Ollama.app now serves the native endpoint; the CPU container remains healthy
  and idle as an optional route. Ngrok remains stopped.
- Added one automatic Ollama attempt for OpenAI authentication, rate-limit,
  server, connection or timeout failures, using a separately configured local
  fallback model. Explicit Ollama roles remain Ollama-only; malformed model
  output does not trigger failover. The 110-test host suite and all Python
  quality checks passed. A live adapter call with an intentionally invalid
  OpenAI key returned a structured Ollama response; a full live Hue turn with
  the same invalid key committed one plan with three Tavily citations, one
  search and no repair. The Compose runtime image built successfully, and a
  one-shot container from that image also committed a Hue plan through the
  fallback with one entry, one search and no validation issues. LangSmith was
  not checked. At the user's request, the running Compose app was then
  recreated from the new image. It reached healthy status; the root page and
  graph PNG returned HTTP 200 and session creation returned HTTP 201. Prior
  in-memory sessions were cleared by the restart.
- Reproduced the Hà Giang request with the container's current OpenAI
  configuration. Coordinator received HTTP 401 `token_invalidated`; Planner and
  Tavily did not run. The graph now gives a localized authentication error and
  skips further model calls on this failure, preserving the current plan. The
  94-test host and Docker suites passed and a runtime image was rebuilt. The
  running app was not recreated, so existing in-memory sessions remain owned by
  that container. This was the pre-fallback diagnostic; the new local Ollama
  path has since committed a sourced plan with an invalid OpenAI key.
- Added an opt-in ngrok Compose profile for temporary sharing of the existing
  HTTP app. It receives only `NGROK_AUTHTOKEN`, forwards to `app:8000`, and
  writes its assigned URL to container logs. The official image was pulled and
  Compose configuration passed. The running public HTTPS URL returned 200 for
  `/` and `/api/graph/image`; a cookie-backed session POST returned 201 and
  its subsequent GET returned 200. Compose recreated the app when `.env`
  changed, so prior in-memory sessions were lost.
- Stopped only the ngrok container at the user's request. The app stayed healthy
  on `127.0.0.1:8503` and its root endpoint returned HTTP 200.
- New trip proposals ignore the previous session itinerary. Chat can extend a
  trip with grounded stops on every added day, or shorten it while preserving
  retained-day stops and removing or rescheduling later stops. Requests to move
  a stop beyond the trip length stop before Planner. Two duration regression
  tests were added; 92 host and Docker tests passed on 2026-10-26. The rebuilt
  Compose app is healthy at
  `127.0.0.1:8503`; `/` and `/api/graph/image` returned HTTP 200.
- Required a complete Planner plan in structured output after a model response
  with no plan surfaced as `candidate_required`. Omitted or null plans now
  report `planner_model_failure` and preserve the current itinerary; four
  regression cases cover create and edit turns. The 82-test host suite and all
  formatting/lint gates passed. A separate rebuilt-image live Hue run with the
  active `qwen2.5:3b` configuration committed two entries with one search and
  no repair. The running app was not restarted, preserving its session state.
- Replaced the archived POC scope with the city/place sightseeing product scope.
- Accepted ADR 0004 for the initial runtime and ADR 0009 for the current
  Coordinator/Planner/Chat architecture.
- Preserved ADR 0001 as the development-agent/tooling decision; Codex helper
  roles remain separate from the webapp runtime Coordinator, Planner and Chat.
- Implemented Coordinator/Planner/Chat with role-specific model defaults:
  Coordinator uses `gpt-5.5`, Planner uses `gpt-6.1-terra`, and Chat uses
  `gpt-4.1`. Typed
  provider boundaries and code-enforced graph/search/repair limits remain in
  place.
- Implemented validate-before-commit input, schedule, opening-hours and source
  provenance checks. Failed candidates preserve the previous plan.
- Temporarily removed `source_place_mismatch` from the commit gate at the
  user's request after repeated false rejections. Returned-URL provenance,
  HTTP(S), required-source and opening-hours checks remain active.
- Added deterministic checks that create/add/remove/replace/reorder/day/time
  candidates actually satisfy the delegated change before commit.
- Unverified opening hours are normalized to the explicit `unverified` label;
  model-authored advisory notes no longer block a deterministically valid plan.
- Added the session-only Streamlit form/chat UI and offline AppTest coverage.
- Confirmed the Streamlit entrypoint starts local-only and returns health 200.
- Verified one real Hue plan with OpenAI, Tavily and LangSmith. The final live
  run committed five returned citations and propagated `thread_id` to all 14
  matching root/child runs.
- Added a multi-stage, locked Docker build with an in-image test target and a
  non-root Streamlit runtime. The container test ran 19/19 tests; Compose health,
  safe failure and live Hue commit checks passed locally.
- Aligned reorder validation with the chronological order shown in Streamlit;
  list-only reorder and no-op edit claims are rejected.
- Kept repair sources tied to actual provider results or the committed plan;
  fabricated candidate URLs cannot become trusted during repair.
- Added eight initial versioned offline chat-edit eval cases and AppTest coverage for a
  successful edit followed by a rejected edit that preserves the new plan.
- Verified a live Hue create-then-remove chat flow on one session: revision 1
  with five entries became revision 2 with four, keeping all other entries.
- Added an offline source-quality evaluator and 16 labelled synthetic citations
  across five plans. It reports relevance, place coverage, source classes and
  host diversity without changing runtime commit policy.
- Migrated the original smoke to LangSmith `runs.query()`; a live Hue run found
  25 matching runs with the same session `thread_id`.
- Added an offline regression for `Lô Lô Chải`/`Lo Lo Chai Village` add-place
  matching and rebuilt the healthy local runtime container with the fix.
- Rechecked the exact `gpt-5.5` model and a representative Lô Lô Chải add
  request in the container. The plan committed revision 2, preserved the
  prior stop and passed validation with one Planner search.
- Set Vietnamese as the default chat/UI language, including model instructions
  and safe fallback responses; a live Vietnamese add request received a
  Vietnamese reply and committed the requested place.
- Installed UI/UX Pro Max for this project and added source-backed place images.
  The earlier map/car experiment was removed at the user's request; ADR 0006
  records the decision. The separate graph page displays the PNG returned by
  `get_graph_image()` without invoking a planning turn.
- After the graph-image update, host and Docker test targets each passed 47 tests;
  Black, isort, flake8, Ruff and `uv lock --check` passed. The Compose runtime
  was rebuilt and reached healthy status on `127.0.0.1:8503`.
- Added a bounded background turn runner and session-owned pending Future so a
  model/search turn continues while the user visits another Streamlit page.
  Nine focused async/UI tests and the full 50-test host and Docker suites passed;
  ADR 0007 records exact-once result integration and process-restart limits.
- Built the current React/Tailwind itinerary, chat and read-only graph interface
  under ADR 0008, with a same-origin FastAPI adapter and session-owned plan.
  Optional Commons photos show creator/license/source and never block a plan.
  The container now serves the new frontend on port 8000 internally and reached
  healthy status at `127.0.0.1:8503`. Frontend typecheck/build, 56 host and Docker tests,
  Python formatting/lint checks and HTTP asset/graph checks passed.
- Removed provider-owned source inventory from the Planner model-output schema,
  so an overlong model-authored `returned_sources[].snippet` cannot fail before
  trusted-source grounding. Tavily prompt snippets remain capped at 1,000
  characters; grounded `SourceReference` snippets accept up to 4,000. Focused,
  full host and offline Docker test runs passed, and the rebuilt runtime is healthy.
- The JavaScript graph view now requests the PNG from `get_graph_image()` through
  a read-only endpoint. Its image and SVG fallback scale within the page panel
  and cannot create horizontal overflow. A web API contract test confirms PNG
  delivery without a planning turn; the full host suite passed 57 tests. The
  running local adapter returned `200 image/png` with 24,241 bytes; its SVG
  fallback also returned HTTP 200.
- Added role-specific runtime model defaults. Coordinator keeps `gpt-5.5`,
  while Planner and Chat use `gpt-5.4-mini`; configuration wiring and the full
  61-test host suite pass. This does not claim a new live provider run.
- Moved response generation into a dedicated Chat node while Coordinator now
  only classifies and routes work. Added `extend_trip` with absolute or relative
  day counts, resolved against the canonical plan before Planner runs. Missing,
  non-increasing and over-seven-day requests stop before search; a committed
  extension preserves existing entries and adds a grounded stop in the new day
  range. The focused suite passed 44 tests, the full host and Docker suites each
  passed 64, frontend checks/build passed, and the rebuilt runtime is healthy at
  `127.0.0.1:8503`.
- Fixed the Planner-to-Chat context handoff. A committed turn now gives Chat the
  Planner summary and the validated plan, including schedule entries and
  grounded source titles/URLs. A rejected turn gives Chat only the validation
  issues and retained prior plan, so it cannot describe a rejected candidate as
  applied. Focused tests passed 44 cases; the full host, Docker build-stage and
  offline Docker suites each passed 64. The rebuilt runtime is healthy at
  `127.0.0.1:8503` and serves the app and graph PNG with HTTP 200.
- Replaced the inline JavaScript chat composer with a lower-right floating chat
  widget. The panel opens from an icon button, stays available on the itinerary
  and graph views, focuses its input, supports Escape-to-close, and renders user
  and assistant turns as right/left conversation bubbles with pending, result
  and error states. Frontend typecheck and production build passed;
  real-browser responsive QA remains pending.
- Restyled the JavaScript interface with a light blue and navy visual system.
  The page uses a soft blue background, white surfaces, navy text and blue
  primary/focus accents so the interface stays bright without losing contrast.
  Frontend typecheck and production build passed; the browser surface was
  unavailable for live visual inspection.
- Added explicit OpenAI/Ollama model-provider configuration. `RuntimeConfig`
  validates the global provider, optional per-role overrides and all three role
  model names; the service resolves each adapter to the existing OpenAI adapter
  or typed `ChatOllama` structured-output adapter without fallback. Compose now
  has an opt-in persistent Ollama profile and initializer for `qwen2.5:3b`. Its
  app endpoint now defaults separately to host Ollama through
  `GTP_COMPOSE_OLLAMA_BASE_URL`; the profile requires an explicit internal
  `http://ollama:11434` override. ADR 0010 records the provider decision.
  Mocked/offline checks cover configuration, routing and
  structured calls. Native `qwen2.5:3b` completed structured output and a
  create-trip smoke. The selected mixed assignment then committed a one-day Hue
  plan with OpenAI `gpt-5.5` as Coordinator and local `qwen3:4b` as Planner and
  Chat: four entries, one Tavily search, no repair and no validation issues.
  The active `qwen2.5:3b` Planner/Chat assignment then returned structured
  output inside the Compose app and committed a two-entry Hue plan with one
  search and no repair.
  LangSmith returned 25 matching runs with the same `thread_id`. The full
  78-test suite and required formatting, lint, lockfile, Compose and diff checks
  passed. The Compose app endpoint now reaches host-native Ollama at
  `host.docker.internal`; its fresh HTTP API Hue smoke committed four entries
  with one search and no repair. Docker's internal Ollama profile was later
  verified as recorded in the Apple M1 deployment entry above.
- With no local Ollama server available on this machine, changed `.env` to use
  OpenAI for all roles with the requested Planner/Chat models, and made the same
  configuration the default in `.env.example`. Parsing `.env` and the rebuilt
  container resolve to `gpt-5.5`, `gpt-5.4-mini` and `gpt-4.1`; the 49 focused
  and 82 full host/Docker tests and standard quality checks passed. The rebuilt
  Compose app is healthy and returns HTTP 200 for the root page and graph PNG.
  No live model API request was made.
- Added session-only conversation context to both UIs. The JavaScript API
  rehydrates up to 12 conversation messages after page navigation or reload;
  reset starts a separate transcript. Coordinator receives the prior summary
  and at most eight 600-character messages, then gives Planner and Chat a
  1,200-character handoff summary rather than the raw transcript. Chat may
  request one structured function-call Tavily search for current facts, sharing
  the two-call turn budget with Planner. Search citations use actual provider
  sources and never change the plan. Both roles emit redacted search events with
  the same `thread_id`. All 88 host tests, frontend typecheck/build, formatting
  and lint checks passed. A live factual Chat request used one Tavily call,
  returned five sources and confirmed `chat.search.start/success` in LangSmith.
  The rebuilt Compose image is healthy and serves the app and graph PNG with
  HTTP 200. ADR 0011 and
  `docs/experiments/2026-10-19-live-chat-search-smoke.md` record the decision
  and evidence for the direct-call version.
- Replaced per-agent search execution with a shared `tavily_tool` graph node.
  Planner and Chat emit typed requests; the node is the only runtime caller of
  Tavily and returns normalized sources to the requesting role. It counts
  attempts before provider execution and records redacted `tool.tavily.*`
  events with requester and session `thread_id`. The graph remains bounded to
  8 nodes, 2 shared searches and 1 repair. The focused suite passed 67 tests,
  the full host suite passed 89, and the required formatter/lint/lock checks
  passed. A live Chat request used one search, returned five sources and
  confirmed `tool.tavily.start/success` with a matching `thread_id`. The rebuilt
  Compose image is healthy; `/` and `/api/graph/image` return HTTP 200. ADR 0012
  and `docs/experiments/2026-10-19-live-shared-tool-node-smoke.md` record the
  implementation and current evidence.
- Simplified the runtime flow without changing graph topology or policy. Removed
  unused role-level `RuntimeConfig` injection, one-field Planner/Chat result
  wrappers, two dead graph-state fields, a duplicate service search reference,
  and duplicate summary/history storage in `PendingTurn`. Session transcript
  and summary bounds now use the shared conversation constants in the HTTP
  adapter. Focused tests passed 63 cases and the full host suite passed 90;
  isort, Black, flake8 and Ruff passed. No live provider run or container
  rebuild was performed for this internal refactor.
- Refined the project Codex development roles and delivery skill from repository
  evidence. The coding role now covers the full product stack, agents preserve
  pre-existing dirty work and direct user corrections, and delivery defaults to
  no commit/push unless explicitly requested. The UI/UX skill now links a small
  local Travel Planner overlay while retaining its upstream catalog separately.
  This documentation/configuration update has static parse and diff evidence
  only; no application, frontend, container, browser or live-provider check ran.
- Added a Vietnamese/English language selector to the React app, Streamlit
  fallback and graph page. The locale is session-scoped, survives a new-trip
  reset, and is captured by each pending turn. New agent-authored content follows
  the selected locale; user text, place names, existing plan/transcript content
  and source evidence remain unchanged. The existing focused API/runner/chat
  suites passed 14 tests; frontend build and Python static gates passed. No
  browser, container or live-provider check is claimed.

## Now

1. Manually verify the JavaScript UI at phone and desktop widths, including
   chat → graph → chat during a pending turn. A browser was unavailable for this
   implementation check.
2. Label sources from representative live plans and measure relevance, place
   coverage and host diversity before a broad demo.
3. Exercise additional live edit intents, especially reorder and replace, with
   separate evidence from the offline gate.
4. Evaluate Chat answer accuracy and live source relevance across more than
   one factual question; the current live smoke verifies plumbing only.

## Next

1. Add production deployment/authentication only under a separate decision.

## Blockers And Risks

- Live provider behavior still depends on local credentials and network access.
- Coordinator's default runtime model is `gpt-5.5`; Planner defaults to
  `gpt-6.1-terra` and Chat to `gpt-4.1`. OpenAI API failures try local Ollama
  once, if reachable. If both providers fail, the previous plan is preserved.
- Tavily snippets can be incomplete; opening hours stay unverified unless a
  source result explicitly supports them.
- Live results can include broad travel pages or video sources. Current code
  validates URL provenance but temporarily does not enforce place-name token
  overlap; editorial quality, relevance and domain diversity remain measured
  outside the commit gate.
- The new live chat-edit smoke verifies a two-turn service flow; it does not
  inspect stored LangSmith runs or automate a live Streamlit browser.
- The source-quality corpus is synthetic and intentionally includes weak and
  irrelevant citations; its scores are a measurement baseline, not a claim
  about the quality of live Tavily recommendations.
- The representative Lô Lô Chải edit passed live on 2026-10-16; the original
  user's session-only plan was not available for exact replay.
- Vietnamese has live evidence for one add request; other edit intents and
  ordinary conversation have offline coverage but no separate live language
  sample yet.
- Public photo APIs can be unavailable. The app caps photo lookups at 12 stops
  and retains the text/source itinerary when no licensed image is resolved.
- Pending turns are in-process and session-only. A Streamlit process restart,
  browser-session loss or container replacement drops them; active Python
  threads cannot be safely cancelled from the UI.
- A Docker test-target rebuild hit intermittent Docker Hub DNS failure; the
  normal runtime image rebuilt, started healthy and served HTTP 200.
- The delegated independent testing agent could not start its shell because of
  Windows `CreateProcessWithLogonW` error 1385. Primary-session targeted/full
  tests and all standard checks provide the recorded verification evidence.
- Project coding/testing subagents configured with `gpt-5.5` could not run in
  this Codex ChatGPT account. Primary-session container checks provide the
  recorded evidence; runtime OpenAI `gpt-5.5` calls remain verified separately.
- The JavaScript frontend has typecheck, build, mocked API and HTTP smoke
  evidence, but no real-browser responsive or live-provider acceptance yet.
- Shared `tavily_tool` has one live factual-question smoke. It confirms source
  return and trace propagation, but not broad factual accuracy, opening-hour
  verification or source relevance.
- Native Ollama evidence covers one all-local `qwen2.5:3b` create-trip flow and
  one mixed `gpt-5.5`/`qwen3:4b` create-trip flow, plus a Compose-app HTTP
  create-trip flow to native Ollama. The internal Compose profile and chat edits
  have not yet been run live. Explicit Ollama roles do not fall back to OpenAI.

## Important Files

- `docs/project-charter.md`
- `docs/implementation-plan.md`
- `docs/learning-log/2026-10-14-scope-reset.md`
- `docs/adr/0004-city-sightseeing-two-agent-runtime.md`
- `docs/adr/0011-bounded-session-context-and-chat-search.md`
- `docs/adr/0012-shared-tavily-tool-node.md`
- `src/grounded_travel_planner/`
- `src/utils/`
- `docs/experiments/2026-10-14-live-two-agent-smoke.md`
- `docs/experiments/2026-10-14-local-container-smoke.md`
- `docs/experiments/2026-10-15-live-chat-edit-smoke.md`
- `docs/experiments/2026-10-15-source-quality-baseline.md`
- `docs/experiments/2026-10-15-langsmith-query-v2-smoke.md`
- `docs/experiments/2026-10-15-lo-lo-chai-add-regression.md`
- `docs/experiments/2026-10-16-live-lo-lo-chai-add.md`
- `docs/experiments/2026-10-16-vietnamese-chat-smoke.md`
- `docs/experiments/2026-10-16-visual-itinerary-smoke.md`
- `docs/experiments/2026-10-18-ollama-local-smoke.md`
- `docs/experiments/2026-10-19-live-chat-search-smoke.md`
- `docs/experiments/2026-10-19-live-shared-tool-node-smoke.md`
- `docs/adr/0005-visual-itinerary-enrichment.md`
- `docs/adr/0006-photo-only-itinerary-and-graph-inspection.md`
- `docs/adr/0010-configurable-openai-ollama-model-provider.md`
- `docs/adr/0007-session-owned-background-turns.md`
- `Dockerfile`
- `compose.yaml`
- `docs/progress/roadmap-progress.json`
