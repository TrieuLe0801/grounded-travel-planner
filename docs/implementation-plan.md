# Implementation Plan

Status: Active
Last updated: 2026-11-08

## Complete Day Coverage For New Trips — Compose Deployed; Provider QA Pending — 2026-11-06

Every newly created itinerary must include at least one grounded stop on each
selected day. The Planner prompt states this requirement, and candidate
validation rejects missing days before commit. One repair attempt can fill gaps;
if it still omits a day, the current plan remains unchanged.

The running Compose app uses the default Planner output ceiling of 8,192 tokens,
with no runtime override. No usage trace established that a request reached the
ceiling. A response truncated before schema completion would fail parsing or
validation. The confirmed code gap was that a sparse but valid structured
response passed the prior commit gate.

The focused regression passed 2 tests; `uv run pytest` passed 170 tests with
one optional PostgreSQL test skipped. isort, Black, flake8, Ruff and
`git diff --check` passed. The app was rebuilt as image
`sha256:133f4f2471e7c81c74ce0fffdb9f39c9e14fb8ebd06c60ad73d520027b55da22`
and recreated. It is healthy, `/` returns HTTP 200, and runtime source inspection
confirms the coverage guard and Planner prompt are present. PostgreSQL remains
healthy and ngrok remained running. App recreation cleared session-only plans.
No live-provider turn or browser interaction was run.

## Home And Account UI Redeploy — Local Compose And Ngrok Verified — 2026-11-06

Final `git fetch origin` and `git pull --ff-only` confirm branch and upstream
at `051c5fc`. The image was rebuilt without cache from that source content,
including the Home and Account UI changes. Image ID:
`sha256:0746fd6f5a1d3c9e442464ab16ae1ed43cc295ac66eadd14816f82dacbcfd7a0`.

Compose recreated only `app` and `ngrok`; PostgreSQL remained running. The app
is healthy, local and ngrok public roots return HTTP 200, and both served the
bundle with Home and Account labels. Ngrok mounts its Traffic Policy read-only.
The live database still has six saved tours, the account-owner column, both
owner indexes and all three auth tables. Auth0/session configuration is present
in the app container. No database migration ran during this deployment.

Frontend check/build passed. Browser interaction and live Auth0 callback/OTP
were not tested.

## Account Actions Dropdown — Implemented — 2026-11-06

The React header groups Saved tours and sign-in/sign-out under one user-icon
dropdown. For an authenticated user, the display name comes from the email
local-part; email remains display data, not an archive owner key. The saved-tour
view retains its legacy-cookie claim action.

The initial frontend check and build passed. Follow-up Compose and ngrok
deployment evidence is recorded above; browser dropdown interaction and live
Auth0 checks remain pending.

## Home Starts a New Trip — Implemented — 2026-11-06

The header Home control now uses the existing session-reset endpoint and returns
the user to the itinerary start. It asks for confirmation before discarding a
current plan, clears the trip form and chat draft, and keeps the selected
language, account and saved-tour archive. The existing New Trip control uses
the same reset behavior.

Frontend check/build and the full `uv run pytest` suite (155 passed, 1 skipped)
passed during implementation. The targeted API reset regression passed in that
suite. Follow-up deployment evidence is recorded above. Browser click behavior
remains unverified.

## Mac CI/CD — Configured; Deployment Gated — 2026-11-05

GitHub Actions now defines Python tests and quality checks, frontend checks and
build, and Compose configuration validation. A Mac `launchd` poller checks for
a successful push workflow every five minutes. The Mac keeps `.env` and the
existing PostgreSQL data directory outside Git. Its deployment script validates
the database, rebuilds only `app`, waits for health, checks HTTP, and attempts
to restore the previous app image after a failed health check.

The workflow and LaunchAgent are configured. Automatic deployment remains
disabled until the controlled Auth0 database migration and rollout in ADR 0016
are complete. CI/CD configuration verification passed; no application image
was deployed or restarted for this change.

## Auth Callback And Session Ingress Hardening — Deployed; Smoke Checked — 2026-11-06

