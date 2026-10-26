# Grounded Travel Planner

A city/place sightseeing webapp built with LangChain, LangGraph, LangSmith,
Tavily, React and Tailwind. The active scope was reset on 2026-10-14; older
three-week POC documents are historical background.

## Current progress

- Scope-reset charter, implementation plan and ADR 0004/0009/0011/0012/0013 exist.
- Core runtime has three roles: `Coordinator`, `Planner` and `Chat`.
- `GTP_MODEL_PROVIDER` selects the global `openai` (default) or local `ollama`
  provider. `GTP_COORDINATOR_PROVIDER`, `GTP_PLANNER_PROVIDER` and
  `GTP_CHAT_PROVIDER` can override it for individual roles. The three
  `GTP_*_MODEL` settings choose model names; OpenAI defaults are `gpt-5.5`,
  `gpt-5.4-mini` and `gpt-4.1` for Coordinator, Planner and Chat.
- Tavily, OpenAI, Ollama and LangSmith integrations sit behind typed provider
  adapters. Planner and Chat route typed requests through the shared LangGraph
  `tavily_tool`; it is the sole runtime caller of the search provider.
- The current JavaScript/Tailwind interface uses a same-origin FastAPI adapter.
  The server keeps the canonical plan, up to 12 conversation messages and a
  rolling summary in an opaque in-memory browser session. The Streamlit
  implementation remains available during migration.
- Deterministic tests use fakes and never call live services.
- Coordinator receives a bounded recent-history slice and summarizes context;
  Planner and Chat receive the summary instead of the raw transcript.
- Chat can use a structured function-call decision to make one Tavily search
  for current facts when needed. It returns citations from actual search results
  and cannot change the plan; its search shares the two-call turn budget with
  Planner. Search attempts appear as `tool.tavily.*` LangSmith events.
- Chat edits are covered by nine versioned offline cases, a successful/rejected
  Streamlit AppTest sequence and a separate live create-then-remove smoke.
- Planning turns run in a bounded background pool, remain owned by the browser
  session and continue while the user opens the read-only graph view.
- The React app and Streamlit fallback support Vietnamese (default) and English.
  The locale stays in the session, and a pending turn keeps the language chosen
  when it was submitted.

See `PROJECT_STATUS.md` for the current Done / Now / Next / Blockers view.

## Active product

The user supplies a destination/place, concrete start date and one-to-seven-day
duration. Coordinator classifies, delegates and summarizes bounded session
history. Planner is the only runtime role that proposes a plan mutation and
searches to ground it; Chat writes the response and may search when current
facts are needed.
Deterministic code validates
input, schedule overlap/range, returned-source provenance and supported opening
hours before committing a candidate.

Chat supports create, add/remove/replace/reorder, trip extension and shortening,
and day/time change intents. Every added trip day gets a grounded stop;
shortening updates the schedule to fit the new duration.
Ordinary chat does not search unnecessarily or mutate the plan. Planner and
Chat share a two-call Tavily limit per turn. A rejected edit preserves the
previous canonical plan.

See `docs/project-charter.md`, `docs/implementation-plan.md` and ADR
0004/0009/0011/0012.

## Repository map

```text
.
├── .codex/                               # Development agents, config and hook
├── .flake8, .python-version              # Python tool configuration
├── AGENTS.md                              # Durable instructions for Codex
├── PROJECT_STATUS.md                      # Current state and next actions
├── README.md
├── pyproject.toml, uv.lock                 # Locked runtime/dev dependencies
├── frontend/                               # React/Tailwind app and npm lockfile
├── docs/
│   ├── adr/                               # Architecture decisions
│   ├── experiments/baseline-environment.md
│   ├── learning-log/2026-10-14-scope-reset.md
│   ├── implementation-plan.md             # Active phased delivery plan
│   ├── progress/roadmap-progress.json
│   ├── project-charter.md
│   └── roadmap.html                       # Current milestone summary
├── src/grounded_travel_planner/           # Agents, graph, policies, HTTP/UI
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
- React/Tailwind for the current UI; Streamlit retained during migration
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

Install the frontend dependencies and run its typecheck/build:

```bash
cd frontend
npm ci
npm run check
npm run build
cd ..
```

Copy `.env.example` to an ignored `.env`, fill the local credentials, then run
the same-origin web server:

```bash
uv run --env-file .env uvicorn grounded_travel_planner.web.api:app --host 127.0.0.1 --port 8000
```

Open `http://127.0.0.1:8000`. For frontend development, run `npm run dev` from
`frontend/`; Vite proxies `/api` to port 8000. The retained Streamlit UI can
still be started separately:

```bash
uv run --env-file .env streamlit run src/grounded_travel_planner/ui/streamlit_app.py
```

Automated tests do not load credentials or call live services. Live OpenAI,
Tavily and LangSmith gates are recorded separately when executed. The bounded
Chat search smoke is `scripts/live_chat_search_smoke.py`.

## Model provider configuration

