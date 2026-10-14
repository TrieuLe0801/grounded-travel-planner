# Learning Log — New scope adoption

Date: 2026-10-14
Status: Current

## Objective

Replace the previous POC plan with the user's new sightseeing-webapp request
and make the repository's entry points consistent with the agreed scope.

## Decisions recorded

- Input: destination/place, concrete start date and user-selected day count.
- Search through Tavily before proposing sightseeing places and an itinerary.
- Chat edits timing, order and the set of places.
- LangChain/LangGraph runtime with Coordinator and Planner using `gpt-5.5`.
- Code validation before applying plan changes.
- App state is session-only; LangSmith traces every turn and groups child runs
  by the same session ID. Traces are not app persistence.
- The old delivery dates, fixture journey, pricing rules and completion counts
  do not govern the new scope. No new deadline has been agreed.

## Artifacts

- [Charter](../project-charter.md) and [implementation plan](../implementation-plan.md)
- [ADR 0004](../adr/0004-city-sightseeing-webapp.md)
- [UI proposal](../ui-plan.md), [roadmap](../roadmap.html) and
  [progress JSON](../progress/roadmap-progress.json)
- [Repository status](../../PROJECT_STATUS.md), [README](../../README.md) and
  [Codex instructions](../../AGENTS.md)
- [Environment template](../../.env.example)
- [Historical snapshots](../archive/2026-10-14/README.md)

## Verification

- Document checks: passed; 61 local Markdown/HTML links resolve.
- Progress JSON: parsed and checked; 3 phases with 12 implementation tasks,
  all uncompleted. Completed planning artifacts exist.
- Current roadmap: old localStorage seeds/task IDs removed.
- Environment template: credential values empty and runtime model `gpt-5.5`;
  existing `.env` remains ignored and `.env.example` is trackable.
- `uv lock --check`: passed.
- `uv run pytest`: 2 passed, covering the existing development hook.
- `uv run isort --check-only . .codex/hooks/format_python.py`: passed.
- `uv run black --check . .codex/hooks/format_python.py`: passed.
- `uv run flake8 . .codex/hooks/format_python.py`: passed.
- `uv run ruff check . .codex/hooks/format_python.py`: passed.
- `git diff --check`: passed.
- Independent read-only review: passed with no actionable issues; all 12
  acceptance scenarios match the approved drafts. Its broader link check
  covered 65 local links, including historical records, with no missing targets.
  The five archive snapshots match the previous HEAD after newline normalization.

Application tests and live model/Tavily/LangSmith checks: N/A / not run; the
application is not implemented by this documentation update. Tooling checks
do not demonstrate runtime behavior or trace delivery.

## Next

Implement the first incomplete step in the new plan: contracts, two runtime
agents, LangGraph state/routing, Tavily, validation and tracing for initial
planning. Preserve existing tooling and local secrets.
