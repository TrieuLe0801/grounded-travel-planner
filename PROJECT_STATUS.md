# Project Status

Last updated: 2026-11-26

## Active scope

Milestone 1: executable city/place sightseeing vertical slice. The product and
runtime contract live in the [project charter](docs/project-charter.md) and
accepted ADRs. This file records the current evidence and remaining acceptance
work; historical implementation detail belongs in the plan, learning log, CI
runs and experiment records.

## Current snapshot

| Area | State | Evidence or open gate |
|---|---|---|
| Runtime | Implemented; 14-day bound verified offline | Coordinator, Planner and Chat retain bounded search, session context and validate-before-commit behavior. New and edited trips accept 1–14 days; initial plans require a grounded stop each day. Offline and mocked browser checks passed. Live 14-day model output, providers and latency remain unverified. Active admins can set role settings; backup restore and write-pause evidence remain pending. See ADR 0024. |
| Web UI | Travel-guide redesign and 14-day selection implemented; mocked browser QA passed; live QA pending | React and Streamlit accept up to 14 days. React submits 14 days and renders 14 day links in mocked desktop/mobile checks. Live Auth0, providers and deployed behavior remain unverified. |
| Saved tours | PostgreSQL Compose storage available; browser QA pending | Explicitly saved, owner-scoped snapshots are read-only. Verify save, list, detail, delete and owner isolation in a browser. |
| Authentication | Remember-login PostgreSQL schema repaired; Auth0 browser QA pending | Sign-in offers an unchecked remember option: ordinary sessions expire after 30 minutes idle; new opted-in sessions have no fixed server deadline and renew their browser cookie on a successful account check. Older opted-in sessions keep their 30-day limit. The backed-up, write-paused PostgreSQL migration added `auth_sessions.remember_login`; 55 older sessions defaulted to false. The restarted app is healthy and public `/api/auth/me` with an invalid cookie returns HTTP 200 with `authenticated: false`. Real sign-in, callback, planner access, remembered return and logout remain unverified. |
| Account administration | Source and offline integration verified; live QA pending | Account access, usage and deletion are implemented. No live Auth0 deletion request or administrator browser flow was checked. |
| Public app | Read-only authentication smoke observed | On 2026-11-24, the restarted Compose app was healthy and public `/api/auth/me` with an invalid cookie returned HTTP 200 with `authenticated: false`. This does not establish browser or Auth0 acceptance. |

## Local Ollama fallback activated — 2026-11-26

The user selected `qwen3:8b` after the benchmark. The deployment `.env` global
Ollama fallback was changed from `qwen3.5:4b-mlx`, and an app-only same-image
Compose recreation activated it. Running container inspection confirms the new
fallback and unchanged OpenAI primary roles; app health and public HTTP smoke
passed. Unsaved session state was cleared. The model still failed the synthetic
Planner schedule checks; this choice is not a Planner quality acceptance. The
LangSmith source edits remain undeployed.

## Trace visibility and local model comparison — 2026-11-26

The user authorized visible LangSmith inputs and outputs for every traced run,
including prompts and answers. Source now preserves complete ordinary content,
redacts recognized credentials, and retains thread and usage metadata. Custom
trace events now complete correctly when the SDK returns no object from
`create_run`. ADR 0024 records the policy amendment.

Independent offline verification passed 301 tests with one optional PostgreSQL
skip; all four Python quality checks passed. Synthetic LangSmith readback
passed all 13 checks for root/LLM content, credential redaction, thread/model/usage
metadata, and custom event completion. A paired synthetic M1 16 GiB
comparison favors `qwen3:8b` for a Chat-only evaluation: median chat latency
8.45 seconds versus 5.58 seconds for 4B and 9.41 seconds for 9B, with clearer
sampled bilingual prose. None passed every schedule check. The subsequent fallback activation is
recorded above. See the [experiment](docs/experiments/2026-11-26-local-model-comparison.md) for artifacts,
limitations, and live verification evidence.

## Local model output handling — 2026-11-26

Ollama thinking is explicitly disabled through ChatOllama reasoning=False; output budgets are unchanged. A direct synthetic live probe with think=False returned valid JSON, no thinking, done_reason=stop and 5 generated tokens at a 128-token cap. This is not deployed-app acceptance.

