# Portable Codex development workflow

This repository keeps its Codex development workflow in Git:

| Path | Purpose |
|---|---|
| `AGENTS.md` | Project rules and required reading |
| `.codex/config.toml` | Agent concurrency; models inherit from the session |
| `.codex/agents/*.toml` | Manager, planner, coding, and testing roles |
| `.agents/skills/*/SKILL.md` | Reusable workflow and project verification skills |
| `.codex/hooks.json`, `.codex/hooks/format_python.py` | Python edit hook |
| `pyproject.toml`, `uv.lock` | Development tools and locked dependencies |

The Codex development agents are separate from the app's Coordinator and
Planner runtime agents. The role files stay generic; `AGENTS.md` and project
records carry travel-planner decisions.

## Another machine, same repository

1. Clone the repository and open it as a trusted Codex project. Project config
   and custom agents load in trusted project sessions. Review the hook before
   enabling it through Codex's hook trust flow.
2. Install Codex and `uv`, then run `uv sync`. Choose a model available to the
   signed-in account; development subagents inherit it.
3. Set up credentials in ignored local environment files. Do not transfer
   `.env`, personal Codex config, plugin cache, or credentials through Git.
4. Check that Codex discovers the four agents and two repository skills. Run
   the verification commands in `AGENTS.md`.

Personal skills in `~/.agents/skills/` or `~/.codex/skills/`, including
`caveman`, are not part of this repository. Install them separately on the
other machine if wanted. Plugin-provided skills require the plugin there.
Personal instructions such as an absolute `~/.codex/RTK.md` reference also
need separate setup; they are not repository files.

## Another repository

Copy `.codex/agents/` and the selected `.agents/skills/` folders. Copy
`.codex/config.toml` after checking concurrency needs. Development models
inherit from the signed-in Codex session.
Rewrite `AGENTS.md` from the destination's actual decisions. Copy the hook
only for a compatible Python project with its formatting tools installed.
Remove travel-planner product rules, source paths, and verification commands
that do not apply. Run `$codex-workflow-transfer` to inventory and check the
result before committing it to the destination repository.

## Skill checks

Use `skill-creator`'s `quick_validate.py` for each changed skill. SkillSpector
checks security patterns; it does not measure whether an agent performs better
with a skill. For performance, use a controlled with-skill/without-skill run
through SkillEvaluator when an agent runtime and credentials are available.
Record the exact tool versions, commands, findings, and limits with the change.
