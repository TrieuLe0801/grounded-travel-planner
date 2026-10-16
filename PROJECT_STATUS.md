# Project Status

Last updated: 2026-10-16

## Current Milestone

Milestone 1: executable city/place sightseeing vertical slice.

The active product scope is defined by `docs/project-charter.md` and
`docs/implementation-plan.md`. Older three-week POC artifacts remain historical
background only.

## Progress Snapshot

| Area | Status | Evidence |
|---|---|---|
| Scope reset | Complete | Charter, implementation plan, current log and ADR 0004 |
| Runtime package | Complete | Coordinator/Planner graph, typed providers and validators |
| Streamlit app | Complete | Session-only itinerary/chat plus read-only graph page |
| Tests | 50 passed | Core, async UI, graph-image, photo, chat-edit/source eval and AppTest coverage |
| Live integration | Passed | OpenAI/Tavily/LangSmith smoke recorded under `docs/experiments/` |
| Local container | Passed | Test/runtime images, health, non-root and live provider checks |
| Chat editing | Passed | Successful UI edit, eight offline eval cases and live two-turn smoke |
| Source quality evaluation | Offline baseline | 16 labelled synthetic citations; live relevance not measured |
| Vietnamese chat | Passed | Vietnamese AppTest/fallback and live add-place response |
| Visual itinerary | Complete | Source-backed photos; route map removed by user request |
| Graph inspection | Complete | `get_graph_image()` PNG on separate page; SVG fallback; offline AppTest |
| Async page navigation | Implemented | Background Future, exact-once session integration; browser QA pending |

Planning progress is not implementation progress. Only executable artifacts and
actual checks count as completion evidence.

## Done

- Replaced the archived POC scope with the city/place sightseeing product scope.
- Accepted ADR 0004 for the two-runtime-agent LangGraph architecture.
- Preserved ADR 0001 as the development-agent/tooling decision; Codex helper
  roles remain separate from the webapp runtime Coordinator and Planner.
- Implemented the exact two runtime roles with `gpt-5.5`, typed provider
  boundaries and code-enforced graph/search/repair limits.
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
- Added eight versioned offline chat-edit eval cases and AppTest coverage for a
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

## Now

1. Manually verify chat → graph page → chat navigation in a real browser while
   a live provider turn is pending; AppTest cannot drive multipage navigation.
2. Label sources from representative live plans and measure relevance, place
   coverage and host diversity before a broad demo.
3. Exercise additional live edit intents, especially reorder and replace, with
   separate evidence from the offline gate.

## Next

1. Add deployment/authentication only under a separate decision.

## Blockers And Risks

- Live provider behavior still depends on local credentials and network access.
- The requested default runtime model is exactly `gpt-5.5`; there is no silent
  fallback. Missing or unavailable configuration returns a safe response and
  preserves the previous plan.
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
- `docs/adr/0005-visual-itinerary-enrichment.md`
- `docs/adr/0006-photo-only-itinerary-and-graph-inspection.md`
- `docs/adr/0007-session-owned-background-turns.md`
- `Dockerfile`
- `compose.yaml`
- `docs/progress/roadmap-progress.json`
