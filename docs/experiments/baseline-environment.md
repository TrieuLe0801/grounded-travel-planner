# Baseline Environment

Last updated: 2026-09-28
Status: Historical environment snapshot; Docker Engine was pending at capture

The measurements and project-state notes below describe the earlier environment
and scope. See [current status](../../PROJECT_STATUS.md) and the
[new implementation plan](../implementation-plan.md) for ongoing work. Preserve
these captured versions; verify the actual target environment before execution.

## Project state

This is a greenfield project.

- Travel-planner application implementation: not started.
- LangGraph workflow: not implemented.
- Travel-planner unit/integration tests: not created.
- Development-hook tests and quality checks: available.
- Streamlit UI: not implemented.
- Measured latency, token usage and cost: not available.

The project was rebaselined to a three-week POC on 2026-09-22. Missing Docker
or Compose details do not block the local `uv` vertical slice. The available
runtime versions are recorded below; only Docker Engine remains pending.

These values are `N/A`, not failed checks. No test or metric result should be
invented before an executable baseline exists.

## What Week 0 establishes

Week 0 records the pre-implementation baseline:

- product charter and scope;
- input/output contracts;
- hard constraints and evidence policy;
- target decisions and evaluation scenarios;
- local development environment;
- planned metrics and verification commands.

## MacBook M1 environment

- Device: MacBook M1
- Architecture: arm64
- macOS version: 26.6.2 (build 25G83), captured with `sw_vers`
- RAM: 16 GiB, captured with `sysctl -n hw.memsize`
- Python requirement: `>=3.10`
- Installed project Python version: CPython 3.10.21, managed by `uv`
- System `python3`: 3.9.6; the hook script supports this interpreter
- Python package and environment manager: `uv`
- Installed `uv` version: 0.12.19
- Git version: 2.54.0 (Apple Git-157)
- Container runtime: Docker Desktop
- Docker CLI version: 20.10.18
- Docker Engine version: TODO — daemon was unavailable on 2026-09-26
- Docker Compose version: v5.0.0-desktop.1

## Confirmed development tooling

- Python: `>=3.10`
- Package and virtual-environment manager: `uv`
- Test framework: `pytest`
- Formatters: isort and Black; linters: flake8 and Ruff
- POC UI framework: Streamlit (selected, not installed yet)
- Dependency lock strategy: commit `uv.lock` after dependencies are introduced
- Local environment strategy: project-local `.venv` managed by `uv`
- Container runtime: Docker Desktop using arm64-compatible images where
  available

The project uses Python 3.10 locally through `.python-version`, while retaining
`>=3.10` as its declared support range. See
`docs/adr/0001-python-development-tooling.md` for the tooling decision.

## Planned verification commands

The Python tooling checks are active. Docker verification requires a running
daemon and a future Compose contract:

```bash
uv sync
uv run pytest
uv run isort --check-only . .codex/hooks/format_python.py
uv run black --check . .codex/hooks/format_python.py
uv run flake8 . .codex/hooks/format_python.py
uv run ruff check . .codex/hooks/format_python.py
docker compose config
```

The pytest suite currently covers only the formatting hook, not application
behavior. Verification results for this tooling change are recorded in the
current learning log.

## Target control flow — initial sketch

The initial framework-oriented flow is:

```text
input
  -> normalize and validate
  -> clarify if required
  -> call travel research tools
  -> aggregate and validate tool results
  -> itinerary generation
  -> deterministic validators
  -> citation verification
  -> plan ready / partial result / clarification / unavailable
```

A more detailed component diagram can later be added to
`docs/architecture-baseline.md`.

## Metrics to define — pending

Create `docs/evaluation-metrics.md`. Metrics are definitions only during Week 0;
measured values begin after the first executable baseline exists.

## Verification status

| Check | Status | Reason |
|---|---|---|
| Travel-planner unit tests | N/A | No application implementation exists |
| Development-hook tests | Available | See `tests/test_format_python_hook.py` |
| Integration tests | N/A | No implementation exists |
| Evaluation run | N/A | Dataset and executable target do not exist |
| Container build | N/A | Container contract not created |
| Latency/cost baseline | N/A | No model or tool execution exists |
