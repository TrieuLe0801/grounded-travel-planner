# Project Status

Last updated: 2026-10-15

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
| Streamlit app | Complete | One-page session-only UI backed by the same service/graph |
| Tests | 19 passed | Core, provider-boundary, graph, service and AppTest coverage |
| Live integration | Passed | OpenAI/Tavily/LangSmith smoke recorded under `docs/experiments/` |
| Local container | Passed | Test/runtime images, health, non-root and live provider checks |

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

## Now

1. Add a versioned evaluation set for source relevance and edit quality.
2. Decide whether to add domain-quality scoring before broad demo use.

## Next

1. Add live chat-edit smoke coverage without weakening the offline test gate.
2. Migrate the smoke script from deprecated `list_runs()` before its 2027
   removal.
3. Add deployment/authentication only under a separate decision.

## Blockers And Risks

- Live provider behavior still depends on local credentials and network access.
- The requested default runtime model is exactly `gpt-5.5`; there is no silent
  fallback. Missing or unavailable configuration returns a safe response and
  preserves the previous plan.
- Tavily snippets can be incomplete; opening hours stay unverified unless a
  source result explicitly supports them.
- Live results can include broad travel pages or video sources. Current code
  validates provenance/place match, not editorial quality or domain diversity.
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
- `Dockerfile`
- `compose.yaml`
- `docs/progress/roadmap-progress.json`
