# Project Status

Last updated: 2026-11-17

## Active scope

Milestone 1: executable city/place sightseeing vertical slice. The product and
runtime contract live in the [project charter](docs/project-charter.md) and
accepted ADRs. This file records the current evidence and remaining acceptance
work; historical implementation detail belongs in the plan, learning log, CI
runs and experiment records.

## Current snapshot

| Area | State | Evidence or open gate |
|---|---|---|
| Runtime | Implemented | Coordinator, Planner and Chat roles; bounded search, session context and validate-before-commit behavior are defined in the charter and ADRs 0004, 0009, 0011 and 0012. |
| Web UI | Route restoration implemented; browser QA pending | JavaScript/Tailwind is the current UI; Streamlit remains available. Refresh restores saved-tour, profile and administrator views after account check; itinerary stays at `/`. Frontend check/build passed for PR #20; browser QA and deployment remain pending. |
| Saved tours | PostgreSQL Compose storage available; browser QA pending | Explicitly saved, owner-scoped snapshots are read-only. Verify save, list, detail, delete and owner isolation in a browser. |
| Authentication | Compose app updated; live verification pending | Public host is www.citedtrip.app. The local app container has its configured Auth0 password connection. Auth0 enablement, sign-in, signup, email verification, OTP, callback, planner access and logout have not been browser-verified. |
| Account administration | Source and offline integration verified; live QA pending | Account access, usage and deletion are implemented. No live Auth0 deletion request or administrator browser flow was checked. |
| Public app | Read-only smoke observed | On 2026-11-17, the local Compose app and PostgreSQL were healthy and the local root returned HTTP 200. This does not establish browser or Auth0 acceptance. |

## Latest verification

- The local Compose app was rebuilt from commit 34e20ba as image
  sha256:286a871aff073cd2a37586c14a557f96aadc0ac96a588c1f8277a1a3a79c3138.
  A container check confirmed the Auth0 connection setting is present without
  exposing its value. PostgreSQL remained running.
- Recreating the app cleared session-only itinerary and chat state.
- The integrated source checks recorded on 2026-11-16 passed 246 tests; one
  optional PostgreSQL integration test was skipped because its opt-in settings
  were unset. Python quality checks and frontend check/build also passed then.
- PR #20 added authenticated view restoration on 2026-11-17. `npm run check`,
  `npm run build` and `git diff --check` passed for that change. Browser refresh
  QA did not run; the active app container uses another checkout.
- No test suite ran during the 2026-11-17 Compose update. No live Auth0 request,
  browser account flow or administrator deletion API call was made.

## Remaining acceptance work

1. Verify Auth0 application settings and complete password, signup, email
   verification, OTP, callback, planner and logout flows on www.citedtrip.app.
2. In a real browser, verify saved-tour operations and owner isolation, then
   review the React UI at phone and desktop widths, including Home reset,
   account actions and navigation while a turn is pending.
3. Measure live source relevance, place coverage and host diversity; evaluate
   Chat answer accuracy across factual questions; test reorder and replace
   intents with live evidence.
4. Treat production rollout as a separate decision and follow the existing
   migration, backup and deployment gates.

## Current risks

- Tavily results may be incomplete or weakly relevant. Opening hours remain
  unverified unless supported by returned source data.
- Live provider behavior depends on credentials and network access. Offline
  checks do not establish live model, search, tracing or browser behavior.
- Live plans, chat and pending turns remain session-only; app recreation clears
  them. Saved-tour snapshots are separate durable records.
- Process-local request limits reset on restart and do not coordinate replicas.

## Canonical records

- [Project charter](docs/project-charter.md)
- [Implementation plan](docs/implementation-plan.md)
- [Current learning log](docs/learning-log/2026-10-14-scope-reset.md)
- [Progress summary](docs/progress/roadmap-progress.json)
- [Roadmap](docs/roadmap.html)
- Accepted ADRs 0004, 0009, 0011 and 0012; authentication, storage and ingress
  decisions are recorded in their respective ADRs.
