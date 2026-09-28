# Project Status

Last updated: 2026-09-28

## Current milestone

Week 1 of the three-week POC — executable vertical slice.

Delivery window: **2026-09-22 to 2026-10-12**.

The active plan is `docs/poc-3-week-plan.md`. The earlier Week 0 + eight-week
roadmap has been replaced because only three weeks remain.

## Progress snapshot

| View | Progress | Interpretation |
|---|---:|---|
| Three-week roadmap | 10 / 53 (19%) | Scope plus four evidenced tooling/scaffold items are complete |
| Rebaseline session | 6 / 6 (100%) | Scope and acceptance target are complete |
| Executable POC | 0% | Development tooling exists, but no application package, graph, fixture or measured metric exists yet |

Planning progress must not be reported as implementation progress.

## Three-week session status

| Session | Completed | Total | Status |
|---|---:|---:|---|
| 1.1 Rebaseline and acceptance | 6 | 6 | Complete |
| 1.2 Project scaffold and contracts | 4 | 6 | In progress |
| 1.3 Deterministic graph slice | 0 | 6 | Not started |
| Week 2 Grounded planner | 0 | 18 | Not started |
| Week 3 Streamlit UI, evaluation and demo | 0 | 17 | Not started |

## Done

### Retained decisions

- Accepted the focused input/output contract.
- Defined ISO-date, traveler defaults, total-budget and synthetic-pricing rules.
- Defined four POC workflow outcomes and eight acceptance scenarios.
- Selected Python `>=3.10`, `uv`, `pytest`, Ruff and Docker Desktop as the
  broader development baseline.
- Created durable Codex instructions, learning log and progress artifacts.

### Three-week rebaseline

- Fixed the delivery window and reduced the plan to P0/P1/P2 priorities.
- Selected one primary offline fixture journey: TP.HCM → Đà Nẵng, 3 days.
- Selected a single LangGraph workflow, structured input and CLI/demo output.
- Reduced POC acceptance to one recommended plan and eight high-value cases.
- Selected a one-page Streamlit UI with CLI fallback for the final demo.
- Deferred Chainlit, multi-agent, long-term memory, live providers, FastAPI,
  persistent storage, Docker/CI and expanded evaluation.
- Added deadline stop rules and a feature freeze from 2026-10-09.
- Recorded the decisions in ADRs 0002 and 0003.

### Development tooling and environment

- Captured the MacBook M1 runtime versions; Docker Engine remains pending and
  does not block the POC.
- Added `pyproject.toml`, `.python-version` and a committed `uv.lock`.
- Configured pytest, isort, Black, flake8 and Ruff.
- Added project-scoped Codex development agents, a Python formatting hook and
  two passing hook tests. These support development; they are not application
  code or the travel planner's runtime topology.

## Now

1. Create the application package plus `data/eval` layout and an import smoke
   test.
2. Add LangGraph and the minimum runtime dependencies to `pyproject.toml`, then
   refresh `uv.lock`.
3. Define the smallest typed request, evidence, state and outcome contracts.
4. Create the first TP.HCM → Đà Nẵng fixture.
5. Compile the first deterministic LangGraph path.

## Next

1. Implement required-input and date validation.
2. Route valid input to fixture research and missing input to clarification.
3. Add a loop limit and tests for ready, clarify and invalid-date paths.
4. Start the golden set with 3–5 cases; grow to eight only after the vertical
   slice runs.

## Blockers and risks

- Docker Engine version is pending because the daemon was unavailable on
  2026-09-26; it is explicitly non-blocking for this POC.
- No application package or executable graph exists yet; Week 1 remains at the
  development-tooling stage despite the passing hook tests.
- Real model/provider credentials may not be available. The deterministic path
  remains the acceptance path and must not depend on an API key.
- Scope expansion is the main deadline risk. P1/P2 work is blocked while any P0
  test is red.
- Streamlit must stay a thin adapter; chat, multipage navigation and visual
  polish are cut first if the graph/eval schedule slips.

## Deferred after 2026-10-12

- Live travel providers and real availability/price research.
- Persistent checkpointing and restart/resume.
- LangSmith experiments beyond an optional synthetic-data spike.
- Chainlit/chat-first UX, FastAPI, multipage/custom UI, Docker, CI/CD and
  deployment.
- Long-term memory, durable feedback and multi-agent experiments.
- Accessibility/dietary support, full bilingual behavior, natural-language
  parsing and a larger dataset.

## Important files

- `docs/poc-3-week-plan.md`
- `docs/adr/0002-three-week-poc-scope.md`
- `docs/adr/0003-streamlit-poc-ui.md`
- `docs/ui-plan.md`
- `docs/project-charter.md`
- `docs/learning-log/week-01.md`
- `docs/learning-log/week-00.md` (legacy baseline)
- `docs/progress/roadmap-progress.json`
- `docs/roadmap.html`
- `AGENTS.md`
