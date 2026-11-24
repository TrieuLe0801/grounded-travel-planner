# Learning Log — 2026-10-14 Scope Reset

This log keeps recent user decisions and operational events that help explain
current status. The [charter](../project-charter.md) and accepted ADRs are the
source of truth for product and architecture. Historical test output belongs
with its CI run or experiment artifact.

## 2026-11-24 — PostgreSQL remember-login repair

- The new app queried `auth_sessions.remember_login` before the live database
  had that column. Public `/api/auth/me` returned HTTP 503 for an invalid
  cookie, although the root health check passed. The deployment path lacked a
  schema gate before replacing the app container.
- The poller was paused and the app stopped. A 13 MB owner-only `pg_dump` was
  restored to a temporary database; counts matched 9 users, 55 sessions and
  19 saved tours. The idempotent migration was applied twice. The new boolean
  column is `NOT NULL DEFAULT false`; all 55 existing sessions are false.
- The restarted app is healthy, and public `/api/auth/me` with an invalid
  cookie now returns HTTP 200 with `authenticated: false`. The temporary
  database was removed and the poller lock released. No real authenticated
  browser flow was checked. A source-level pre-deploy schema gate now checks
  the new app's required column before container replacement; deployment of
  that gate itself remains unverified. The source and Docker test stages passed
  282 tests with one optional PostgreSQL skip; Python quality, Bash syntax,
  diff and runtime/frontend image builds passed.

## 2026-11-24 — Remember login without a fixed deadline

- The user changed the opt-in policy to no fixed server deadline and accepted
  cookie renewal on app use. Browser limits or deletion can still require a
  new sign-in; Chrome caps each persistent cookie to 400 days. Existing
  remembered sessions retain their recorded 30-day expiry, and ordinary
  sessions retain the 30-minute idle limit. ADR 0016 records the amendment.
- The additional change uses existing SQLite and PostgreSQL expiry columns;
  the pending remember-login schema migration remains required before rollout.
  Logout, administrator revocation and session-only trip/chat state remain.
- Offline verification passed 281 tests with one optional PostgreSQL skip,
  frontend check/build, four Python quality checks and 52 mocked Playwright
  checks with two duplicate mobile skips. The browser heartbeat was checked
  with a fake 24-hour clock. PostgreSQL migration, live Auth0, real elapsed
  browser persistence and deployment were not checked.

## 2026-11-24 — Remember login

- The user selected an unchecked “Remember login” option. Without it, the
  account session expires after 30 minutes idle; with it, the server and cookie
  enforce a 30-day absolute limit. The choice applies to direct Google,
  password, email-code and signup flows. ADR 0016 records the decision.
- Source implementation covers signed login state, SQLite and PostgreSQL
  session records, the bilingual landing card and an explicit schema migration.
  Existing databases need a backup and write pause before migration and rollout.
- Offline tests passed 276 with one optional PostgreSQL skip. Python quality,
  frontend check/build and 50 mocked Playwright checks passed; two duplicate
  mobile sweeps skipped. SQLite migration was tested offline. PostgreSQL
  migration, live Auth0 and deployment were not checked.

## 2026-11-21 — CI/CD review and main branch protection

- The user clarified that a successful merge into `main` must trigger Mac app
  deployment. ADR 0019 now selects `main` as the poller's source. Deployment
  still requires a successful push workflow for the exact commit; missing,
  pending or failed CI does not deploy. Migrations remain explicit.
- The CI workflow already verified pull requests targeting `main` and the
  feature branch, but push verification covered only
  `feature/travel-ground-planner`. The workflow change also targets pushes
  to `main` and uses the repository-wide flake8 command. Until it reaches
  `main`, no push CI run for that branch exists.
