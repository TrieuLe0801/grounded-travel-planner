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
5. Relevant accepted ADRs; ADR 0004, ADR 0009, ADR 0011 and ADR 0012 govern the
   current product/runtime scope.
6. `docs/experiments/baseline-environment.md` for historical environment context
   when needed. Verify the actual target environment before making claims.

## Architecture principles

- Use LangChain for model, agent, tool and structured-output integrations.
- Use LangGraph for explicit state, routing, delegation and bounded processing.
- The runtime has Coordinator, Planner and Chat roles. Coordinator classifies,
  routes and summarizes session context; Planner proposes all plan changes;
  Planner and Chat request Tavily search through the shared `tavily_tool` graph
  node when needed. That node is the only runtime caller of the search provider.
  Coordinator defaults to `gpt-5.5`,
  Planner defaults to `gpt-5.4-mini`, and Chat defaults to `gpt-4.1`.
- Implement schedule, input and source-reference checks in code.
- Keep one canonical current plan, bounded transcript and rolling summary in
  session state. Coordinator receives at most eight recent messages (600
  characters each) and the prior summary, then gives Planner and Chat a summary
  of at most 1,200 characters instead of forwarding the transcript. Commit a
  candidate only after validation; Chat explains the result and cannot mutate
  the plan. Planner and Chat share a maximum of two Tavily calls per turn.
- Trace all chat turns, agents, tools and validation through LangSmith. Propagate
  the same `thread_id` metadata to root and child runs in a session.
- App conversation/trip state is session-only and isolated between users.
  LangSmith traces are observability data and are not used to resume app state.
- A bounded background turn may continue across Streamlit page navigation, but
  its Future and result integration remain owned by the originating session.
  Only one turn may be in flight per session; workers never mutate Session State.
- Typed provider interfaces keep model/search integration separate from UI.
- The JavaScript/Tailwind frontend and thin Python HTTP adapter are the current
  UI under ADR 0008. Streamlit remains available during migration. Neither UI
  duplicates domain logic or adds persistence.

## Product invariants

- Accept destination/place, a concrete start date and user-selected day count.
- Search for actual information before claiming sourced recommendations.
- Never fabricate source URLs, opening hours or tool results. Source references
  must originate from actual search results. The `source_place_mismatch` token
  overlap gate is temporarily disabled because it rejected valid sources; do
  not restore it without a new user decision and a better matching strategy.
- Label estimated visit/travel times and information that remains unverified.
- Reject or explain overlapping/out-of-range schedule entries and known
  opening-hour conflicts before treating an edit as successful.
- Preserve the previous plan when a candidate fails, and explain that it has
  not yet satisfied the new request.
- Chat supports time/day changes, trip extension, reordering and
  adding/removing/replacing places. Ordinary chat should not mutate the plan or
  trigger unnecessary research.
- Bound search calls, repairs and graph steps for every turn.
- Keep secrets out of model inputs, traces, logs and tracked files.

## Working agreements

- The primary Codex session manages development requests. Assign bounded work to
  project-scoped `planner`, `coding` and `testing` roles when needed, wait for
  results and coordinate shared-file edits.
- Codex development agents/configuration are separate from the webapp runtime
  Coordinator/Planner/Chat. Preserve the tooling decision in ADR 0001.
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
