# Grounded Travel Planner — Codex Instructions

## Project boundary

- This repository is an independent LangChain, LangGraph and LangSmith learning
  project.
- The active delivery target is the three-week POC in
  `docs/poc-3-week-plan.md`. Broader charter goals are post-POC unless the plan
  marks them P0 or P1.
- Use only decisions and artifacts recorded in this repository as project
  context unless the user explicitly supplies another source.
- The active product is a three-week, fixture-first proof of concept, not a
  booking system or a broader travel platform.

## Read before making changes

Before editing code or project decisions, read these files in order:

1. `PROJECT_STATUS.md`
2. `docs/poc-3-week-plan.md`
3. `docs/project-charter.md`
4. the current file under `docs/learning-log/`
5. relevant records under `docs/adr/`, when they exist
6. `docs/experiments/baseline-environment.md` for environment-dependent work

Treat repository Markdown as the durable source of truth. Browser
`localStorage`, chat history and assumptions are not project evidence unless
they have been written to the repository.

## Architecture principles

- Use LangGraph for explicit state, routing, interrupts, bounded loops and
  persistence.
- Use LangChain for model, tool and structured-output integrations.
- Use LangSmith for traces, datasets and evaluations after an executable flow
  exists.
- Start with a deterministic single-agent workflow. Add specialist agents only
  after a controlled comparison demonstrates value.
- For the three-week POC, use one parent graph, one offline fixture journey and
  structured input. Do not add multi-agent, live providers, long-term memory,
  Chainlit, FastAPI, persistent storage, Docker or CI unless all P0 work is
  complete and the plan explicitly allows the task.
- The P0 UI is one Streamlit page. Keep it as a thin adapter over typed
  graph/domain interfaces; never duplicate business rules in UI code.
- External providers must be behind typed, provider-independent interfaces.

## Product invariants

- Never fabricate sources, prices, availability or tool results.
- Label fixture-based flight and lodging estimates as `synthetic_estimate` and
  include their fixture ID; do not attach a fake URL.
- A supplied total-trip budget is a hard limit and includes flight, lodging,
  food, local transport and activities.
- Unsupported route or duration must return `PLAN_UNAVAILABLE`; do not invent
  fixture data.
- Missing, stale or conflicting evidence must not become a guessed fact.
- Preserve the workflow outcomes defined in `docs/project-charter.md`.

## Working agreements

- The primary Codex session manages development requests: assign bounded
  planning, implementation and verification work to the project-scoped
  `planner`, `coding` and `testing` agents when those roles are needed; wait for
  their results and integrate them. Keep shared-file edits coordinated.
- These Codex development agents are separate from the travel planner's runtime
  single-agent-first architecture. See `docs/adr/0001-python-development-tooling.md`.

- Support Python `>=3.10`.
- Use `uv` for dependency management, virtual environments and command
  execution. Commit `uv.lock` after dependencies are introduced.
- Use `pytest` for automated tests.
- Use isort and Black for Python formatting, flake8 for PEP 8 checks, and Ruff
  for supplementary lint checks. See `docs/adr/0001-python-development-tooling.md`.
- Use Docker Desktop for local containers and prefer arm64-compatible images for
  the MacBook M1.
- Prefer small, typed, testable Python modules and deterministic fixtures.
- Keep network and model calls out of unit tests.
- Use Streamlit `AppTest` for the minimum UI checks after graph/eval P0 is
  stable. Keep the CLI as a fallback and debugging entry point.
- Bound all agent and repair loops explicitly.
- Store secrets only in ignored environment files; never commit credentials or
  raw sensitive preferences.
- Do not claim tests, metrics or providers exist until the corresponding
  executable artifact exists.
- Do not invent the installed Python, `uv`, Docker or Compose versions; record
  them from the target MacBook.
- Update `PROJECT_STATUS.md`, the current learning log and
  `docs/progress/roadmap-progress.json` when a checklist item is completed.
- Use `docs/poc-3-week-plan.md` as the delivery gate and apply its stop rules
  before starting P1 or P2 work.
- Add or update an ADR when changing a confirmed architectural decision.
- Run the narrowest relevant checks after a change, then the full available
  suite. If no executable checks exist, report that status as `N/A`.
- Once the Python project exists, use `uv run pytest`, `uv run isort --check-only
  . .codex/hooks/format_python.py`, `uv run black --check .
  .codex/hooks/format_python.py`, `uv run flake8 .
  .codex/hooks/format_python.py` and `uv run ruff check .
  .codex/hooks/format_python.py` as the standard verification commands.

## Completion evidence

A task is complete only when its durable artifact exists and its verification
result is recorded. A checked box in `docs/roadmap.html` alone is not evidence.