- The `main` ruleset now requires the GitHub Actions `verify` check. The Mac
  LaunchAgent now polls `main` with its local deploy gate enabled. The current
  `main` SHA has no push CI run, so the poller waited and did not deploy. The
  checkout, app image and healthy PostgreSQL container stayed unchanged.
  No database migration ran during the branch switch. The runtime settings
  tables already exist; a pre-migration archive parsed successfully, while a
  full restore and write-pause evidence remain unverified.
- Local verification passed: `uv sync --frozen`, 267 offline tests, isort,
  Black, flake8, Ruff, frontend install/check/build, 46 mocked Playwright
  checks, Compose configuration, Mac deployment preflight and diff check.
  One optional PostgreSQL test and two duplicate viewport sweeps skipped.

## 2026-11-20 — Travel and exploration redesign request

- The user requested research and implementation of a travel and exploration
  interface. The selected brief uses an editorial travel-guide composition,
  preserving the existing palette, typography, local guide illustrations and
  product interactions. Scope is frontend presentation; no deployment requested.
- Research, preservation criteria and baseline evidence are recorded in the
  [redesign record](../experiments/2026-11-20-travel-exploration-redesign.md).
  Baseline Playwright passed 32 checks with two duplicate viewport sweeps skipped.
  The redesign is implemented in React/CSS/i18n and the local design system.
  Frontend check/build and 34 mocked browser checks passed; two duplicate
  viewport sweeps skipped. Source/credit labels, saved-detail read-only behavior,
  chat focus/Escape and pending locale preservation are covered. Tester reached
  its usage limit after initial checks and added coverage; the primary session
  completed the final run and screenshot review. No Python, live provider,
  deployed/Auth0 checks or deployment ran for this frontend-only change.

## 2026-11-20 — Development skill and agent refresh

- The user requested a project reread, skill cleanup and selective adaptation
  from Hallmark without copying its skill. Four project skills and five roles
  remain. Transfer guidance moved into `docs/codex-workflow.md`; its duplicate
  skill and manifest were removed. No usage telemetry was available.
- UI guidance now defines audit/polish/redesign scope, a brief and interaction
  inventory, preservation checks and independent review. Existing tokens,
  components, SVG guide, accessibility and Playwright remain authoritative.
  Removed obsolete formatter exclusions for the previously deleted UI bundle.
- Four skill manifests, seven TOML files, remaining YAML manifest and progress
  JSON passed validation. Active-reference review and `git diff --check` passed.
  `uv run isort --check-only . .codex/hooks/format_python.py`,
  `uv run black --check . .codex/hooks/format_python.py`,
  `uv run flake8 . .codex/hooks/format_python.py` and
  `uv run ruff check . .codex/hooks/format_python.py` passed.
- The initial parser check was blocked by sandbox access to the uv cache;
  its authorized rerun exposed `ModuleNotFoundError: No module named 'tomllib'`
  under Python 3.10. Using installed `tomli` passed without adding dependencies.
  The Tester agent hit its usage limit; the primary session performed verification.
- Application tests, frontend builds, browser/live-provider checks and deployment
  were not run because this changes guidance and lint configuration only.
  Fresh-session agent discovery was not tested. Personal/plugin skills and
  product acceptance are unchanged.

## 2026-11-20 — Implemented UI trend proposal priorities

- Based on the review, moved landing sign-in above the introduction on mobile,
  grouped itinerary identity and explicit snapshot save, added accessible day
  links for longer plans, compacted missing-photo feedback, corrected English
  day singular/plural, and raised language/calendar targets to 44px.
- Kept all five guide steps, session and pending-turn language behavior, reset
  confirmation, saved-tour read-only behavior, source links, photo credits,
  estimates and unverified-hours labels. No new image, package or API/runtime
  behavior was added.
- Frontend check/build and diff check passed. Playwright passed 17 mocked
  Chromium checks, including phone/tablet/desktop widths, keyboard day jump,
  missing photo, touch targets and pending language switch. Screenshots were
  generated at 390/768/1024/1440px; landing and itinerary were inspected at
  390/1440px. Live Auth0, providers and deployed flows were not checked.

