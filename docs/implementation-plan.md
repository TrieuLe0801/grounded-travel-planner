# Implementation Plan

Status: Active
Last updated: 2026-10-17

## Phase 1A - Core Runtime — Implemented

Acceptance:

- Create an importable `grounded_travel_planner` package.
- Keep reusable modules in `src/utils/`.
- Add typed provider interfaces for model, search and tracing.
- Add LangChain `ChatOpenAI` structured-output adapter.
- Add Tavily search adapter that returns normalized URLs only.
- Add LangSmith trace sink that propagates one `thread_id`.
- Implement a LangGraph runtime with Coordinator, Planner and Chat nodes.
- Coordinator classifies and routes; Planner produces every candidate and owns
  all search calls; Chat writes the final response after policy validation.
- Keep `gpt-5.5` for Coordinator and use `gpt-5.4-mini` for Planner and Chat by
  default, with role-specific settings behind the model provider boundary.
- Validate input, schedule and source references before committing a candidate.
- Preserve the previous plan when validation fails.

Checks:

- Compile/import the package with local dependencies.
- Do not claim live OpenAI, Tavily or LangSmith verification until credentials,
  network and an executable flow are run.

## Phase 1B - Streamlit Webapp — Implemented

Acceptance:

- Streamlit itinerary/chat page with destination/place, start date and day count
  input, plus a separate read-only graph-inspection page.
- Session-only canonical plan and chat history.
- Chat can request add, remove, replace, reorder, trip extension, day and time
  changes.
- Ordinary chat does not mutate plan state.
- Render estimated durations, unverified hours, validation issues and sources.
- Smoke-run the app with `.env` credentials.

## Phase 1C - Tests And Live Gates — Verified

Acceptance:

- Mocked unit tests cover providers, graph routing, validation and service
  commit semantics.
- Live Tavily/OpenAI/LangSmith verification is recorded separately and never
  substitutes for deterministic tests.
- Full quality checks pass or blockers are documented.

## Verification Evidence

- `uv run pytest`: 19 passed on 2026-10-14.
- isort, Black, flake8, Ruff, `uv lock --check` and `git diff --check` passed.
- `scripts/live_smoke.py`: final run committed a one-day Hue plan with
  `gpt-5.5`, one Tavily call, one bounded repair and five returned citations.
- LangSmith query found 14 matching root/child runs, all with the same
  `thread_id` metadata.
- Detailed live evidence: `docs/experiments/2026-10-14-live-two-agent-smoke.md`.

## Planner Source Schema Hardening — Verified

Acceptance:

- Keep provider-owned `returned_source_urls` and `returned_sources` out of the
  Planner model-output schema and attach them only after trusted-source grounding.
- Keep Tavily/SearchResult snippets bounded to 1,000 characters before prompt use.
- Accept grounded `SourceReference` snippets up to 4,000 characters while
  retaining deterministic returned-URL provenance validation.
- Regress a model payload that includes an extra overlong `returned_sources`
  item without allowing that inventory into the committed candidate.

Evidence: 33 focused tests and 56 full host tests passed; isort, Black, flake8,
Ruff, `uv lock --check` and `git diff --check` passed. The rebuilt offline Docker
test image passed 56 tests with networking disabled, and the rebuilt Compose
runtime reached healthy status at `127.0.0.1:8503`.

## Phase 1D - Local Container — Verified

Acceptance:

- Multi-stage locked build with a dedicated offline test target.
- Final runtime contains production dependencies only and runs as a non-root
  user.
- `.env` is excluded from the build context; Compose injects it only at runtime.
- Streamlit listens inside the container on `0.0.0.0:8501`; the host mapping is
  loopback-only.
- Healthcheck, image history, log scan, environment-presence check and one live
  successful plan are recorded before repository push.
- Dockerfile and uv base images retain Linux arm64 support for the Mac M1.

Evidence: `docs/experiments/2026-10-14-local-container-smoke.md`.

## Phase 1E - Chat Editing Hardening — Verified

Acceptance:

- Number itinerary stops in the same chronological order used by Coordinator,
  Planner and reorder validation.
- Commit a chat edit only when the requested visible change is applied; reject
  no-op edits and preserve the prior plan on failure.
- Keep only provider-returned or previously committed sources across a repair.
- Exercise successful and rejected chat edits through Streamlit AppTest and a
  versioned offline evaluation set.
- Run a separate live create-then-edit service smoke with the same session ID.

Evidence:

- `uv run pytest`: 39 passed on 2026-10-15, including eight
  `data/eval/chat-edit-v1.jsonl` cases.
- isort, Black, flake8, Ruff, `uv lock --check` and `git diff --check` passed.
- `scripts/live_chat_edit_smoke.py` committed a Hue plan then removed one stop
  through chat, advancing revision 1 to 2 and preserving the other four stops.
