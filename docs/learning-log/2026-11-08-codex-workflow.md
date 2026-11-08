# Learning Log — Portable Codex workflow

Date: 2026-11-08
Status: Current

## Objective

Make the repository's Codex development agents, skills, and workflow reusable
on another machine or in another repository, then open a PR against `main`.
The travel-planner runtime architecture is outside this change.

## Changes

- Kept the manager, planner, coding, and testing responsibilities while
  removing travel-planner product detail from their agent TOML files.
- Removed fixed Codex development models and reasoning effort from the project
  config and agents. A `testing` agent spawn using the former `gpt-5.5` setting
  failed on the current ChatGPT Codex account. Development agents now inherit
  the primary session's available model. The app runtime model is unchanged.
- Added `codex-workflow-transfer` and `project-change-verification` as
  repository skills. Added a transfer guide and linked it from `AGENTS.md` and
  `README.md`. Updated ADR 0001 for the revised development model decision.

## Skill evaluation

- `skill-creator` `quick_validate.py`: both skills valid.
- NVIDIA SkillSpector v2.12.0, recursive `--no-llm` scan: both skills scored
  0/100 LOW with zero findings. This is static security analysis only.
- NVIDIA SkillEvaluator deterministic `quality-check` (source commit
  `d136a597c54784ad8a0ce28542c208602b397a5c`):
  `codex-workflow-transfer` improved from 82.8 to 88.0/100 (B), and
  `project-change-verification` from 82.0 to 87.2/100 (B).
- Read-only forward test found missing destination-path handling and narrow
  skill discovery wording. Both were corrected. A live with-skill/without-skill
  benchmark was not run; no measured skill lift is claimed.

## Repository verification

- `uv run pytest`: 2 passed (development-hook tests).
- `uv run isort --check-only . .codex/hooks/format_python.py`: passed.
- `uv run black --check . .codex/hooks/format_python.py`: passed.
- `uv run flake8 . .codex/hooks/format_python.py`: passed.
- `uv run ruff check . .codex/hooks/format_python.py`: passed.
- `git diff --check`: passed.

The Codex agent model inheritance has not yet been verified in a fresh Codex
session. Live app, provider, and LangSmith checks remain N/A for this tooling
change.
