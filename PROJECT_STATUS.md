# Project Status

Last updated: 2026-11-21

## Active scope

Milestone 1: executable city/place sightseeing vertical slice. The product and
runtime contract live in the [project charter](docs/project-charter.md) and
accepted ADRs. This file records the current evidence and remaining acceptance
work; historical implementation detail belongs in the plan, learning log, CI
runs and experiment records.

## Current snapshot

| Area | State | Evidence or open gate |
|---|---|---|
| Runtime | Implemented; admin model settings source-verified | Coordinator, Planner and Chat retain bounded search, session context and validate-before-commit behavior. Active admins can set role provider/model, additive prompt and bounded generation parameters. Offline and mocked browser checks passed; explicit settings migration and live provider check remain pending. See ADR 0024. |
| Web UI | Travel-guide redesign implemented; mocked browser QA passed; live QA pending | Travel-guide redesign implemented with an editorial landing, local decorative landscape/compass SVG, departure form, destination-led journal, numbered days, saved-tour index and consistent chat styling. Frontend check/build and 34 mocked Chromium checks passed; two duplicate viewport sweeps skipped. Live Auth0, providers and deployed behavior remain unverified. |
| Saved tours | PostgreSQL Compose storage available; browser QA pending | Explicitly saved, owner-scoped snapshots are read-only. Verify save, list, detail, delete and owner isolation in a browser. |
| Authentication | Compose app updated; live verification pending | Public host is www.citedtrip.app. The local app container has its configured Auth0 password connection. Auth0 enablement, sign-in, signup, email verification, OTP, callback, planner access and logout have not been browser-verified. |
| Account administration | Source and offline integration verified; live QA pending | Account access, usage and deletion are implemented. No live Auth0 deletion request or administrator browser flow was checked. |
| Public app | Read-only smoke observed | On 2026-11-17, the local Compose app and PostgreSQL were healthy and the local root returned HTTP 200. This does not establish browser or Auth0 acceptance. |

## Development workflow

On 2026-11-21, a project-authored `requirement-clarification` skill was added
for blocking user decisions and explicit deep interviews. Researcher and
Planner identify questions; the primary session asks and records answers.
Five project skills and five development roles now exist. Runtime behavior and
product acceptance are unchanged. Five skill manifests, five agent TOML files,
config TOML, progress JSON and diff checks passed. Application/browser/live
checks were not run for this guidance-only change.

On 2026-11-21, project-authored delivery and agent guidance gained focused
defect reproduction and separate Goal Card/project-contract review after a
review of mattpocock/skills. Four skills and five roles remain; no external
bundle was installed. Agent TOML parsing and diff checks passed. This is a
workflow change only; application and live acceptance are unchanged.

On 2026-11-20, project skills were consolidated to four and the five development
roles gained explicit UI/UX handoffs. The redundant transfer skill was replaced
by its procedure in `docs/codex-workflow.md`. Selective Hallmark ideas extend
existing UI/browser guidance; no external bundle was imported. Four skill
manifests, TOML/JSON/YAML parsing, active references, diff checks and all four
Python formatting/lint checks passed. Product and live acceptance are unchanged.

## Latest verification

- Administrator runtime model settings: 267 offline tests passed; one optional
  PostgreSQL archive test skipped because its opt-in DSN was unset. Frontend
  check/build and 42 mocked Chromium tests passed; two duplicate viewport
  sweeps skipped. Screenshots at 390 and 1440 px were reviewed. isort, Black,
  flake8, Ruff and diff checks passed. Settings migration was not run; no live
  Auth0, model provider, Postgres migration, or deployment was checked.

- Travel/exploration redesign: frontend type check/build, diff check and 34
  mocked Chromium tests passed; two duplicate mobile viewport sweeps skipped.
  Screenshots cover 390, 768, 1024 and 1440 px, VI/EN, landing, itinerary, saved
  detail and chat. See the [research and evidence record](docs/experiments/2026-11-20-travel-exploration-redesign.md).
  Python checks were not run for this frontend-only change. No deployment or
  live Auth0/provider flow was performed.

