---
name: project-change-verification
description: Verify code or development-tooling changes in this repository and record durable evidence when a roadmap item is completed.
---

# Project Change Verification

Use `AGENTS.md` for the current project rules and read order. Start with the
narrowest check that exercises the change. Then run the full available suite:

```bash
uv run pytest
uv run isort --check-only . .codex/hooks/format_python.py
uv run black --check . .codex/hooks/format_python.py
uv run flake8 . .codex/hooks/format_python.py
uv run ruff check . .codex/hooks/format_python.py
git diff --check
```

Record commands, results, and limits in the current learning log. When a
roadmap checklist item is complete, update `PROJECT_STATUS.md` and
`docs/progress/roadmap-progress.json` too. Do not call development-hook tests
application tests or claim live provider behavior from offline checks.
If a command cannot run, record the exact reason and mark that check N/A or
blocked; never turn a missing dependency into a claimed pass. These commands
require `uv` and the locked development dependencies in `pyproject.toml`.