The runtime Uvicorn command disables access logs so the Auth0 callback's
short-lived `code` and `state` query parameters are not recorded in app access
logs. The local README run command uses the same setting. The optional Compose
ngrok profile loads a Traffic Policy that rate-limits anonymous session
creation/reset to 20 requests per client IP per sliding hour and planning
turns to 20 per client IP per sliding hour. Reset is included because a missing
or invalid session cookie can allocate a new session there too. Turn limits
also reduce repeated public requests that could consume model and search quota.

Three deployment-security regression tests, `docker compose --profile ngrok
config --quiet`, and `git diff --check` passed. The host suite and Docker test
target each passed 155 tests with one optional PostgreSQL test skipped; isort,
Black, flake8 and Ruff passed. On 2026-11-06 the runtime image was rebuilt and
Compose recreated app, PostgreSQL and ngrok with the `ngrok` profile. All
services are running; app and database are healthy. The runtime command includes
`--no-access-log`; ngrok loads the policy from a read-only mount. Local and
public root returned HTTP 200, and the tunnel URL matches
`GTP_AUTH_PUBLIC_ORIGIN`. App recreation cleared session-only plans. Live 429
enforcement and Auth0 callback exchange were not tested. Other public ingress
paths still need equivalent rate controls.

## Runtime Token And Turn Quotas — Compose Image Deployed; Enforcement QA Pending — 2026-11-06

ADR 0020 adds per-role output-token ceilings, a 28-entry itinerary limit, a
sliding-hour HTTP turn quota keyed by verified account or anonymous session,
and redacted model-usage events when LangSmith tracing is enabled. The
per-principal default matches the current 20/hour ingress policy. An optional
process-wide hourly turn ceiling is read from runtime environment; blank leaves
that extra ceiling disabled. Actual environment values are not stored here.

Mocked/offline verification passed: 168 host tests passed and one optional
PostgreSQL test skipped; isort, Black, flake8, Ruff and `git diff --check`
passed. Verification disabled dotenv loading and used dummy model names. The
runtime image was then rebuilt and the Compose app container recreated. The
container is healthy, the app root returns HTTP 200, and the process-wide quota
setting parses as configured. Recreating the app cleared session-only plans;
the PostgreSQL container and saved tours remained intact. No request was sent
to exercise HTTP 429, and no LangSmith usage event was inspected. Actual
environment values are not recorded. The hourly turn ceiling is not a USD
meter. Configure a provider-project hard spend limit separately and place the
production app behind a managed DDoS/WAF edge with direct origin access closed.

## Auth0 Account Ownership — Offline Verified; Rollout Pending — 2026-11-03

ADR 0016 selects Auth0 Universal Login email OTP for account-owned saved
tours. FastAPI now has a typed OIDC boundary, persistent SQLite/PostgreSQL
account sessions, CSRF, and account-scoped archive routes. The React header
groups Saved tours and sign-in/sign-out in one user-icon dropdown. Its
authenticated display name uses the email local-part; the saved-tour view
retains the legacy-cookie claim action. The explicit migration adds account
ownership and auth tables without rewriting tour snapshots.

The host suite, Python gates, frontend build and Compose config passed.
The PostgreSQL migration ran twice against an isolated restore: all five
snapshot IDs, timestamps and exact text retained their checksum. A separate
repository process read and revoked a persisted test auth session. See
`docs/experiments/2026-11-03-auth0-account-offline.md`.

The running app and live database remain unchanged. Before rollout: configure
the Auth0 development application and ignored `.env`, verify callback/logout
URL and email OTP, decide the old-cookie claim window and account
deletion/export policy, pause writes, migrate the backed-up live database,
then perform A/B cross-browser and failure-path QA. Do not infer live Auth0
behavior from mocked tests.

Follow-up verification on 2026-11-04 added existing-session revocation on
sign-in and serialized concurrent first-account creation. Host and container
pytest now pass 146 tests with one optional PostgreSQL test skipped. An
isolated PostgreSQL check mapped 16 concurrent logins to one account and
verified session persistence, CSRF and revocation.

