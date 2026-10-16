# Grounded Travel Planner

A city/place sightseeing webapp built with LangChain, LangGraph, LangSmith,
Tavily and Streamlit. The active scope was reset on 2026-10-14; older
three-week POC documents are historical background.

## Current progress

- Scope-reset charter, implementation plan and ADR 0004 exist.
- Core runtime has exactly two agent roles: `Coordinator` and `Planner`.
- Both agents use the exact default model identifier `gpt-5.5` through an
  injectable LangChain structured-output boundary.
- Tavily, OpenAI and LangSmith integrations sit behind typed provider adapters.
- The Streamlit itinerary/chat page stores the canonical plan in session state
  only; a separate read-only page shows the compiled LangGraph architecture.
- Deterministic tests use fakes and never call live services.
- Chat edits are covered by eight versioned offline cases, a successful/rejected
  Streamlit AppTest sequence and a separate live create-then-remove smoke.

See `PROJECT_STATUS.md` for the current Done / Now / Next / Blockers view.

## Active product

The user supplies a destination/place, concrete start date and one-to-seven-day
duration. Coordinator classifies and delegates; Planner is the only runtime
role that searches or proposes a plan mutation. Deterministic code validates
input, schedule overlap/range, returned-source provenance and supported opening
hours before committing a candidate.

Chat supports create, add/remove/replace/reorder and day/time change intents.
Ordinary chat does not search or mutate the plan. A rejected edit preserves the
previous canonical plan.

See `docs/project-charter.md`, `docs/implementation-plan.md` and ADR 0004.

## Repository map

```text
.
├── .codex/                               # Development agents, config and hook
├── .flake8, .python-version              # Python tool configuration
├── AGENTS.md                              # Durable instructions for Codex
├── PROJECT_STATUS.md                      # Current state and next actions
├── README.md
├── pyproject.toml, uv.lock                 # Locked runtime/dev dependencies
├── docs/
│   ├── adr/                               # Architecture decisions
│   ├── experiments/baseline-environment.md
│   ├── learning-log/2026-10-14-scope-reset.md
│   ├── implementation-plan.md             # Active phased delivery plan
│   ├── progress/roadmap-progress.json
│   ├── project-charter.md
│   └── roadmap.html                       # Current milestone summary
├── src/grounded_travel_planner/           # Agents, graph, policies, UI
├── src/utils/                              # Reusable domain-free helpers
└── tests/                                 # Offline core and Streamlit tests
```

## Continue on a MacBook M1

Clone the repository on the Mac and open Codex from the repository root:

```bash
git clone <repository-url>
cd grounded-travel-planner
```

The local machine baseline is recorded in
`docs/experiments/baseline-environment.md`. To refresh it, run:

```bash
sw_vers
uname -m
python3 --version
git --version
docker --version
docker compose version
```

Copy the results into `docs/experiments/baseline-environment.md`. Values that
are unavailable should remain explicit `TODO` items.

The selected development baseline is:

- Python `>=3.10`
- `uv` for dependencies and virtual environments
- `pytest` for tests
- isort and Black for formatting; flake8 and Ruff for linting
- Streamlit for the session-only itinerary/chat UI and graph-inspection page
- Docker Desktop for the verified local container workflow

The development tooling is configured in `pyproject.toml`. Run:

```bash
uv sync
uv run pytest
uv run isort --check-only . .codex/hooks/format_python.py
uv run black --check . .codex/hooks/format_python.py
uv run flake8 . .codex/hooks/format_python.py
uv run ruff check . .codex/hooks/format_python.py
```

Copy `.env.example` to an ignored `.env`, fill the local credentials, then run:

```bash
uv run --env-file .env streamlit run src/grounded_travel_planner/ui/streamlit_app.py
```

Automated tests do not load credentials or call live services. Live OpenAI,
Tavily and LangSmith gates are recorded separately when executed.

## Verification recorded on 2026-10-14

- `uv run pytest`: 19 passed.
- isort, Black, flake8, Ruff, `uv lock --check` and `git diff --check`: passed.
- Streamlit local-only startup: HTTP 200 health response.
- Live `gpt-5.5` + Tavily flow: committed one Hue plan with five returned
  citations, one search and one bounded repair.
- LangSmith: 14 matching root/child runs; all carried the same `thread_id`.

See `docs/experiments/2026-10-14-live-two-agent-smoke.md` for sanitized live
evidence and the integration defects found during the smoke.

## Chat editing and source-quality checks

The current offline suite passed 47 tests on 2026-10-16. To run the separate
live two-turn edit smoke with local credentials:

```bash
uv run --env-file .env python scripts/live_chat_edit_smoke.py
```

The source-quality baseline uses labelled synthetic cases, not live Tavily
results. It reports relevance, place coverage and host diversity without
changing the runtime commit rule:

