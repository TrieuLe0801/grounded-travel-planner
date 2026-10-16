# Grounded Travel Planner — Codex Instructions

## Project boundary

- The active product is the city/place sightseeing webapp defined in
  `docs/project-charter.md` and `docs/implementation-plan.md`.
- The user replaced the earlier POC scope on 2026-10-14. Archived documents,
  superseded ADRs and historical logs are background, not active requirements.
- Repository Markdown is the durable source of truth. Record explicit new user
  decisions before using them as ongoing project context.

## Read before making changes

Read these records in order:

1. `PROJECT_STATUS.md`
2. `docs/project-charter.md`
3. `docs/implementation-plan.md`
4. `docs/learning-log/2026-10-14-scope-reset.md` (current log)
5. Relevant accepted ADRs; ADR 0004 governs the current product/runtime scope.
6. `docs/experiments/baseline-environment.md` for historical environment context
   when needed. Verify the actual target environment before making claims.

## Architecture principles

- Use LangChain for model, agent, tool and structured-output integrations.
- Use LangGraph for explicit state, routing, delegation and bounded processing.
- The runtime requires at least two agents. Start with Coordinator and Planner:
  Coordinator owns user-facing chat/delegation; Planner proposes all plan changes
  and searches via Tavily. Both use the requested `gpt-5.5` model.
- Implement schedule, input and source-reference checks in code.
- Keep one canonical current plan in session state. Commit a candidate only
  after validation; Coordinator explains the committed result.
- Trace all chat turns, agents, tools and validation through LangSmith. Propagate
  the same `thread_id` metadata to root and child runs in a session.
- App conversation/trip state is session-only and isolated between users.
  LangSmith traces are observability data and are not used to resume app state.
- Typed provider interfaces keep model/search integration separate from UI.
- Streamlit is the current one-page UI proposal, not a reason to duplicate
  domain logic or add persistence.

## Product invariants

- Accept destination/place, a concrete start date and user-selected day count.
- Search for actual information before claiming sourced recommendations.
- Never fabricate source URLs, opening hours or tool results. Source references
  must originate from actual search results and match the recommended place.
- Label estimated visit/travel times and information that remains unverified.
- Reject or explain overlapping/out-of-range schedule entries and known
  opening-hour conflicts before treating an edit as successful.
- Preserve the previous plan when a candidate fails, and explain that it has
  not yet satisfied the new request.
- Chat supports time/day changes, reordering and adding/removing/replacing places.
  Ordinary chat should not mutate the plan or trigger unnecessary research.
- Bound search calls, repairs and graph steps for every turn.
- Keep secrets out of model inputs, traces, logs and tracked files.

## Working agreements

- The primary Codex session manages development requests. Assign bounded work to
  project-scoped `planner`, `coding` and `testing` roles when needed, wait for
  results and coordinate shared-file edits.
- Codex development agents/configuration are separate from the webapp runtime
  Coordinator/Planner. Preserve the tooling decision in ADR 0001.
- Retain Python `>=3.10`, `uv`, `pytest`, isort, Black, flake8 and Ruff.
  Runtime dependencies and an application package remain implementation work.
- Keep modules small, typed and testable. Automated unit tests use mocked
  providers and never call live models/search/tracing services.
- Verify live model, Tavily and LangSmith integration separately when credentials
  and an executable flow are available; do not report it as tested beforehand.
- Use ignored environment files for credentials; `.env.example` contains
  placeholders only. Preserve existing local secrets.
- Update status, the current log, progress JSON and the roadmap summary when
  their recorded state changes. Do not carry over old POC completion counts.
- Add/update an ADR when changing an accepted architectural decision.
- Do not claim application code, test results, traces or metrics exist without
  executable artifacts and verification evidence.
- Run the narrowest relevant checks, then the full existing suite as applicable:
  `uv run pytest`, `uv run isort --check-only . .codex/hooks/format_python.py`,
  `uv run black --check . .codex/hooks/format_python.py`,
  `uv run flake8 . .codex/hooks/format_python.py` and
  `uv run ruff check . .codex/hooks/format_python.py`.

## Completion evidence

Record the durable artifact and actual verification result. Planning progress,
browser state and passing development-hook tests do not demonstrate a working
travel-planner webapp. Application and live-trace acceptance is defined in the
current charter and implementation plan.