## PostgreSQL Host Data Directory — Deployed — 2026-11-01

The user moved persistent PostgreSQL data outside the Git repository. Compose
bind-mounts `${GTP_DATA_DIR:-../grounded-travel-planner-data}/postgres`; the
default sibling directory is not part of the repository or Docker build
context. The former `postgres-data` named volume remains intact for recovery.
ADR 0015 records the amendment.

The app was stopped before migration. A PostgreSQL custom-format dump was
created in the sibling directory with owner-only permissions and accepted by
`pg_restore --list`. The new database started from the empty host directory;
the dump restored without errors. Before and after, `saved_tours` contained
three rows with the same ordered row checksum
`b2106fd26f97d08098fd137e10f97f74`; its three indexes remained present.
Both app and database are healthy, root returned HTTP 200 and session creation
returned 201. Recreating the app cleared session-only conversations and plans.
No browser or live-provider turn was run.

## PostgreSQL Compose Storage — Deployed — 2026-11-01

The user directed the database to run in its own Docker Compose container.
ADR 0015 changes the saved-tour storage engine to PostgreSQL 17. The app waits
for a healthy `db` service, uses a bounded connection pool and keeps the same
owner-scoped, immutable save/list/detail/delete API. The PostgreSQL database
has a named volume and no published host port. The local non-Compose SQLite
backend remains available for deterministic offline tests.

Before cutover, the app was stopped and the one-row SQLite archive was backed
up to ignored `.local/backups/saved_tours_pre_postgres_2026-11-01.sqlite`.
`scripts/migrate_saved_tours_to_postgres.py` read the old volume without
writing it, copied the row and checked all fields including snapshot text.
Rerunning the migration verified the same row without duplication. The app
then started on PostgreSQL: both containers reached healthy status, root
returned HTTP 200 and session creation returned 201. Recreating the database
and app containers retained the row. A PostgreSQL custom-format dump was
written to ignored `.local/backups/saved_tours_postgres_initial_2026-11-01.dump`
and `pg_restore --list` accepted it.

The full host and Docker test-target suites passed 131 cases with one
PostgreSQL integration test skipped by default. The PostgreSQL test passed
inside the Compose network. Isolated Compose smoke tested migration, exact
snapshot retention, idempotent save, owner isolation, list/detail and delete.
isort, Black, flake8, Ruff, lock, Compose config and diff checks passed. No
live model/search or browser check was run. A separate disposable PostgreSQL
Compose project populated 2,000,000 rows with tiny synthetic snapshots under
one owner. Ten samples yielded first-page p50/p95 0.729/13.898 ms, page 20,000
0.373/21.557 ms, save 0.155/1.194 ms and delete 0.136/0.523 ms. The database
occupied 1,415,034,547 bytes, including a 341,360,640-byte list index. These
figures do not predict real snapshot size or concurrent production latency.
The benchmark project and volume were removed.

## Current Compose Deployment — 2026-11-01

At the user's request, rebuilt `grounded-travel-planner:local` and recreated
the app container. The first start failed because the existing saved-tour
volume had one row under schema v1. Before migration, a SQLite backup was
written to the ignored `.local/backups/saved_tours_pre_v2_2026-11-01.sqlite`;
its integrity check passed and it retained the one row. The explicit migration
completed. The current app container is healthy on `127.0.0.1:8503`; root
returned HTTP 200 and session creation returned 201. The mounted database is
schema v2, has the composite index, retains one row and passes integrity check.
The test image also rebuilt; its 131-test build layer was cached from the
prior passing run. Recreating the app cleared live session-only state. Browser
and live-provider checks were not run.

## Hide Graph Inspection Page — 2026-11-01

The graph inspection page is no longer presented in React navigation or
Streamlit's auto-discovered pages. Compiled-graph rendering and the read-only
HTTP image/SVG endpoints remain available for diagnostics. ADR 0006 records
the user's updated UI decision.

