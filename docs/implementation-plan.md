# Implementation Plan

Status: Active
Last updated: 2026-10-26

## Model Authentication Failure Diagnosis — 2026-10-26

The exact two-day Hà Giang request reached the configured OpenAI Coordinator
and returned HTTP 401 `token_invalidated` before Planner or Tavily ran. A
deterministic, localized authentication failure now explains why the plan was
preserved and avoids a redundant Chat call. The 94-test host and Docker suites
passed; the runtime image was rebuilt without recreating the running container.
Successful live planning remains pending a valid `OPENAI_API_KEY`.

## Phase 1A - Core Runtime — Implemented

Acceptance:

- Create an importable `grounded_travel_planner` package.
- Keep reusable modules in `src/utils/`.
- Add typed provider interfaces for model, search and tracing.
- Add LangChain `ChatOpenAI` structured-output adapter.
- Add Tavily search adapter that returns normalized URLs only.
- Add LangSmith trace sink that propagates one `thread_id`.
- Implement a LangGraph runtime with Coordinator, Planner and Chat nodes.
- Coordinator classifies, routes, reads bounded recent history and summarizes
  session context. Planner produces every candidate and emits typed requests
  for grounded search. Chat writes the final response after policy validation
  and may request one bounded Tavily search for current facts. Both roles route
  through the shared `tavily_tool` graph node, the only runtime caller of the
  typed search provider.
- Keep `gpt-5.5` for Coordinator, `gpt-5.4-mini` for Planner and `gpt-4.1` for
  Chat by default, with role-specific settings behind the model provider
  boundary.
- Select `openai` or local `ollama` explicitly through `GTP_MODEL_PROVIDER`;
  load all three model names through role-specific environment variables and
  keep each provider behind the structured-output interface. The default
  `.env.example` uses OpenAI so it works without a local model server.
- Validate input, schedule and source references before committing a candidate.
- Preserve the previous plan when validation fails.
- Keep session-only conversation history (maximum 12 messages) and a rolling
  1,200-character summary. Coordinator sees at most eight recent 600-character
  turns; Planner and Chat receive the bounded summary rather than the transcript.
- Share a maximum of two Tavily calls per turn across Planner and Chat. Chat
  citations come only from provider-returned sources and never enter plan
  validation or mutation.

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

## Bilingual Session Language — Implemented

- Provide Vietnamese (default) and English UI language choices in the React
  frontend and the Streamlit fallback, including the read-only graph page.
- Keep the language preference in the current session. Updating it does not
  clear the plan, transcript, summary, view or pending turn; session reset for a
  new trip carries the preference forward.
- Capture the selected language when a turn is submitted and pass it through
  the background runner and LangGraph roles. The active turn keeps that locale;
  later turns use the updated preference.
- Make new Coordinator summaries, Planner itinerary prose, Chat responses and
  safe fallbacks follow the selected language. Preserve user messages, place
  names, source titles/snippets/URLs and evidence text verbatim.
- Keep validation and source policies language-independent; localize
  user-facing issue messages by stable issue code.

Evidence: ADR 0013; existing focused API/runner/chat-context checks passed 14
tests; frontend typecheck and production build passed; Python compileall,
flake8, Black, isort, Ruff, lock and diff checks passed. No new locale-specific
test was added, and no browser, container or live-provider run is claimed.

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

ADR 0013 extends this behavior with an English option while keeping Vietnamese
as the default. The 2026-10-16 live evidence below proves the Vietnamese path;
current locale/session behavior is recorded in the Bilingual Session Language
section above.

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
  Planner, the shared `tavily_tool`, validators and repair. Retain an SVG
  fallback for render outages.
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

## Configurable OpenAI/Ollama Runtime Models — Host Smoke Verified

Acceptance:

- `GTP_MODEL_PROVIDER` accepts only `openai` (default) or `ollama` as the
  legacy global fallback. Optional role-provider variables override it for
  Coordinator, Planner and Chat; role model variables are validated before
  adapters are built.
- OpenAI defaults to `gpt-5.5` for Coordinator, `gpt-5.4-mini` for Planner and
  `gpt-4.1` for Chat. Ollama uses `ChatOllama` and its documented LangChain
  structured-output method without an OpenAI fallback.
- Compose exposes an opt-in Ollama profile with persistent weights and a
  one-shot model pull initializer. No model weights are baked into the app.

Evidence: mocked provider-selection and adapter tests cover configuration and
structured invocation. On 2026-10-18, native Ollama `qwen2.5:3b` completed a
structured-output call and committed a one-day Hue plan. The requested mixed
assignment also committed a one-day Hue plan: Coordinator OpenAI `gpt-5.5`,
Planner/Chat Ollama `qwen3:4b`, four entries, one Tavily search, no repair and
no validation issues. The active Planner/Chat setting was then changed to
`qwen2.5:3b`; it returned structured output from the Compose app and committed
a two-entry Hue API plan with one search and no repair. LangSmith returned 25 runs, all with the same
`thread_id`. The Compose app also reached native host Ollama through
`host.docker.internal` and committed a fresh HTTP API Hue turn after its
endpoint was separated from the direct-host loopback setting. See
`docs/experiments/2026-10-18-ollama-local-smoke.md`. The internal Docker
Ollama profile remains unrun.