Ollama remains the final fallback. Empty, thinking-only, truncated and invalid structured output now fail with safe classified errors; no retry or further provider is added, and the previous plan is preserved. Offline verification passed 294 tests with one optional PostgreSQL skip; all four Python quality checks passed. Live workload and deployment were not tested.

## Development workflow

On 2026-11-21, the CI workflow was extended to verify pushes to `main`
and to run flake8 across the repository. Pull request checks and push checks
for `feature/travel-ground-planner` remain. The user selected `main` for Mac
deployment. Its local poller now tracks `main` with the deployment gate enabled,
but the current `main` commit has no push CI run, so the poller waited without
deploying. The checkout, app image and healthy PostgreSQL container stayed
unchanged. The `main` ruleset requires the GitHub Actions `verify` check; the
workflow edit has not reached `main`. See ADR 0019.

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

- Remember-login PostgreSQL repair (2026-11-24): The deployment poller was
  paused, the app stopped, and a 13 MB owner-only `pg_dump` was restored into a
  temporary database. Counts matched: 9 users, 55 auth sessions and 19 saved
  tours. The idempotent schema migration was applied twice; the new boolean
  column is `NOT NULL DEFAULT false`, and all 55 older sessions are false.
  After restart, the app was healthy and public `/api/auth/me` changed from
  HTTP 503 to HTTP 200 for an invalid cookie. The temporary database was
  removed and the poller lock released. No authenticated browser flow ran.
- Pre-deploy schema gate source (2026-11-24): New app image checks required
  PostgreSQL columns before container replacement; a failed check restores the
  prior image tag. Local and Docker test stages passed 282 tests with one
  optional PostgreSQL test skipped. Python quality, Bash syntax, diff and
  runtime/frontend image builds passed. The new gate has not been deployed.

- Remember login without a fixed deadline (2026-11-24): 281 offline tests passed; one optional PostgreSQL test skipped because its opt-in DSN was unset. isort, Black, flake8, Ruff, frontend check/build, and 52 mocked Playwright checks passed; two duplicate mobile sweeps skipped. The 24-hour visible-tab heartbeat and the new 400-day cookie renewal path were tested offline. PostgreSQL, live Auth0, real elapsed browser persistence, and deployment were not checked.

- Remember login (2026-11-24): 276 offline tests passed; one optional PostgreSQL test skipped because its opt-in DSN was unset. isort, Black, flake8, Ruff, frontend check/build, and 50 mocked Playwright checks passed; two duplicate mobile sweeps skipped. SQLite migration was tested offline. PostgreSQL migration, live Auth0, browser persistence across a real sign-in, and deployment were not checked.

- CI/CD review: `uv sync --frozen`, 267 offline tests, isort, Black, flake8,
  Ruff, frontend install/check/build, 46 mocked Playwright checks, Compose
  configuration, Mac deployment preflight and diff check passed. One optional
  PostgreSQL test and two duplicate viewport sweeps skipped. No live deploy or
  GitHub run of the edited workflow occurred.
- Mac deployment branch switch: local config now has `GTP_DEPLOY_BRANCH=main`
  and `GTP_DEPLOY_ENABLED=true`. The installed poller reported the current
  `main` SHA's push CI run as pending. Deployment checkout remained at
  `a7409fd`, app image at `a16e52d` and PostgreSQL container at `da18268`;
  both services stayed healthy. Mac preflight passed. No app deploy occurred.

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
4. Verify administrator runtime-settings edits in the deployed app; confirm
   settings records in the restored backup before accepting those edits.
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
- PostgreSQL runtime settings tables exist, but a complete backup restore and
  write-pause evidence have not been verified. Admin edit behavior in the
  deployed app remains untested.

## Canonical records

- [Project charter](docs/project-charter.md)
- [Implementation plan](docs/implementation-plan.md)
- [Current learning log](docs/learning-log/2026-10-14-scope-reset.md)
- [Progress summary](docs/progress/roadmap-progress.json)
- [Roadmap](docs/roadmap.html)
- [ADR 0024](docs/adr/0024-administrator-runtime-model-settings.md)
- Accepted ADRs 0004, 0009, 0011 and 0012; authentication, storage and ingress
  decisions are recorded in their respective ADRs.