Verification: graph view tests passed 4/4; the full host suite passed 131/131.
Frontend TypeScript check and production build passed, as did isort, Black,
flake8, Ruff, JSON validation and `git diff --check`. Browser and running
container behavior were not checked in this change.

## Large Saved-Tour Archive — Offline And Compose Verified — 2026-11-01

Acceptance:

- Support more than two million explicitly saved tour records on the current
  single-host SQLite deployment without scanning earlier pages for list reads.
  Keep list responses owner-scoped, bounded to 50 metadata rows and ordered by
  save time plus ID. Use an opaque continuation cursor and reject invalid or
  obsolete offset parameters.
- Match the owner filter and stable order with a composite index. Preserve the
  unique save key, immutable plan snapshots, source references and owner-scoped
  detail/delete behavior. Avoid a table scan during normal startup.
- Migrate existing populated databases explicitly and atomically, preserving
  all saved rows. Include the migration command in the runtime image and
  document backup/write-pause requirements.
- Test migration, query plan, pagination with tied timestamps and insertions,
  malformed cursors and owner isolation. Measure a disposable two-million-row
  archive and run host/container suites and an isolated Compose smoke.

Evidence: `saved_tours.py` now uses `(saved_at, id)` keyset reads with
`saved_tours_by_owner_saved_at_id`; `web/api.py` returns `next_cursor` and
rejects offset requests. `scripts/migrate_saved_tours_index.py` upgrades a
populated v1 archive explicitly. Nine focused and 131 full host tests passed;
the Docker test target also passed all 131. isort, Black, flake8, Ruff,
frontend typecheck/build, Compose config and diff checks passed. A disposable
2,000,000-row benchmark took 15.22 seconds to populate and occupied
1,313,050,624 bytes after checkpoint. Ten measured reads at page 1 yielded
p50/p95 0.715/3.985 ms; page 20,000 yielded 0.667/1.465 ms. Ten saves yielded
1.281/3.061 ms and deletes 2.051/2.851 ms. The fixture uses a tiny synthetic
snapshot and all rows under one owner, so its bytes and timings are not
production estimates. An isolated Compose project built the runtime image,
became healthy, served root 200 and an empty cursor-list response, rejected
offset with 422, created schema v2 and ran the migration CLI; that project and
volume were removed. Browser QA and a full live-provider turn were not run.

## Explicit Saved Tours — Offline And Compose Verified — 2026-10-31

Acceptance:

- Store a snapshot of a canonical validated plan in SQLite only when the user
  explicitly chooses Save tour. Duplicate saves of one owner/plan/revision
  return the existing record. A rejected candidate, ordinary chat or missing
  plan must never create a saved tour.
- Keep the live plan/transcript/summary/pending turn in the existing session.
  Use a separate durable browser owner credential for saved tours. List,
  inspect and delete only that owner's records, even after a new app session
  or process restart with the same database and owner cookie.
- Show saved records read-only with original citations, estimates, opening-hour
  verification flags, save time and a stale-facts notice. Keep VI/EN UI labels.
- Keep runtime graph and provider boundaries unchanged. No archive endpoint
  calls a model, Tavily or LangSmith.
- Verify offline with isolated SQLite test databases, full Python gates and
  frontend typecheck/build. Verify the named volume across a Compose container
  recreation before claiming storage persists across restarts.

ADR 0014 changes the former database non-goal only for explicitly saved tour
snapshots. Search-history persistence remains a research proposal rather than
part of this implementation.

Evidence: `src/grounded_travel_planner/saved_tours.py` and the FastAPI saved-tour
endpoints implement SQLite snapshots, owner-scoped list/detail/delete and
bounded pagination. React implements explicit save and read-only review.
`tests/test_saved_tours.py` passed 6 cases; all 128 host tests, isort, Black,
flake8, Ruff, `npm run check`, `npm run build`, Compose configuration and
`git diff --check` passed. The Compose runtime image built. The Docker test
stage initially failed collection because it lacked required model-name
environment variables; synthetic test-only names fixed that and all 128
container tests passed. An isolated Compose app was healthy, returned HTTP 200
at `/` and 201 for session creation, and listed a synthetic saved tour after
its container was force-recreated with the same named volume. Its detail still
contained the fixture source. The isolated project and volume were removed;
the original app was left running on its older image. No browser QA or live
provider turn was run for this feature.