## Role-Specific Runtime Models — Verified

Acceptance:

- Keep Coordinator's `gpt-5.5` default for routing.
- Use `gpt-5.4-mini` for Planner and `gpt-4.1` for Chat when using OpenAI.
- Keep each assignment behind `RuntimeConfig` and the typed structured-output
  adapter. Ollama remains explicitly selected; a missing local server does not
  silently trigger an OpenAI call.

Evidence: `RuntimeConfig` and `TravelPlannerService.from_environment()` wire
the three role names independently. After the Chat default changed to
`gpt-4.1`, 49 focused core tests and all 82 host tests passed. isort, Black,
flake8, Ruff, `uv lock --check` and `git diff --check` passed. Loading the local
`.env` resolved all roles to OpenAI with `gpt-5.5`, `gpt-5.4-mini` and
`gpt-4.1`. The Docker test image passed all 82 tests; the rebuilt runtime image
and frontend production build completed. The Compose app started healthy, read
the same three role assignments, and returned HTTP 200 for `/` and
`/api/graph/image`. No live model provider request was run.

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

## Session Context And Chat Research — Verified

Acceptance:

- Restore the active session's bounded user/assistant transcript from the API
  after page navigation or refresh; reset creates a clean session.
- Give Coordinator the previous rolling summary and a bounded recent-history
  slice. Give Planner and Chat the resulting concise summary plus task-specific
  context, not an unbounded raw transcript.
- Let Chat use a structured function-call decision to request at most one Tavily
  search when current facts are needed and the shared per-turn budget permits.
- Keep search results and citations out of plan candidates; emit redacted
  start/success/failure trace events with the session `thread_id`.
- Preserve a maximum of 8 graph steps, 2 combined Planner/Chat search calls and
  1 repair attempt. Never claim current facts verified when Tavily returned no
  usable source.

ADR 0011 records this amendment to the role/context and search ownership in
ADR 0009. The first direct-call iteration passed 88 host tests and recorded one
live Chat search with five sources and `chat.search.*` LangSmith events. ADR
0012 supersedes its provider-call mechanism with a shared graph node; current
tool-node evidence is recorded below. The original smoke is preserved in
`docs/experiments/2026-10-19-live-chat-search-smoke.md`.

## Shared LangGraph Tavily Tool Node — Verified

Acceptance:

- Planner and Chat emit typed search requests; neither agent invokes the
  provider directly.
- One `tavily_tool` graph node validates requests, owns provider invocation,
  increments the shared two-call budget before attempts, and returns normalized
  sources only to the requester.
- Trace redacted `tool.tavily.start/success/failure` events with the requester
  and same session `thread_id`.
- Keep the graph within 8 node executions and 1 repair; skip Chat search if the
  remaining graph steps cannot fit a search and response.

On 2026-10-19, 89 host tests passed, including tool ownership/routing,
provider-failure accounting, source isolation, repair and graph-step bounds.
The live smoke made one Chat search, received five Tavily sources and found
`tool.tavily.start/success` LangSmith events with the same `thread_id`. The
Docker app image rebuilt and ran healthy; `/` and `/api/graph/image` returned
HTTP 200. See ADR 0012 and
`docs/experiments/2026-10-19-live-shared-tool-node-smoke.md`. One smoke verifies
the integration path, not broad answer accuracy or source quality.

## Runtime Flow Cleanup — Verified

Acceptance:

- Remove graph-state fields and service/agent dependencies with no runtime
  readers while preserving the shared Tavily tool topology and bounds.
- Return `PlanCandidate` and `ChatResponse` directly instead of wrapping each in
  a one-field internal result object.
- Keep background-worker input copies but avoid storing additional summary and
  conversation copies in `PendingTurn` after the Future owns its captured args.
- Reuse the conversation module's 12-message and 1,200-character constants in
  the HTTP session adapter.
- Preserve validate-before-commit behavior, exact tool-owned Chat citations,
  one repair, two searches, eight graph steps and session isolation.

Evidence: 63 focused tests and all 90 host tests passed. isort, Black, flake8
and Ruff passed. This cleanup changed no accepted architecture and required no
new ADR or live-provider run.

## Bidirectional Chat Trip-Length Changes — Implemented, Offline Verified

A new `create_trip` request gives Planner no prior itinerary context, so a new
trip cannot inherit stops from an earlier plan in the same session. Chat can
extend a trip by adding a grounded stop to every added day. It can also shorten
a trip by preserving stops on retained days and removing or rescheduling stops
from removed days. Duration changes use the existing 1–7 day bound and pass
through validate-before-commit. A `change_day` request beyond the current trip
length is rejected before Planner runs.

Two regression tests now cover stops on every added day and retained-stop
integrity when shortening. The 92-test host and Docker test suites passed on
2026-10-26. The rebuilt Compose app reached healthy status at
`127.0.0.1:8503`; the root and graph PNG endpoints returned HTTP 200. Live
provider behavior remains unverified for this follow-up.
