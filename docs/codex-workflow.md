# Portable Codex development workflow

This repository keeps its Codex development workflow in Git:

| Path | Purpose |
|---|---|
| `AGENTS.md` | Project rules and required reading |
| `.codex/config.toml` | Agent concurrency; models inherit from the session |
| `.codex/agents/*.toml` | Researcher, planner, coordinator, tester, and deployer roles |
| `.agents/skills/*/SKILL.md` | Portable workflow-transfer reference |
| `.codex/skills/*/SKILL.md` | Delivery, UI, and security-review guidance |
| `.codex/hooks.json`, `.codex/hooks/format_python.py` | Python edit hook |
| `pyproject.toml`, `uv.lock` | Development tools and locked dependencies |

For implementation goals, the development workflow passes requirements from
Researcher to Planner, implementation to Coordinator, verification to Tester,
and requested PR or release work to Deployer. The Codex roles are separate from
the app's Coordinator, Planner, and Chat runtime roles. Project-specific agent
instructions and skills remain under `.codex/`; `AGENTS.md` and project records
carry product decisions.

## Another machine, same repository

1. Clone the repository and open it as a trusted Codex project. Project config
   and custom agents load in trusted project sessions. Review the hook before
   enabling it through Codex's hook trust flow.
2. Install Codex and `uv`, then run `uv sync`. Choose a model available to the
   signed-in account; development subagents inherit it.
3. Set up credentials in ignored local environment files. Do not transfer
   `.env`, personal Codex config, plugin cache, or credentials through Git.
4. Check that Codex discovers all five agents and the project and portable
   skills. Follow `AGENTS.md` for this repository's active workflow.

Personal skills in `~/.agents/skills/` or `~/.codex/skills/`, including
`caveman`, are not part of this repository. Install them separately on the
other machine if wanted. Plugin-provided skills require the plugin there.
Personal instructions such as an absolute `~/.codex/RTK.md` reference also
need separate setup; they are not repository files.

## Another repository

Copy `.codex/agents/` only after adapting their product rules. Copy selected
`.agents/skills/` folders as portable workflow tools. Copy
`.codex/config.toml` after checking concurrency needs. Development models
inherit from the signed-in Codex session.
Rewrite `AGENTS.md` from the destination's actual decisions. Copy the hook
only for a compatible Python project with its formatting tools installed.
Remove travel-planner product rules, source paths, and verification commands
that do not apply. Run `$codex-workflow-transfer` to inventory and check the
result before committing it to the destination repository.

## Skill checks

Use the available skill manifest validator for each changed skill. Routine code
verification belongs to Tester and `AGENTS.md`, so this repository has no
separate project-change-verification skill. Keep the portable transfer skill
only for cross-repository or cross-machine setup requests. Record commands,
results, and limits with the change.
