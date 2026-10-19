# Project Status

Last updated: 2026-10-19

## Current Milestone

Milestone 1: executable city/place sightseeing vertical slice.

The active product scope is defined by `docs/project-charter.md` and
`docs/implementation-plan.md`. Older three-week POC artifacts remain historical
background only.

## Progress Snapshot

| Area | Status | Evidence |
|---|---|---|
| Scope reset | Complete | Charter, implementation plan, current log and ADR 0004/0009 |
| Runtime package | Complete | Coordinator/Planner/Chat graph, typed providers and validators |
| Streamlit app | Complete | Session-only itinerary/chat plus read-only graph page |
| Tests | 82 passed | Core, async UI, graph-image, photo, chat-edit/source eval, AppTest, web API and model-provider coverage |
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
| No-local API defaults | Verified in Compose | Container resolves to OpenAI `gpt-5.5` / `gpt-5.4-mini` / `gpt-4.1`; root and graph image return HTTP 200 |

Planning progress is not implementation progress. Only executable artifacts and
actual checks count as completion evidence.

## Done

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
  Coordinator uses `gpt-5.5`, Planner uses `gpt-5.4-mini`, and Chat uses
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
  with one search and no repair. Docker's internal Ollama profile remains
  unrun.
- With no local Ollama server available on this machine, changed `.env` to use
  OpenAI for all roles with the requested Planner/Chat models, and made the same
  configuration the default in `.env.example`. Parsing `.env` and the rebuilt
  container resolve to `gpt-5.5`, `gpt-5.4-mini` and `gpt-4.1`; the 49 focused
  and 82 full host/Docker tests and standard quality checks passed. The rebuilt
  Compose app is healthy and returns HTTP 200 for the root page and graph PNG.
  No live model API request was made.

## Now

1. Manually verify the JavaScript UI at phone and desktop widths, including
   chat → graph → chat during a pending turn. A browser was unavailable for this
   implementation check.
2. Label sources from representative live plans and measure relevance, place
   coverage and host diversity before a broad demo.
3. Exercise additional live edit intents, especially reorder and replace, with
   separate evidence from the offline gate.
4. Rebuild the runtime container after Docker becomes available so the new Chat
   model default is included in the image.

## Next

1. Add deployment/authentication only under a separate decision.

## Blockers And Risks

- Live provider behavior still depends on local credentials and network access.
- Coordinator's default runtime model is `gpt-5.5`; Planner defaults to
  `gpt-5.4-mini` and Chat to `gpt-4.1`. There is no silent provider fallback.
  Missing or unavailable
  configuration returns a safe response and preserves the previous plan.
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
- Native Ollama evidence covers one all-local `qwen2.5:3b` create-trip flow and
  one mixed `gpt-5.5`/`qwen3:4b` create-trip flow, plus a Compose-app HTTP
  create-trip flow to native Ollama. The internal Compose profile and chat edits
  have not yet been run live. Providers do not fall back to OpenAI.

## Important Files

- `docs/project-charter.md`
- `docs/implementation-plan.md`
- `docs/learning-log/2026-10-14-scope-reset.md`
- `docs/adr/0004-city-sightseeing-two-agent-runtime.md`
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
- `docs/adr/0005-visual-itinerary-enrichment.md`
- `docs/adr/0006-photo-only-itinerary-and-graph-inspection.md`
- `docs/adr/0010-configurable-openai-ollama-model-provider.md`
- `docs/adr/0007-session-owned-background-turns.md`
- `Dockerfile`
- `compose.yaml`
- `docs/progress/roadmap-progress.json`