Copy `.env.example` to `.env`. The provider and every role model are explicit:

```dotenv
GTP_MODEL_PROVIDER=openai
GTP_COORDINATOR_MODEL=gpt-5.5
GTP_PLANNER_MODEL=gpt-5.4-mini
GTP_CHAT_MODEL=gpt-4.1
```

To run local models with an Ollama process installed on the host, pull a model,
then point the app at the host endpoint. On macOS and Windows, Docker Desktop
containers can reach it at `http://host.docker.internal:11434`; a directly run
app normally uses `http://127.0.0.1:11434`.

```bash
ollama pull qwen2.5:3b
```

```dotenv
GTP_MODEL_PROVIDER=openai
GTP_COORDINATOR_PROVIDER=openai
GTP_PLANNER_PROVIDER=ollama
GTP_CHAT_PROVIDER=ollama
GTP_COORDINATOR_MODEL=gpt-5.5
GTP_PLANNER_MODEL=qwen2.5:3b
GTP_CHAT_MODEL=qwen2.5:3b
OLLAMA_BASE_URL=http://127.0.0.1:11434
```

To run Coordinator locally as well, set `GTP_COORDINATOR_PROVIDER=ollama` and
`GTP_COORDINATOR_MODEL` to a model served by that Ollama instance. The same
per-role provider/model pattern applies to Planner and Chat.

The application uses OpenAI for all three roles when no local provider is
selected. Choosing `ollama` requires a reachable Ollama server; it does not
silently send that role to OpenAI.

The Compose Ollama profile is opt-in and keeps weights in the named
`ollama-models` volume. It does not start with ordinary `docker compose up`.
Initialize its default lightweight model (or the whitespace-separated names in
`OLLAMA_PULL_MODELS`) before starting the app:

```bash
docker compose --profile ollama up --wait ollama ollama-init
docker compose --profile ollama up -d app
```

For a normal Compose app, `GTP_COMPOSE_OLLAMA_BASE_URL` defaults to
`http://host.docker.internal:11434`, so it reaches Ollama running on the host.
This is separate from the direct-host `OLLAMA_BASE_URL` setting. When using the
opt-in Compose Ollama profile, explicitly set
`GTP_COMPOSE_OLLAMA_BASE_URL=http://ollama:11434` before starting `app`:

```bash
GTP_COMPOSE_OLLAMA_BASE_URL=http://ollama:11434 \
  docker compose --profile ollama up -d app
```

On 2026-10-18, a native mixed-provider smoke committed a one-day Hue plan with
OpenAI `gpt-5.5` as Coordinator and local `qwen3:4b` as Planner and Chat. The
current recommended local configuration uses `qwen2.5:3b`; the Compose profile
itself still needs a live run.

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

The webapp defaults to Vietnamese and now offers an English language switch for
the React and Streamlit interfaces. New assistant and itinerary prose follows
the session locale, while source titles and proper place names retain their
original spelling. The representative live Vietnamese add-place smoke remains
historical evidence at `docs/experiments/2026-10-16-vietnamese-chat-smoke.md`;
ADR 0013 records the bilingual session behavior.

## Visual itinerary

After a plan is committed, the app looks up actual place images from Wikimedia
Commons. Cards show image creator, license and file-page link. Missing imagery
leaves the text itinerary intact. The first 12 stops are enriched to bound
public-API calls. The route map and car interaction were removed at the user's
request; ADR 0006 records the change.

Use **Xem graph** in the JavaScript UI to inspect the compiled workflow as the
PNG returned by `TravelPlannerService.get_graph_image()`. The image scales to
the graph panel without horizontal overflow; an SVG fallback is shown if PNG
rendering is unavailable. The retained Streamlit graph page has the same
PNG-first behavior.

## Background chat turns

Creating or editing a plan submits one background turn for the current session.
The JavaScript interface opens chat from the floating button in the lower-right
corner; the panel shows a waiting state and disables competing mutations. The
user can visit the graph view while the turn continues. The canonical plan changes
only after a committed response. This mechanism is session-only and does not
survive a server process restart.

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

The default URL is `http://127.0.0.1:8503` (container port 8000). To avoid a local port conflict in
PowerShell:

```powershell
$env:GTP_PORT = "8513"
docker compose up -d --wait
```

To share the running app through ngrok, set `NGROK_AUTHTOKEN` in the ignored
`.env` file, then start the optional tunnel:

```powershell
docker compose --profile ngrok up -d ngrok
docker compose logs ngrok
```

Use the HTTPS forwarding URL shown in the ngrok logs. The tunnel connects to
`app:8000` inside Compose; the app remains bound to `127.0.0.1:8503` on this
host. The URL is public, so stop the tunnel when sharing is finished. Changing
`.env` and starting the profile can recreate the app and clear its in-memory
sessions. To stop sharing without stopping the app:

```powershell
docker compose --profile ngrok stop ngrok
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
Coordinator, Planner and Chat. Start a new trusted Codex session to load project
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
