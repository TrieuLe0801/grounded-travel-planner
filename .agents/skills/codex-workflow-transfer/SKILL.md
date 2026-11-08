---
name: codex-workflow-transfer
description: Transfer Codex agents, skills, and development workflow to another repository or machine when the user requests a reusable setup or migration.
---

# Codex Workflow Transfer

Inspect the source and destination before copying. Inventory project files
(`AGENTS.md`, `.codex/config.toml`, `.codex/agents/`, hooks, and
`.agents/skills/`) separately from user and plugin installations.
If the destination is not supplied, complete the source inventory and request
its repository path before copying files.

Preserve reusable role responsibilities. Rewrite product rules, paths, tool
commands, model choices, and verification gates against the destination's
actual code and decisions. Keep runtime application agents separate from Codex
development agents. Do not copy ignored environment files, credentials, plugin
caches, or personal configuration by default.

For another machine, put shareable files in version control. Document any
machine-local installs and credentials that must be set up separately. For a
different repository, adapt `AGENTS.md` and hooks before enabling them.

Validate skill manifests, parse agent and config TOML, inspect hook commands,
check tracked files and ignored secrets, and run the destination's relevant
checks. Confirm agent model inheritance or availability on the destination
account. Report what transferred, what changed, and what remains machine-local.

For example, when moving a Python project's workflow to another machine,
commit the repository files, then document the separate Codex and Python tool
installs. When moving it to a different codebase, rewrite `AGENTS.md` and
verification commands against that codebase before claiming the transfer done.
