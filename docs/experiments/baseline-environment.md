# Baseline Environment

Last updated: 2026-09-21  
Status: Planned toolchain selected — actual machine versions pending

## Project state

This is a greenfield project.

- Application implementation: not started.
- LangGraph workflow: not implemented.
- Unit/integration tests: not created.
- Executable quality baseline: not available.
- Measured latency, token usage and cost: not available.

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
- macOS version: TODO
- RAM: TODO
- Python requirement: `>=3.10`
- Installed Python version: TODO — capture on the target MacBook
- Python package and environment manager: `uv`
- Installed `uv` version: TODO — capture on the target MacBook
- Git version: TODO
- Container runtime: Docker Desktop
- Docker Engine/Compose versions: TODO — capture on the target MacBook

## Confirmed development tooling

- Python: `>=3.10`
- Package and virtual-environment manager: `uv`
- Test framework: `pytest`
- Formatter and linter: Ruff
- Dependency lock strategy: commit `uv.lock` after dependencies are introduced
- Local environment strategy: project-local `.venv` managed by `uv`
- Container runtime: Docker Desktop using arm64-compatible images where
  available

The project has not selected an exact Python minor version yet. The interpreter
used on the MacBook must satisfy `>=3.10`, and its exact version must be recorded
before the first executable baseline is accepted.

## Planned verification commands

These commands become active after `pyproject.toml` and application code exist:

```bash
uv sync
uv run pytest
uv run ruff check .
uv run ruff format --check .
docker compose config
```

They are currently planned commands, not successful verification results.

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
| Unit tests | N/A | No implementation exists |
| Integration tests | N/A | No implementation exists |
| Evaluation run | N/A | Dataset and executable target do not exist |
| Container build | N/A | Container contract not created |
| Latency/cost baseline | N/A | No model or tool execution exists |
