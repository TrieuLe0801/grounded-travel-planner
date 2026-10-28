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
- Session-only state, bounded background turns, Vietnamese by default and an
  English option. Secrets are kept in ignored environment files.
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
start the API:

```bash
uv run --env-file .env uvicorn grounded_travel_planner.web.api:app \
  --host 127.0.0.1 --port 8000
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