## Deterministic Trip Shortening — Offline Verified — 2026-10-27

Fixed a failure where reducing trip duration returned the safe Planner failure
message. Prompt compaction had removed each existing stop's nested source data,
which the exact-retention validation requires for shortening. The Planner now
builds this candidate deterministically from the validated current plan: it
changes the day count and revision, preserves all entries on retained days
unchanged, and removes entries after the new final day. It performs no model
call or Tavily search for this deterministic edit. The prompt used for other
model-backed edits also retains source references beside their entries and
does not duplicate those URLs in the separate source list.

The graph regression confirms a relative one-day reduction commits, retains
schedule and source fields exactly, and uses zero searches or repairs. The full
host suite passed 117; isort, Black, flake8, Ruff and `git diff --check` passed.
The running Compose container has not been recreated; its in-memory sessions
would be cleared by replacement.

## Agent Prompt Latency And Token Optimization — Offline Verified — 2026-10-27

Applied the OpenAI latency guide's prompt/output guidance to the existing
Coordinator/Planner/Chat flow without changing model assignments, graph routing,
search limits or validation. Planner now receives a chronological projection
of the prior plan once, with trusted source references supplied separately;
the duplicate request object and raw user message inside intent are omitted.
Chat receives the visible schedule and Planner summary rather than the full
plan JSON a second time. All three roles are asked for concise summaries or
responses.

Two focused prompt regressions passed, and Ruff, Black and `git diff --check`
passed. A full live before/after token and latency comparison was not run, so no
numeric performance gain is claimed. Full pytest collection currently fails
before running because unrelated pending `config.py`/`service.py` edits remove
model constants still imported by tests and recurse in the OpenAI factory.
OpenAI guidance: https://developers.openai.com/api/docs/guides/latency-optimization

## Planner OpenAI Model Change — Model-Only Smoke Verified — 2026-10-27

Planner now defaults to `gpt-6.1-terra` with `reasoning_effort="none"` and
JSON-schema structured output through Chat Completions. This avoids the
function-call route, which requires the Responses API for this model. The
published context window is 1,050,000 tokens versus 400,000 for the prior
`gpt-5.4-mini`. Coordinator, Chat, provider overrides and one-attempt Ollama
fallback keep their existing behavior. A small live call verified account
access; actual Planner latency requires a separate check. The larger context
window does not increase the app's intentionally bounded session history or
search limits.
Focused tests passed 70 and the full suite passed 111. Isort, Black, Ruff and
diff check passed; repo-wide flake8 retains three pre-existing F841 findings.
A direct live `ChatResponse` call with Terra returned structured output in
3.91 seconds. The installed LangChain package bound the full Planner schema
offline. The rebuilt local app is healthy, resolves OpenAI `gpt-6.1-terra`
and Ollama `qwen2.5:3b` fallback, and serves root/graph at HTTP 200.
Recreating the container cleared session-only state. No full Planner turn or
latency comparison has been verified after this change. Automatic approval
review rejected a direct API check with the full internal Planner schema
because it would disclose that schema externally; it was not retried.

## Model Authentication Failure Diagnosis — 2026-10-26

The exact two-day Hà Giang request reached the configured OpenAI Coordinator
and returned HTTP 401 `token_invalidated` before Planner or Tavily ran. A
deterministic, localized authentication failure now explains why the plan was
preserved and avoids a redundant Chat call. The 94-test host and Docker suites
passed; the runtime image was rebuilt without recreating the running container.
This diagnosis preceded the OpenAI-to-Ollama fallback below.

## Automatic Ollama Fallback — Host And Live Smoke Verified — 2026-10-26