- Detailed live evidence: `docs/experiments/2026-10-15-live-chat-edit-smoke.md`.

## Phase 1F - Source Quality Measurement — Offline Baseline Verified

Acceptance:

- Keep provenance validation as the runtime commit rule.
- Temporarily keep source-place token overlap out of the commit gate; the
  `source_place_mismatch` rule produced repeated false rejections. Continue to
  measure relevance offline until a replacement strategy is accepted.
- Use a versioned, manually labelled corpus to measure citation relevance,
  relevant-place coverage, source classes and normalized host diversity.
- Keep synthetic fixture metrics separate from live-source quality claims.

Evidence: 16 labelled synthetic citations in `data/eval/source-quality-v1.jsonl`,
offline evaluator and three focused tests, and
`docs/experiments/2026-10-15-source-quality-baseline.md`. The next acceptance
step is labelling representative live results before a broad demo.

## Trace Query Maintenance — Verified

The original live smoke now uses LangSmith `Client.runs.query()` in place of
deprecated `list_runs()`. Two offline fake-client tests passed. A new live run
found 25 matching root/child runs and the same `thread_id` on all of them.
Evidence: `docs/experiments/2026-10-15-langsmith-query-v2-smoke.md`.

## Add-Place Name Variant Follow-Up — Live Rechecked

An add request for `Lô Lô Chải` may be proposed as `Lo Lo Chai Village` by a
model. The validator now accepts this bounded spelling/descriptor variant,
requires a newly added matching place and keeps the prior stops. A focused
regression and the full offline suite passed. The rebuilt runtime container is
healthy. The initial live recheck stopped at OpenAI HTTP 429
`billing_not_active` before Planner ran; on 2026-10-16, a representative
container flow committed Lô Lô Chải at revision 2 with one Planner search and
no validation issues. The original user session was not replayed. Evidence:
`docs/experiments/2026-10-15-lo-lo-chai-add-regression.md` and
`docs/experiments/2026-10-16-live-lo-lo-chai-add.md`.

## Vietnamese Chat — Verified For Representative Flow

Acceptance:

- Accept Vietnamese chat requests and present the webapp's form/chat guidance
  in Vietnamese.
- Reply in Vietnamese for normal and committed turns, with Vietnamese
  deterministic fallback messages on model or graph failure.
- Keep place names and source titles faithful to user input and search results.

Evidence: `uv run pytest` passed 40 tests on 2026-10-16; the full formatting and
lint suite passed. A live Vietnamese add-place turn in the rebuilt container
committed Lô Lô Chải at revision 2 and received a Vietnamese assistant reply.
See `docs/experiments/2026-10-16-vietnamese-chat-smoke.md`.

## Phase 1G - Visual Itinerary — Photo Presentation

Acceptance:

- Install the project-local UI/UX Pro Max skill and apply its accessible,
  responsive design guidance to the Streamlit page.
- Add actual place photos with visible source and license credit, or a clear
  unavailable state.
- Failed visual lookups never block plan creation/chat edits or change the
  canonical session plan.
- Verify provider parsing with mocks and UI behavior with AppTest.

ADR 0005 records the earlier map design and ADR 0006 supersedes it after the
user requested removal of the geographic route view. Historical map/coordinate
checks remain recorded in `docs/experiments/2026-10-16-visual-itinerary-smoke.md`;
they do not describe the current UI.

## Graph Architecture Inspection — Acceptance

- Show a separate Streamlit page using the PNG returned by
  `TravelPlannerService.get_graph_image()`, including START/END, Coordinator,
  Planner, validators and repair. Retain an SVG fallback for render outages.
- Expose the actual node and edge list, and distinguish conditional branches.
- Opening this page does not call live providers, invoke a graph turn, or change
  the canonical session plan.

ADR 0006 records the page boundary. On 2026-10-16, the focused UI/photo/graph
tests passed 9/9; after the `get_graph_image()` integration, the full host and
Docker test suites each passed 47/47.
Black, isort, flake8, Ruff and `uv lock --check` passed. The rebuilt Compose
runtime reached healthy status on `127.0.0.1:8503`. Real-browser visual
inspection of the SVG has not been recorded.

## Phase 1H - Async Session Turns — Implemented, Browser Navigation QA Pending

Acceptance:

- Submit create/edit turns to a bounded background executor without blocking
  Streamlit page navigation.
- Capture deep copies of thread ID, message, current plan and request; workers
  never access Session State.
- Keep one pending turn per session, disable competing actions and integrate the
  response exactly once after polling.
- Preserve the captured plan and show a safe Vietnamese response if a worker
  fails unexpectedly.
- Continue the pending turn when the user visits the graph page and collect the
  result immediately after returning to chat.

