# Learning Log — Week 01

Period: 2026-09-22 to 2026-09-28
Status: Historical log; previous product scope superseded on 2026-10-14

Current work is recorded in [2026-10-14-scope-reset.md](2026-10-14-scope-reset.md).
The objectives, next steps and progress below belong to the earlier scope.

## Week objective

Move from a specification-heavy greenfield repository to the first executable,
deterministic LangGraph vertical slice with typed state and unit tests.

## Starting baseline

- Focused three-week POC charter: accepted.
- Three-week roadmap: 6/53 items at the 2026-09-22 rebaseline.
- Executable POC: 0%; no application package, graph, fixture, application test
  or metric existed at the rebaseline.
- Primary fixture journey: TP.HCM → Đà Nẵng, 3 days.
- Acceptance path must work offline without a model key or network.

## This week

1. Create the `uv` project scaffold, package layout, pytest and Ruff config.
2. Define minimal typed request, evidence, state and outcome contracts.
3. Implement input/date validation and traveler defaults.
4. Compile a deterministic graph with a clarification branch.
5. Add tests for ready, clarify, invalid-date and loop-limit paths.

## Evidence required to close the week

- `pyproject.toml` and `uv.lock`.
- Importable source package and at least one graph module.
- Automated tests for the first vertical slice.
- Successful pytest, isort, Black, flake8 and Ruff results recorded here.
- Updated `PROJECT_STATUS.md` and roadmap progress JSON.

## Entries

### 2026-09-22 — Scope rebaseline

**Question**

What is the smallest POC that still demonstrates LangGraph value within three
weeks?

**Learned**

- Specification readiness and implementation progress need separate measures.
- Live data, long-term memory and multi-agent experiments are not necessary to
  demonstrate state, routing, bounded loops and deterministic validation.

**Tried**

- Audited the current artifacts and replaced the original eight-week roadmap
  with a three-week P0/P1/P2 plan.

**Result**

- Scope, Definition of Done, calendar, stop rules and backlog are recorded.
- The first implementation task is now the `uv` scaffold, not another broad
  specification pass.

**Decision**

- Use one single graph, structured input, offline fixtures and a CLI demo.
- Keep a deterministic acceptance path even if an optional model adapter is
  added later.

**Evidence**

- `docs/poc-3-week-plan.md`
- `docs/adr/0002-three-week-poc-scope.md`
- `PROJECT_STATUS.md`

**Next**

- Create `pyproject.toml`, lock dependencies and add the smoke test.

### 2026-09-22 — Reduce charter to executable features

**Question**

Which charter features are realistically implementable inside the three-week
delivery window?

**Learned**

- The broader charter still carried eight-week topics and made the active scope
  harder to read.
- Eight failure-mode groups are enough for the first deterministic acceptance
  suite.

**Tried**

- Rewrote the charter around structured input, one fixture journey, one plan,
  four outcomes, deterministic validation, CLI demo and offline evaluation.

**Result**

- Removed active requirements for accessibility/dietary recommendations,
  severe-allergy handling, memory, feedback, bilingual parsing, live providers
  and recommendation alternatives.
- Kept those topics only in a concise post-POC backlog.

**Decision**

- The charter now contains only P0 features plus a short list of optional P1
  integrations.
- Golden-set scope is fixed at eight failure-mode groups.

**Evidence**

- `docs/project-charter.md`
- `docs/poc-3-week-plan.md`
- `docs/roadmap.html`

**Next**

- Create the `uv` scaffold and first smoke test; do not add more specification
  work unless implementation exposes a concrete gap.

### 2026-09-22 — Select the POC UI

**Question**

Should the three-week demo use Streamlit or Chainlit?

**Learned**

- Streamlit forms batch structured widgets on submit, Session State preserves
  values across reruns in the current WebSocket session, and `AppTest` supports
  headless UI checks.
- Chainlit provides a chat lifecycle, `AskUserMessage`, step visualization,
  streaming and an official LangGraph integration. Resume across disconnected
  sessions requires authentication and data persistence.

**Tried**

- Compared the current structured trip contract with official Streamlit and
  Chainlit UI/integration documentation.

**Result**

- Streamlit is the lower-risk match for a one-page trip form and structured
  itinerary/cost/source output.
- Chainlit is more appropriate if conversational clarification becomes the
  primary UX after the POC.

**Decision**

- Add a minimal Streamlit page and two `AppTest` cases to P0 in Week 3.
- Keep Chainlit, chat history, auth, persistence and full chat UX post-POC.

**Evidence**

- `docs/ui-plan.md`
- `docs/adr/0003-streamlit-poc-ui.md`
- `docs/project-charter.md`

**Next**

- Keep UI implementation blocked until the graph and offline eval path are
  stable.

### 2026-09-28 — Rebase and reconcile the shortened roadmap

**Question**

How can the latest development-tooling commit be integrated without losing the
three-week POC rebaseline already in the working tree?

**Learned**

- Upstream added the Python toolchain, lockfile, Codex development agents and
  hook tests, but did not add travel-planner application code.
- Four Week 1 scaffold checklist items now have repository evidence; application
  progress must still remain separate from development-tooling progress.

**Tried**

- Fetched `origin/main`, rebased local `main` to commit `6acddd6` and reapplied
  the saved working tree.
- Merged the five overlapping documentation files and renumbered the POC ADRs
  after the upstream tooling ADR claimed sequence number 0001.
- Migrated the interactive roadmap from state version 7 to 8 while preserving
  existing browser checklist state.

**Result**

- Local `main` matches `origin/main`; the shortened roadmap is 10/53 (19%).
- `uv lock --check`: passed.
- `uv run pytest`: 2 passed.
- isort, Black, flake8 and Ruff checks: passed.
- Roadmap progress JSON and embedded roadmap JavaScript syntax: valid.

**Decision**

- Keep the three-week, fixture-first scope as the active delivery plan.
- Count the environment record, `pyproject.toml`, `uv.lock` and pytest/Ruff
  setup as complete; do not count hook tests as application implementation.

**Evidence**

- `PROJECT_STATUS.md`
- `docs/progress/roadmap-progress.json`
- `docs/roadmap.html`
- `pyproject.toml`, `uv.lock`, `tests/test_format_python_hook.py`

**Next**

- Create the application/data layout and import smoke test, then implement the
  typed state and first deterministic LangGraph path.