```bash
uv run python scripts/evaluate_source_quality.py
```

See `docs/experiments/2026-10-15-live-chat-edit-smoke.md` and
`docs/experiments/2026-10-15-source-quality-baseline.md` for evidence and
limits. The original live smoke now uses LangSmith `runs.query()`; its v2 query
verification is recorded in
`docs/experiments/2026-10-15-langsmith-query-v2-smoke.md`.

The add-place regression for `Lô Lô Chải` is verified offline and a
representative live container edit passed on 2026-10-16. The initial live
recheck had hit OpenAI HTTP 429 `billing_not_active`; the original user's
session was not replayed. See
`docs/experiments/2026-10-16-live-lo-lo-chai-add.md`.

The webapp uses Vietnamese for chat and form guidance by default. A Vietnamese
add-place request and assistant reply passed in the running container; source
titles and proper place names keep their original spelling. See
`docs/experiments/2026-10-16-vietnamese-chat-smoke.md`.

## Visual itinerary

After a plan is committed, the app looks up actual place images from Wikimedia
Commons. Cards show image creator, license and file-page link. Missing imagery
leaves the text itinerary intact. The first 12 stops are enriched to bound
public-API calls. The route map and car interaction were removed at the user's
request; ADR 0006 records the change.

Use the separate **Kiến trúc LangGraph** page in Streamlit's navigation to
inspect the PNG produced by `TravelPlannerService.get_graph_image()` from the
compiled workflow. It shows the runtime nodes, conditional branches and repair
loop without running a planning turn; an SVG fallback handles render outages.

UI guidance is installed at `.codex/skills/ui-ux-pro-max/` (upstream MIT,
version `2.15.0`) and adapted in `docs/ui-visual-itinerary.md`. The earlier
map experiment and live public-media checks remain recorded in
`docs/experiments/2026-10-16-visual-itinerary-smoke.md` as historical evidence.

## Run with Docker locally

The runtime image is non-root and receives `.env` only when Compose starts the
container; credentials are never build arguments or image layers.

```bash
docker build --target test -t grounded-travel-planner:test .
docker compose build
docker compose up -d --wait
```

The default URL is `http://127.0.0.1:8501`. To avoid a local port conflict in
PowerShell:

```powershell
$env:GTP_PORT = "8513"
docker compose up -d --wait
```

Stop only this project while retaining the local images:

```bash
docker compose down
```

Verified locally on 2026-10-14: container pytest 19/19, health HTTP 200,
UID/GID 10001, no `/app/.env`, no secret-pattern matches in history/logs and a
live Hue plan committed with six Tavily-returned citations. See
`docs/experiments/2026-10-14-local-container-smoke.md`.

The trusted project `.codex/config.toml` sets the primary Codex session to
`gpt-6-sol`. It receives development requests and coordinates these agents:

| Agent | Model | Work |
|---|---|---|
| `manager` | `gpt-6-sol` | Delegate tasks and integrate results when invoked explicitly |
| `planner` | `gpt-5.6-terra` | Plan code changes from repository evidence |
| `coding` | `gpt-5.5` | Implement assigned changes |
| `testing` | `gpt-5.5` | Write and run deterministic tests |

The primary session acts as manager through `AGENTS.md`; the separate `manager`
definition supports explicit delegation to a manager subagent. The manager
assigns bounded tasks, waits for results, and coordinates edits to shared files.
These are development roles and are separate from the webapp runtime
Coordinator and Planner. Start a new trusted Codex session to load project
configuration and agent files.

The `.codex/hooks.json` `PostToolUse` hook runs isort, Black and flake8 on Python
files changed through Codex `apply_patch`. In a new Codex session, use `/hooks`
to review and trust this project hook. For Python files changed outside
`apply_patch`, run `uv run isort <files>`, `uv run black <files>` and
`uv run flake8 <files>` manually.

Codex automatically reads repository-level `AGENTS.md` when a new session is
started from this repository. A useful first prompt is:

```text
Read AGENTS.md, PROJECT_STATUS.md, docs/project-charter.md,
docs/implementation-plan.md and docs/learning-log/2026-10-14-scope-reset.md.
Continue the first incomplete active-scope milestone without using archived POC
completion counts.
```

## Roadmap state

`docs/roadmap.html` is a convenient interactive view. Its browser state is not
the source of truth. Exported progress belongs in
`docs/progress/roadmap-progress.json`, and completed work must be supported by a
repository artifact.

## Git repository

- Remote: `https://github.com/TrieuLe0801/grounded-travel-planner.git`
- Default branch: `main`
- Visibility: private

Publish the current feature branch with:

```bash
git push origin feature/travel-ground-planner
```