An OpenAI-configured Coordinator, Planner or Chat role now attempts the same
structured call once with local Ollama after an OpenAI authentication,
rate-limit, server, connection or timeout failure. The fallback model defaults
to `qwen2.5:3b` through `GTP_OLLAMA_FALLBACK_MODEL`, with optional per-role
model overrides. OpenAI calls have no SDK retry and a 20-second timeout so a
failure is bounded. Explicit Ollama roles remain Ollama-only; schema and
application errors do not trigger failover. Prompt, schema and trace metadata
carry through to Ollama, and deterministic plan validation still controls
commit. ADR 0010 records the amended provider policy.

The 110-test host suite, isort, Black, flake8, Ruff and diff check passed. A
live call with an intentionally invalid OpenAI key returned a structured
`ChatResponse` from host Ollama `qwen2.5:3b`. A complete live Hue turn with the
same invalid key committed a sourced plan with three citations, one Tavily
search and no repair in six graph steps. LangSmith was disabled for that turn.
The host Ollama process was started for verification and the Compose runtime
image built successfully. A one-shot container from that image also committed
a Hue plan through host Ollama with one entry, one Tavily search, zero repairs
and no validation issues under the same intentionally invalid OpenAI key. The
running app was subsequently recreated from that image at the user's request,
clearing its prior session-only state. The app reached healthy status; `/` and
`/api/graph/image` returned HTTP 200, and `POST /api/session` returned 201.
The web UI failover path was not tested in this change.

## Ollama Container And Apple M1 Routing — Verified — 2026-10-26

The opt-in Compose `ollama` and `ollama-init` services started successfully;
the initializer pulled `qwen2.5:3b` into the named volume. With the app
temporarily pointed at `http://ollama:11434`, a live turn using an intentionally
invalid OpenAI key committed a one-entry Hue plan with one Tavily search, no
repair and no validation issues. `ollama ps` inside the container reported
`100% CPU`.

The user then chose the Apple M1 chip for inference. Docker Desktop for macOS
does not expose the Apple GPU to the Ollama Linux container, so the app now
uses native Ollama through `http://host.docker.internal:11434`. The macOS
Ollama app is serving that endpoint. A fallback call from the running app
container returned a structured `ChatResponse` after a deliberately invalid
OpenAI key, and host `ollama ps` reported `100% GPU`. The CPU Ollama container
remains healthy but is not the app's active endpoint. No source, graph or plan
policy changed; this was a local deployment configuration change.

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
- Keep `gpt-5.5` for Coordinator, `gpt-6.1-terra` for Planner and `gpt-4.1` for
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
- Format app-rendered itinerary and saved-tour dates in the selected UI locale;
  localize React date-picker controls and format Streamlit date inputs by that
  locale; keep session and API date values in ISO form.

Evidence: ADR 0013; initial API/runner/chat-context checks passed 14 tests;
frontend typecheck and production build passed. On 2026-11-06, Coordinator,
Planner and both Chat prompt paths gained an explicit locale policy for new
prose in multilingual context. On 2026-11-07, UI errors, validation messages
and action statuses changed to translation keys rendered in the current locale;
language option names now follow that locale too. Two prompt regression cases
and the full Python suite passed (172 passed, 1 optional PostgreSQL test
skipped); isort, Black, flake8, Ruff, diff checks and React production build
passed. Existing conversation and source data remain verbatim. Browser and
live-provider locale QA were not run. On 2026-11-08, React replaced its
browser-native date input with an in-app calendar whose month, weekday and
control labels follow the selected locale. Streamlit date input order and
app-rendered dates follow selected locale. `npm run check`, Python isort, Black,
flake8 and Ruff checks passed; Docker runtime image built, and recreated app
returned HTTP 200. GitHub Actions run `42395988122` passed pytest, Python
format/lint, frontend check/build and Compose validation. Browser QA was not run.

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
- OpenAI defaults to `gpt-5.5` for Coordinator, `gpt-6.1-terra` for Planner and
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
Ollama profile was subsequently verified in the Apple M1 routing section
above.

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
