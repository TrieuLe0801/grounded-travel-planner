# Grounded Travel Planner

A personal learning project and proof of concept for building a grounded travel
planning agent with LangChain, LangGraph and LangSmith.

The project is currently in **Week 1 of a three-week POC** running from
2026-09-22 to 2026-10-12. Application implementation has not started yet; the
next milestone is an executable deterministic LangGraph vertical slice.

## Current progress

- Active three-week roadmap: **10 / 53 items complete (19%)**
- Scope/rebaseline session: **6 / 6 complete**
- Project scaffold/tooling session: **4 / 6 complete**
- Executable POC: **0%** — development-hook tests pass, but no application
  package, graph, fixture or measured metric exists yet
- Focused POC charter: accepted for the three-week deadline

See `PROJECT_STATUS.md` for the current Done / Now / Next / Blockers view.

## Three-week POC

The delivery target is a single offline, fixture-first LangGraph workflow with
a one-page Streamlit UI for a TP.HCM → Đà Nẵng three-day demo. It accepts
structured input, routes missing requirements to clarification, builds one
grounded plan, validates budget and citations, and exposes
incomplete/unavailable outcomes without guessing.

The POC uses Streamlit, a CLI fallback and eight offline eval cases. Chainlit,
multi-agent, long-term memory, live providers, FastAPI, persistent storage,
Docker/CI and expanded LangSmith evaluation are deferred.

See `docs/poc-3-week-plan.md` for weekly outcomes, Definition of Done and stop
rules. See `docs/ui-plan.md` for the Streamlit/Chainlit comparison and minimal UI
contract.

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
│   ├── learning-log/week-00.md            # Legacy specification baseline
│   ├── learning-log/week-01.md            # Active implementation log
│   ├── poc-3-week-plan.md                 # Active delivery plan and scope
│   ├── progress/roadmap-progress.json
│   ├── project-charter.md
│   ├── ui-plan.md                         # Streamlit UI decision and contract
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
- Streamlit for the one-page POC UI
- Docker Desktop for later local-container work; Docker is not required for the
  three-week POC

The development tooling is configured in `pyproject.toml`. Run:

```bash
uv sync
uv run pytest
uv run isort --check-only . .codex/hooks/format_python.py
uv run black --check . .codex/hooks/format_python.py
uv run flake8 . .codex/hooks/format_python.py
uv run ruff check . .codex/hooks/format_python.py
```

The Streamlit command will be added after the application package and UI
dependency exist; it is not part of the current tooling-only baseline.

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
Read AGENTS.md, PROJECT_STATUS.md, docs/poc-3-week-plan.md,
docs/project-charter.md and docs/learning-log/week-01.md. Summarize the current
three-week POC status and implement only the first incomplete P0 action.
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