- On 2026-11-20, UI trend proposal P0 and day-navigation P1 changes passed
  `npm run check`, `npm run build`, `git diff --check`, and 17 mocked Chromium
  browser checks. Screenshots were generated at 390, 768, 1024 and 1440 px;
  landing and itinerary were inspected at phone and desktop sizes. Checks cover
  first-viewport sign-in, one/seven-day navigation, keyboard activation,
  compact missing-photo fallback, 44px language/calendar targets and switching
  language while a turn is pending. APIs were mocked; live Auth0, providers,
  saved-tour ownership and deployed behavior were not exercised.

- On 2026-11-20, the layout refinement passed `npm run check`, `npm run build`,
  `git diff --check`, and 18 Playwright checks; two duplicate mobile viewport
  sweeps were skipped. Screenshots were reviewed at 390, 768, 1024 and 1440 px.
  The offline suite passed 246 tests with one optional PostgreSQL skip after
  supplying test-only model names. isort, Black, flake8 and Ruff passed.
  Browser APIs were mocked; live Auth0, provider and deployed-app flows were
  not run.
- On 2026-11-20, the React UI refresh passed `npm run check`, `npm run build`,
  `git diff --check` and 16 Playwright checks; two duplicate viewport sweeps
  were intentionally skipped in the mobile project. Screenshots were reviewed
  at 390, 768, 1024 and 1440 px. Browser APIs were mocked; live Auth0,
  provider and deployed-app flows were not run.
- On 2026-11-19, the new Playwright browser suite passed four mocked public
  landing checks across desktop and mobile Chromium. Frontend check and build
  passed. These checks do not establish live Auth0, saved-tour or provider
  acceptance.
- On 2026-11-19, the illustrated landing guide passed `npm run check`,
  `npm run build`, `git diff --check`, isort, Black, flake8 and Ruff. The offline
  suite passed 246 tests; one optional PostgreSQL test was skipped. Browser
  visual, mobile and reduced-motion checks did not run because browser access
  was unavailable.
- On 2026-11-19, the landing usage guide passed `npm run check`,
  `npm run build`, `git diff --check`, isort, Black, flake8 and Ruff. The offline
  suite passed 246 tests; one optional PostgreSQL test was skipped. Browser and
  live Auth0 checks did not run.
- On 2026-11-19, React feedback copy and display rules passed `npm run check`,
  `npm run build` and `git diff --check`. `npm ci --offline` installed the
  locked frontend dependencies. Browser QA did not run.
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
2. In the deployed app, verify saved-tour operations and owner isolation, then
   complete authenticated browser QA for Home reset, account actions and
   navigation while a turn is pending. Mocked responsive UI checks have passed.
3. Measure live source relevance, place coverage and host diversity; evaluate
   Chat answer accuracy across factual questions; test reorder and replace
   intents with live evidence.
4. Back up the account database, pause application writes, and apply the
   runtime-model-settings migration before enabling admin edits in deployment.
5. Treat production rollout as a separate decision and follow the existing
   migration, backup and deployment gates.

## Current risks

- Tavily results may be incomplete or weakly relevant. Opening hours remain
  unverified unless supported by returned source data.
- Live provider behavior depends on credentials and network access. Offline
  checks do not establish live model, search, tracing or browser behavior.
- Live plans, chat and pending turns remain session-only; app recreation clears
  them. Saved-tour snapshots are separate durable records.
- Process-local request limits reset on restart and do not coordinate replicas.
- Admin model settings remain unavailable until the explicit backed-up
  SQLite/PostgreSQL migration runs during a write pause.

## Canonical records

- [Project charter](docs/project-charter.md)
- [Implementation plan](docs/implementation-plan.md)
- [Current learning log](docs/learning-log/2026-10-14-scope-reset.md)
- [Progress summary](docs/progress/roadmap-progress.json)
- [Roadmap](docs/roadmap.html)
- [ADR 0024](docs/adr/0024-administrator-runtime-model-settings.md)
- Accepted ADRs 0004, 0009, 0011 and 0012; authentication, storage and ingress
  decisions are recorded in their respective ADRs.