ADR 0007 records the execution and ownership boundary. Nine focused async/UI
tests and the full 50-test host and Docker suites passed on 2026-10-16. AppTest
verifies a whole-page rerun as the page-return equivalent; real sidebar
multipage navigation remains a manual browser acceptance check.

## Phase 1I - JavaScript/Tailwind Interface — Implemented, Browser QA Pending

Acceptance:

- Serve the React/Tailwind itinerary and chat with a same-origin FastAPI adapter.
- Keep the chat composer in a lower-right floating panel opened by an accessible
  icon button; support responsive sizing, keyboard close and focus on open.
- Keep one server-owned canonical plan per opaque browser session. A pending
  turn continues when the user opens the read-only graph view.
- Render the compiled graph as the responsive PNG from `get_graph_image()`;
  constrain it to the graph panel and retain the SVG fallback for render errors.
- Display source references, estimated durations, unverified opening hours and
  optional Commons photos with creator, license and file-page credit.
- Preserve the previous plan after a rejected edit; show validation feedback.
- Build and typecheck the frontend, test the adapter with mocked providers, and
  start the container with a healthy HTTP response.

ADR 0008 governs this interface. The Streamlit implementation remains in the
repository during migration. Offline browser interaction and responsive visual
inspection remain open until a browser is available. The frontend and API
tests do not constitute a new live OpenAI/Tavily/LangSmith verification.

The JavaScript graph follow-up serves `get_graph_image()` bytes from
`GET /api/graph/image`. The responsive image is capped by its panel and
viewport height, while `GET /api/graph` remains the SVG fallback. Its contract
test verifies `image/png` delivery and that no planning turn runs. On
2026-10-17, `uv run pytest` passed 57 tests; frontend typecheck and production
build, isort, Black, flake8, Ruff and `uv lock --check` passed. The running
adapter returned `200 image/png` (24,241 bytes) and its SVG fallback returned
HTTP 200.

## Role-Specific Runtime Models — Verified

Acceptance:

- Keep Coordinator's `gpt-5.5` default for routing.
- Use the lighter `gpt-5.4-mini` default for Planner and Chat.
- Keep each assignment behind `RuntimeConfig` and the typed structured-output
  adapter, with no silent fallback.

Evidence: `RuntimeConfig` and `TravelPlannerService.from_environment()` wire
the three role names independently. Focused role/model tests passed 41/41 and
the full host suite passed 61/61; isort, Black, flake8, Ruff and `git diff
--check` passed. No new live provider run was claimed.

## Coordinator Routing And Trip Extension — Verified Offline

Acceptance:

- Coordinator only classifies and routes each turn; Planner remains the only
  search/proposal role and Chat writes the final response.
- Resolve `extend_trip` as an absolute target or positive relative increment
  against the canonical current plan before Planner runs.
- Reject a missing target, a non-increasing target or a total above seven days
  before Planner/search and preserve the current plan.
- Commit an extension only when existing entries remain unchanged and at least
  one grounded entry is scheduled in the added day range.
- Keep the repair route within the existing eight-step graph limit.

Evidence: ADR 0009, one new versioned chat-edit case and focused graph/runtime
regressions. The focused suite passed 44 tests and the full host and Docker
suites each passed 64. Frontend typecheck/build, isort, Black, flake8, Ruff,
`uv lock --check` and `git diff --check` passed. The rebuilt Compose runtime is
healthy at `127.0.0.1:8503`; no new live model/Tavily/LangSmith turn was run.

## Planner-To-Chat Context — Verified Offline

Acceptance:

- Give Chat the Planner summary and complete validated plan after a successful
  commit, including the new schedule entries and grounded source titles/URLs.
- On rejection, give Chat the validation issues and retained prior plan while
  excluding the rejected candidate summary and plan body.
- Reuse the existing typed `PlanCandidate` graph state without adding a node,
  edge or graph step.

Evidence: end-to-end prompt regressions cover both committed trip extension and
rejected repair paths. The focused suite passed 44 tests; the full host, Docker
build-stage and offline Docker suites each passed 64. isort, Black, flake8,
Ruff, `uv lock --check` and `git diff --check` passed. The rebuilt Compose
runtime is healthy at `127.0.0.1:8503`; the app and graph PNG return HTTP 200.
No live provider turn was run for this fix.

The JavaScript chat composer now uses a fixed lower-right panel with a 44px-plus
trigger, accessible labels, example prompts and reduced-motion-aware entrance.
User turns render as right-aligned bubbles and assistant turns as left-aligned
bubbles with role labels, status and validation details. `npm run check` and
`npm run build` passed; browser-level responsive inspection remains pending.

The interface uses a light blue and navy visual system across the page shell,
forms, itinerary cards, graph panel and chat widget. Frontend typecheck/build
passed; the browser surface was unavailable for live visual inspection.
