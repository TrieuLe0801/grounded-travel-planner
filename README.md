# Grounded Travel Planner

A personal learning project and proof of concept for building a grounded travel
planning agent with LangChain, LangGraph and LangSmith.

The project is currently in **Week 0: specification and baseline**. Application
implementation intentionally has not started yet.

## Current progress

- Week 0: **23 / 34 items complete (68%)**
- Project charter: accepted for MVP
- Travel-planner application code and measured runtime metrics: `N/A` until
  implementation begins; development tooling has executable hook tests

See `PROJECT_STATUS.md` for the current Done / Now / Next / Blockers view.

## Repository map

```text
.
├── .codex/                               # Development agents, config and hook
├── .flake8, .python-version              # Python tool configuration
├── AGENTS.md                              # Durable instructions for Codex
├── PROJECT_STATUS.md                      # Current state and next actions
├── README.md
├── pyproject.toml, uv.lock                 # Locked development dependencies
├── data/eval/                             # Machine-readable eval cases (pending)
├── docs/
│   ├── adr/                               # Architecture decisions
│   ├── experiments/baseline-environment.md
│   ├── learning-log/week-00.md
│   ├── progress/roadmap-progress.json
│   ├── project-charter.md
│   └── roadmap.html                       # Interactive learning roadmap
├── src/                                   # Application code (not started)
└── tests/                                 # Development-hook tests
```

## Continue on a MacBook M1

After pushing this folder to a Git host, clone it on the Mac and open Codex from
the repository root:

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
- Docker Desktop for local containers

The development tooling is configured in `pyproject.toml`. Run:

```bash
uv sync
uv run pytest
uv run isort --check-only . .codex/hooks/format_python.py
uv run black --check . .codex/hooks/format_python.py
uv run flake8 . .codex/hooks/format_python.py
uv run ruff check . .codex/hooks/format_python.py
```

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
These are development roles and do not change the travel planner's
single-agent-first runtime architecture. Start a new trusted Codex session to
load project configuration and agent files.

The `.codex/hooks.json` `PostToolUse` hook runs isort, Black and flake8 on Python
files changed through Codex `apply_patch`. In a new Codex session, use `/hooks`
to review and trust this project hook. For Python files changed outside
`apply_patch`, run `uv run isort <files>`, `uv run black <files>` and
`uv run flake8 <files>` manually.

Codex automatically reads repository-level `AGENTS.md` when a new session is
started from this repository. A useful first prompt is:

```text
Read AGENTS.md, PROJECT_STATUS.md, docs/project-charter.md and
docs/learning-log/week-00.md. Summarize the current Week 0 status and implement
only the first incomplete next action.
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

After committing local changes, publish them with:

```bash
git push origin main
```
