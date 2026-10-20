# ADR 0001 — Python development tooling

Status: Accepted
Date: 2026-09-26

## Context

The Week 0 baseline selected `uv`, `pytest` and Ruff, but the Python project did
not yet exist. The development workflow now needs Codex coding/testing helpers
and automatic PEP 8 formatting with isort, Black and flake8.

These are development assistants. They are separate from the travel planner's
runtime agent topology, which remains single-agent-first.

## Decision

- Define project-scoped `manager`, `planner`, `coding` and `testing` Codex agents
  in `.codex/agents/`. The primary Codex session uses `gpt-6-sol` and acts as
  manager; an explicit `manager` subagent uses the same model. `planner` uses
  `gpt-5.6-terra`; `coding` and `testing` use `gpt-5.5`. All four roles use
  medium reasoning effort. The manager assigns bounded planning, coding and
  testing tasks, coordinates shared files and integrates verification results.
- Use a project-scoped Codex `PostToolUse` hook for Python files edited through
  `apply_patch`. Run isort, then Black, then flake8. Flake8 checks style; it does
  not reformat files.
- Keep Ruff lint checks as a supplementary quality check. Black replaces Ruff
  format as the canonical formatter. Configure isort's Black profile and an
  88-character line length across tools.
- Manage the tools with `uv` in `pyproject.toml` and commit `uv.lock`. Keep the
  application code and runtime dependencies out of scope for this tooling step.

## Alternatives considered

- Ruff alone: simpler, but does not satisfy the requested isort, Black and
  flake8 workflow.
- A Git pre-commit hook: useful at commit time, but does not format a Codex edit
  immediately after `apply_patch`.
- Running on every Codex tool call: would repeatedly touch unrelated or
  pre-existing dirty Python files.

## Consequences

- New or changed project hooks require Codex trust review through `/hooks` before
  they run. The hook only covers `apply_patch`; Python files edited by other
  means need the documented manual commands.
- Project `.codex/config.toml` and custom agents load in trusted Codex project
  sessions. The manager workflow does not alter the application's runtime
  single-agent-first decision.
- `uv` may sync the environment when a hook first runs. Hook failures appear in
  Codex as a warning; they do not undo the source edit.
- The baseline verification commands are `uv run pytest`, `uv run isort
  --check-only . .codex/hooks/format_python.py`, `uv run black --check .
  .codex/hooks/format_python.py`, `uv run flake8 .
  .codex/hooks/format_python.py` and `uv run ruff check .
  .codex/hooks/format_python.py`. The explicit hook path covers the hidden
  `.codex/` directory.

## Review triggers

- The team adopts a different editor or hook event for Python changes.
- Black, isort and Ruff produce incompatible output on real application code.
- A controlled workflow comparison justifies changing the development agents.
- A requested model is unavailable in the selected Codex client or account.

## Amendment — 2026-10-20

The development-agent instructions now cover the repository's full product
stack: typed Python/LangGraph and FastAPI code, React/Tailwind UI, container and
environment configuration, and durable project documents. The coding role no
longer describes itself as Python-only. The manager must preserve pre-existing
dirty hunks, use direct user steering as a constraint, assign explicit file
ownership, and avoid restarting an approach that the user has rejected.

The delivery workflow detects explicit commit/push authorization and otherwise
does neither; it does not pause to ask a yes/no authorization question. Agents
must distinguish static, offline, browser, container and live-provider evidence
and may not make the latter claims without a corresponding executed artifact.
These development roles remain separate from the runtime Coordinator, Planner,
Chat and `tavily_tool` graph node.