## 2026-11-20 — UI trend research and proposed next steps

- The user requested current UI design research, comparison with the project,
  and a modification proposal. This request covers research and planning;
  application changes and publishing are not part of this research pass.
- The [review and proposal](../experiments/2026-11-20-ui-trends-review.md)
  compares external design references with source and mocked browser evidence
  at `bdf3e35`. It prioritizes earlier landing actions, trip-header hierarchy,
  day navigation and compact missing-photo states while retaining the existing
  design system and source attribution. These remain proposals.
- A fresh Chromium run passed 10 mocked checks. Landing and itinerary
  screenshots were inspected at phone and desktop sizes. No application code,
  product acceptance count, deployment state or live-provider evidence changed.

## 2026-11-20 — Plan-first interface layout

- The user requested another interface analysis and layout improvement, with
  imagery and effects where useful. Screenshot review showed the trip form
  delaying the current itinerary, narrow desktop day cards and a large gap
  before the illustrated public guide. The current plan now leads the workspace;
  New Trip remains the confirmed reset path. Day cards use full width with
  credited photos beside place details on desktop. Landing guide cards are
  wider and appear sooner.
- Existing local SVG guide illustrations and source-attributed place photos
  meet the visual need. No additional image or motion was added.
- Frontend check/build, diff check, 18 mocked Playwright checks, 246 offline
  tests, and Python quality checks passed. Two duplicate browser sweeps and
  one optional PostgreSQL test were skipped. Live flows remain pending.

## 2026-11-20 — React interface refresh

- The user asked to run an interface update using the revised project UI skill.
  The landing, planner, chat, saved-tour, profile and administrator surfaces now
  use clearer bilingual copy and a consistent visual hierarchy. Ordinary chat
  remains available before an itinerary exists.
- Screenshot review found the floating chat button obscuring actions at phone
  and tablet widths. The phone create action now leaves room for that button;
  tablet and desktop use a sticky-header chat control instead. The admin view
  does not offer chat.
- Frontend check/build and diff check passed. Playwright passed 16 mocked
  browser checks with two intentional duplicate-sweep skips. Screenshots at
  390, 768, 1024 and 1440 px were reviewed. Live Auth0, providers, owner
  isolation and deployed flows were not run.

## 2026-11-19 — Playwright browser evaluation workflow

- The user directed test and evaluation skills and agents to use Playwright.
  Tester now follows a project-authored browser evaluation skill. Frontend
  browser tests cover the public landing in desktop and mobile Chromium with
  mocked authentication. Live Auth0, saved-tour and source-quality acceptance
  remain separate and must be observed on the actual target.
- `npm run check`, `npm run build` and `npm run test:browser` passed. Playwright
  ran four checks across desktop and mobile Chromium. The first sandboxed
  browser run could not bind localhost (`EPERM`); the permitted rerun passed.

## 2026-11-19 — Frontend and UI skill guidance

