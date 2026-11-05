# Grounded Travel Planner

Grounded Travel Planner is a city/place sightseeing webapp. A user provides a
destination, concrete start date and a 1–7 day duration; the app builds one
source-backed itinerary and supports bounded chat edits.

## Current scope

- JavaScript/Tailwind UI with a same-origin FastAPI adapter; Streamlit remains
  available during the UI migration.
- LangGraph runtime with `Coordinator`, `Planner`, `Chat` and one shared
  `tavily_tool` node. Planner owns plan changes; Chat explains results and can
  search for current facts without mutating the plan.
- Deterministic validation for input, schedule, overlaps, opening hours and
  source provenance. Failed candidates preserve the current plan.
- Session-only live plan and chat, bounded background turns, Vietnamese by
  default and an English option. Explicitly saved tours persist separately.
  Secrets are kept in ignored environment files.
- Optional source-attributed place photos and a read-only compiled graph view.

See [PROJECT_STATUS.md](PROJECT_STATUS.md) for current progress and known
risks. The active requirements are in the
[project charter](docs/project-charter.md) and
[implementation plan](docs/implementation-plan.md).

## Quick start

Requirements: Python 3.10+, [uv](https://docs.astral.sh/uv/), Node.js/npm for
the frontend, and Docker Desktop for the container workflow.

```bash
uv sync
cp .env.example .env
```

Fill the required provider credentials and model placeholders in `.env`, then
set `GTP_SAVED_TOURS_COOKIE_SECURE=false` for this direct local HTTP setup and
start the API:

```bash
uv run --env-file .env uvicorn grounded_travel_planner.web.api:app \
  --host 127.0.0.1 --port 8000 --no-access-log
```

Install and start the frontend in a second terminal:

```bash
cd frontend
npm ci
npm run dev
```

Open the Vite URL shown in the terminal. For the retained Streamlit UI:

```bash
uv run --env-file .env streamlit run \
  src/grounded_travel_planner/ui/streamlit_app.py
```

## Configuration

Copy `.env.example` to the ignored `.env` and replace every
`<YOUR_MODEL_NAME>` with a model available from the selected provider. The
three role providers may use OpenAI or Ollama independently:

```dotenv
GTP_MODEL_PROVIDER=openai
GTP_COORDINATOR_MODEL=<YOUR_MODEL_NAME>
GTP_PLANNER_MODEL=<YOUR_MODEL_NAME>
GTP_CHAT_MODEL=<YOUR_MODEL_NAME>
GTP_OPENAI_JSON_SCHEMA_MODELS=<YOUR_MODEL_NAME>
GTP_OLLAMA_FALLBACK_MODEL=<YOUR_MODEL_NAME>
```

An OpenAI API error makes one bounded Ollama fallback attempt when configured.
An explicitly Ollama-only role does not fall back to OpenAI. Direct host runs
use `OLLAMA_BASE_URL`; Compose uses `GTP_COMPOSE_OLLAMA_BASE_URL`. The optional
Compose Ollama profile is CPU-only under Docker Desktop on Apple Silicon:

```bash
docker compose --profile ollama up --wait ollama ollama-init
docker compose --profile ollama up -d app
```

Never commit `.env`, API keys, model credentials or provider responses.

## Saved tours

After a plan passes validation, choose **Lưu tour / Save tour** to store an
immutable snapshot with its source references. The saved-tour view can list,
inspect and delete snapshots without restoring or changing the live plan.
Opening a snapshot does not recheck current facts.

Compose stores saved tours in PostgreSQL 17. Its data directory defaults to
`../grounded-travel-planner-data/postgres`, outside the Git repository. Set
`GTP_DATA_DIR` in the ignored `.env` to choose another host directory. Create
its `postgres` subdirectory before starting Compose. Set a unique
`GTP_SAVED_TOURS_POSTGRES_PASSWORD` in `.env`. The database has no host port.
Back up the host directory separately; a bind mount does not protect against
host loss. Local runs outside Compose use the SQLite path
`GTP_SAVED_TOURS_DB_PATH` by default.

The archive belongs to a browser through a separate 365-day HttpOnly owner
cookie. Clearing that cookie loses access; there is no account or cross-device
recovery. Both owner and session cookies default to `Secure`, and Compose forces
that setting. For direct local HTTP only, set
`GTP_SAVED_TOURS_COOKIE_SECURE=false` outside Compose.

Account-owned saved tours with Auth0 are implemented in the worktree but have
not been rolled out to the running app. See
[`docs/proposals/2026-11-02-auth0-account-owned-saved-tours-plan.md`](docs/proposals/2026-11-02-auth0-account-owned-saved-tours-plan.md)
and [ADR 0016](docs/adr/0016-auth0-account-owned-saved-tours.md) before
migrating. The new app requires an explicit account migration, Auth0 tenant
configuration in the ignored `.env`, and browser QA. The live tour and chat
remain session-only.

To move an existing SQLite Compose archive to PostgreSQL, stop the app, back up
the SQLite volume, start `db`, then run:

```bash
docker compose --profile migrate-saved-tours run --rm migrate-saved-tours
```

The migration reads the SQLite volume without modifying it and can be rerun.
Start the app after it succeeds. Keep the old volume for rollback; avoid
`docker compose down -v` during migration. See [ADR 0015](docs/adr/0015-postgres-compose-saved-tour-storage.md)
for the storage decision.

For a PostgreSQL backup, run `pg_dump` into a directory outside the repository
and store the dump securely outside the host:

```bash
mkdir -p ../grounded-travel-planner-data/backups
docker compose exec -T db pg_dump -U travel_planner -d travel_planner \
  --format=custom > ../grounded-travel-planner-data/backups/saved_tours.dump
```

## Verification

Offline tests use mocked providers and do not call live services:

```bash
uv run pytest
uv run isort --check-only . .codex/hooks/format_python.py
uv run black --check . .codex/hooks/format_python.py
uv run flake8 . .codex/hooks/format_python.py
uv run ruff check . .codex/hooks/format_python.py
```

Frontend checks:

```bash
cd frontend
npm ci
npm run check
npm run build
```

Build and run the local container:

```bash
docker build --target test -t grounded-travel-planner:test .
docker compose up -d --wait
```

The Compose app is served at `http://127.0.0.1:8503` by default. Live
OpenAI/Tavily/LangSmith verification is separate from the offline suite and is
recorded under `docs/experiments/` when run.

## CI/CD to the Mac

GitHub Actions runs Python tests, Python quality checks, frontend checks/build
and Compose validation on pushes and pull requests to
`feature/travel-ground-planner`. A Mac `launchd` agent checks the public Actions
status every five minutes. It deploys the latest branch commit only after its
push workflow passes. Pull requests run only on GitHub-hosted runners. The Mac
deploy script rebuilds and health-checks only the app service; it leaves
PostgreSQL and its external data directory running. An app restart clears live
session plans and chat history.

The Mac keeps `.env` and deployment paths outside Git. Its local file
`~/.config/grounded-travel-planner/deploy.env` contains absolute paths and a
deployment gate:

```dotenv
GTP_DEPLOY_ENV_FILE=/absolute/path/to/grounded-travel-planner/.env
GTP_DATA_DIR=/absolute/path/to/grounded-travel-planner-data
GTP_DEPLOY_ENABLED=false
GTP_DEPLOY_BRANCH=feature/travel-ground-planner
GTP_DEPLOY_SOURCE=/absolute/path/to/development/checkout
GTP_DEPLOY_CHECKOUT=/absolute/path/to/private/deployment/checkout
```

Keep that file mode `600`; keep `.env` mode `600`. The `GTP_DATA_DIR` value must
point to the existing data root whose `postgres` directory holds the current
database. `scripts/install_macos_deploy_agent.sh` installs the five-minute
LaunchAgent. Run `scripts/poll_and_deploy_macos.sh --check` to validate local
paths, Compose configuration and database health without restarting the app.
The LaunchAgent runs in the logged-in Mac session; keep the Mac awake and
Docker Desktop available. After changing the deployment gate, run:

```bash
launchctl kickstart -k "gui/$(id -u)/com.groundedtravelplanner.deploy"
```

Rerun `scripts/install_macos_deploy_agent.sh` after changing the poller script.

Set local `GTP_DEPLOY_ENABLED=true` to enable automatic deployment after CI
passes. Keep it `false` until the explicit Auth0 account schema migration and
rollout are complete under [ADR 0016](docs/adr/0016-auth0-account-owned-saved-tours.md).
The migration is not part of automatic deployment. The poller uses the public
GitHub API and needs no GitHub token or inbound network access.

For temporary public sharing, set `NGROK_AUTHTOKEN` in the ignored `.env` and
start the optional tunnel:

```bash
docker compose --profile ngrok up -d --wait ngrok
```

The tunnel applies `deploy/ngrok-traffic-policy.json`, limiting session
creation/reset to 20 requests per client IP per hour and planning turns to 20
per client IP per hour. Uvicorn access logs are disabled so Auth0 callback
query parameters are not written to app logs.

## Repository map

```text
frontend/                         React/Tailwind application
src/grounded_travel_planner/      runtime, graph, policies and web/UI adapters
src/utils/                        reusable helpers
tests/                            offline tests
docs/project-charter.md           active product requirements
docs/implementation-plan.md       delivery plan and evidence
docs/adr/                         accepted architecture decisions
PROJECT_STATUS.md                 current status, risks and next steps
```

## Further reading

- [Project charter](docs/project-charter.md)
- [Implementation plan](docs/implementation-plan.md)
- [Current status](PROJECT_STATUS.md)
- [Scope-reset learning log](docs/learning-log/2026-10-14-scope-reset.md)
- [Architecture decisions](docs/adr/)
- [Baseline environment](docs/experiments/baseline-environment.md)
