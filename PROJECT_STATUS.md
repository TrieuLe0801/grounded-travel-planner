# Project Status

Last updated: 2026-09-21

## Current milestone

Week 0 — Project charter, constraints and baseline.

Artifact-backed progress: **23 / 34 checklist items (68%)**.

This is an independent LangChain/LangGraph/LangSmith learning project. Only
architecture, baselines, workflow outcomes and invariants recorded in this
repository apply.

This percentage is based on files present in this repository. Browser-only
checkboxes or notes stored in `localStorage` are not evidence unless exported
into the repository.

## Session status

| Session | Completed | Total | Status |
|---|---:|---:|---|
| 0.1 Project charter | 6 | 6 | Complete |
| 0.2 Technical baseline | 4 | 5 | In progress |
| 0.3 Golden set V0 | 2 | 8 | In progress |
| 0.4 Hard constraints | 5 | 9 | In progress |
| 0.5 Codex context | 6 | 6 | Complete |

## Done

### Project charter

- Defined target users, primary journey, MVP scope and non-goals.
- Defined research questions for orchestration, multi-agent and memory.
- Accepted ISO-date, traveler-count, total-budget and recommendation contracts.
- Defined deterministic synthetic flight/lodging pricing for the MVP.
- Defined accessibility, dietary, severe-allergy and evidence policies.
- Reviewed and accepted `docs/project-charter.md` for MVP.

### Technical and quality baseline

- Recorded the project as greenfield: code, tests and measured metrics are
  currently `N/A`, not failed checks.
- Sketched the target flow from input normalization through LangChain tools,
  LangGraph orchestration, deterministic validation and final output.
- Listed core product/evidence invariants and explicit workflow outcomes.
- Selected the MacBook M1 toolchain: Python `>=3.10`, `uv`, `pytest`, Ruff and
  Docker Desktop. Exact installed versions remain to be captured on the target
  machine.

### Initial evaluation design

- Defined at least three clarification situations.
- Defined a wheelchair and step-free acceptance scenario.
- Recorded 22 scenario descriptions in the charter; these are not yet a
  machine-readable evaluation dataset.

### Durable project context

- Added repository-level `AGENTS.md` with project boundaries, invariants and the
  required reading order for Codex.
- Added `docs/learning-log/week-00.md` using the learn–try–result–decision model.
- Added this Done / Now / Next / Blockers status file.
- Kept Markdown as the durable source of truth and exported roadmap state to
  `docs/progress/roadmap-progress.json`.

## Now

- Capture the actual macOS, RAM, Python, `uv`, Git, Docker and Compose versions
  on the MacBook M1.
- Define evaluation metrics before assigning any measured values.
- Convert charter scenarios into a versioned JSONL golden set.
- Turn accessibility and dietary policies into typed schemas.

## Next

1. On the MacBook M1, fill the remaining version fields in
   `docs/experiments/baseline-environment.md`.
2. Create `docs/evaluation-metrics.md` with metric names, formulas and expected
   inputs; do not invent measurements.
3. Create `data/eval/travel-scenarios-v0.jsonl` with structured expected
   outcomes, constraints, evidence requirements and forbidden claims.
4. Add the missing happy-path, impossible-budget, tool-failure, stale-evidence,
   severe-allergy-boundary and memory-conflict cases.
5. Define typed accessibility and dietary constraint schemas.
6. Specify consent, update and forget behavior for sensitive preferences.
7. Create ADRs for single-agent-first and deterministic synthetic pricing.

## Blockers and deferred dependencies

- The actual macOS, RAM, Python, Git and container versions can only be recorded
  on the target MacBook.
- Live flight, lodging and availability providers are intentionally deferred.
- The synthetic pricing fixture schema and sample routes are not implemented.
- Executable tests and measured metrics begin after the remaining Week 0
  specification artifacts are complete.

## Important files

- `AGENTS.md`
- `docs/project-charter.md`
- `docs/learning-log/week-00.md`
- `docs/experiments/baseline-environment.md`
- `docs/progress/roadmap-progress.json`
- `docs/roadmap.html`
