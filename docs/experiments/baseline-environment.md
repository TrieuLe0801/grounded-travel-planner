# Baseline Environment

Last updated: 2026-09-21  
Status: Draft — environment details pending

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

## MacBook environment — pending

- Device: MacBook M1
- Architecture: arm64
- macOS version: TODO
- RAM: TODO
- Python version: TODO
- Package manager: TODO
- Git version: TODO
- Container runtime: TODO
- Docker/Compose version: TODO

## Candidate development tooling — pending decision

- Python package manager: TODO
- Test framework: TODO
- Formatter/linter: TODO
- Dependency lock strategy: TODO
- Local environment strategy: TODO

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