- The user asked to read [Taste Skill](https://github.com/Leonxlnx/taste-skill)
  and update related frontend/UI skills and agents. The project-authored UI
  skill now asks for task-first copy, real product states, one coherent layout,
  purposeful motion and rendered browser review at phone, tablet and desktop
  widths. Planner, Coordinator and Tester carry the matching responsibilities.
  Project photo attribution, grounded claims, reduced motion and the existing
  design system remain authoritative. No external skill bundle was installed.

## 2026-11-19 — Itinerary and chat feedback

- The React itinerary page uses plain progress text while creating an
  itinerary. Chat progress and submission errors stay in the chat panel.
- Ordinary chat responses do not show a page-level notice. Committed or
  rejected itinerary changes from chat show a short localized status, without
  repeating the assistant's chat response.
- `npm ci --offline`, `npm run check`, `npm run build` and `git diff --check`
  passed. Browser QA did not run.

## 2026-11-19 — Landing usage guide

- The user requested usage guidance before entering the app, with animation
  on the landing page. The public landing now contains a bilingual five-step
  guide and reduced-motion-aware entrance animation. Authentication and
  private planner access remain unchanged.
- The user then requested images and animation for the guide and removal of
  the guide jump button. Users reach the illustrated guide by scrolling; its
  cards animate on entering the viewport, and decorative SVG motion is disabled
  when reduced motion is preferred.
- The illustrated update passed frontend check/build, diff check, isort, Black,
  flake8 and Ruff. The offline suite passed 246 tests; one optional PostgreSQL
  test was skipped. Browser visual, mobile and reduced-motion checks did not run
  because browser access was unavailable.
- Frontend type check, build, diff check, isort, Black, flake8 and Ruff passed.
  The offline suite passed 246 tests with one optional PostgreSQL test skipped.
  Browser and live Auth0 flows did not run.

## 2026-11-17 — Authenticated view refresh

- PR #20 keeps the current React workspace view across refresh. Saved tours,
  profile and administrator views use the `view` query parameter; itinerary
  remains at `/`. The app restores private views only after checking the
  account, and non-admin accounts cannot restore the administrator view.
- The plan and conversation rehydrate from the same server session. Trip data
  is not stored in the URL, and graph inspection remains hidden.
- `npm run check`, `npm run build` and `git diff --check` passed. Browser QA,
  container recreation and deployment were not run; the active app uses another
  checkout.

## 2026-11-17 — Local Compose refresh

- Local Compose rebuilt the app from commit 34e20ba. The app and PostgreSQL
  were healthy; the local root returned HTTP 200. The Auth0 connection setting
  was present in the container, and its value was not recorded here.
- PostgreSQL was not recreated. Recreating the app cleared session-only
  itinerary, conversation and pending-turn state.
- The latest offline suite and Python/frontend checks predate this rebuild:
  246 tests passed, one optional PostgreSQL test was skipped. No tests,
  browser flow or live Auth0 request ran during the refresh.

## 2026-11-17 — Merged-account tombstone cleanup

- The user requested cleanup of a merged, non-administrator tombstone. Before
  the change, a database backup was verified and a guarded transaction was
  dry-run. The tombstone was then marked deleted and its email cleared; the
  merge mapping and audit history were retained.
- Post-check found no identities, sessions or tours on the target. The active
  administrator and their tours remained unchanged. No Auth0 request ran
  because the tombstone had no Auth0 identity.

## 2026-11-16 — Account-flow integration

- PR #16 and PR #17 were integrated with three-method identity linking,
  duplicate-account reconciliation and administrator deletion. Merged,
  deleting and deleted accounts cannot authenticate or be reactivated;
  account-owned tours and audit history are protected.
- The integrated offline suite passed 246 tests; one optional PostgreSQL test
  was skipped because its opt-in settings were unset. Python quality checks
  and frontend check/build passed. Browser account flows and live Auth0
  deletion were not exercised.

## 2026-11-15 — Account and host decisions

- The user confirmed www.citedtrip.app as the public host. ADR 0022 and the
  deployment record are authoritative for ingress and callback configuration;
  browser callback, OTP, planner and logout checks remain open.
- A user-confirmed duplicate application account was reconciled after backup
  validation and a rollback dry-run. The chosen existing account retained its
  tours; identities and access history were transferred under the guarded
  operator procedure. Runtime linking by email alone remains prohibited.
- Historical LangSmith usage is included through a persistent account alias;
  existing trace tags are not rewritten. See ADR 0023 and the implementation
  record for the account-usage behavior.

## 2026-11-21 — Development guidance review

- The user requested a project-authored requirements-question skill for the
  development agents, based on the interview pattern in mattpocock/skills.
  Focused clarification applies to blocking decisions; a deep interview needs
  an explicit request. Researcher and Planner identify questions, while the
  primary session asks and records the answers. Five project skills now exist.
- Reviewed mattpocock/skills against the existing project workflow. Adapted
  focused defect reproduction and separate goal/contract review into the
  project-authored delivery skill and development-agent instructions.
- Kept the four project skills and five roles. No external skill files, runtime
  agents, application behavior, or issue-tracker process were added.

## Durable decisions

| Decision | Canonical record |
|---|---|
| City/place sightseeing scope and product invariants | [Project charter](../project-charter.md) |
| Coordinator, Planner and Chat responsibilities | [ADR 0004](../adr/0004-city-sightseeing-two-agent-runtime.md), [ADR 0009](../adr/0009-coordinator-routed-chat-agent-and-trip-extension.md) |
| Bounded session context and shared Tavily node | [ADR 0011](../adr/0011-bounded-session-context-and-chat-search.md), [ADR 0012](../adr/0012-shared-tavily-tool-node.md) |
| Saved-tour storage and account ownership | ADRs 0014–0016 and 0021 |
| Administrator access, usage and deletion | [ADR 0023](../adr/0023-admin-access-and-account-usage.md) |
| Cloudflare public ingress | [ADR 0022](../adr/0022-cloudflare-tunnel-public-ingress.md) |

The old POC remains archived. Do not treat roadmap or planning progress as
evidence that the application, a browser flow or a live provider was verified.
## 2026-11-21 — Administrator runtime model settings

- Added active-admin configuration for provider, model, additive role
  instructions, temperature, top-p, and output-token limits across Coordinator,
  Planner, and Chat. Credentials, endpoints, and fallback models remain in the
  deployment environment.
- Settings and field-name audit records persist in the existing SQLite or
  PostgreSQL account database. An immutable per-turn snapshot keeps in-flight
  work stable. Admin prompt text is excluded from audit records; LangSmith
  inputs and outputs are hidden while tracing is enabled.
- Offline tests (267 passed, one optional PostgreSQL archive test skipped),
  frontend checks/build, 42 mocked browser checks, formatting and lint passed.
  PostgreSQL settings migration, live providers, Auth0, and deployment remain
  unverified. See ADR 0024.

## 2026-11-23 — Latency and 14-day trip proposal

- The user requested research and a proposal for lower suggestion latency and
  trips of up to 14 days. The current implementation and charter still cap trips
  at seven days; no runtime change has been made.
- In the requirements interview, the user selected at least one grounded stop
  per day in the initial 14-day itinerary, with further detail added through
  chat. Source quality and correctness take priority; a latency improvement
  must be demonstrated by measurement before it is claimed.
- Researcher and Planner proposed measuring per-stage and end-to-end latency,
  token usage, repair frequency, and source coverage before adjusting model or
  Tavily budgets. The proposal calls for coordinated 14-day bounds across
  contracts, graph, validation, both UIs, and tests. Implementation and live
  measurements remain pending.
- After the user identified the omitted interview handoff, the project-owned
  requirement and delivery skills and Researcher/Planner instructions were
  updated. Proposal work now asks unresolved product questions before Planner
  finalizes a dependent recommendation. This is a development workflow change;
  application behavior is unchanged.

## 2026-11-23 — Implemented two-week trip bound

- The user requested implementation of the previously selected 14-day option.
  New and edited trips now accept 1–14 days in runtime, React and Streamlit.
  An initial 14-day itinerary needs a grounded stop on every day; Chat can add
  detail. Extension and shortening retain the existing commit gates.
- Offline tests passed 271 with one optional PostgreSQL skip. Python quality
  checks, frontend check/build, 48 mocked Playwright checks and diff check
  passed; two duplicate browser viewport sweeps skipped. The first pytest
  collection attempt lacked configured test model names; rerun passed.
- Live 14-day model output, source quality, latency, Auth0 and deployment were
  not checked. Search/graph and model output-token budgets were not changed.
