---
name: delivery-orchestrator
description: Coordinate this repository's development agents for a concrete coding goal through planning, implementation, verification, and optionally user-authorized commit/push; do not use for travel-planner runtime agent design.
---

# Delivery Orchestrator

Use this skill only with a concrete development goal for this repository. The
primary Codex session stays responsible for integration and final judgment.

## Goal Card

Extract or create a compact Goal Card before work:

- objective;
- acceptance criteria;
- scope and exclusions;
- verification required;
- explicit commit and push intent.

Implicit skill invocation never authorizes commit or push. Treat absent intent
as no commit and no push; do not interrupt delivery with a yes/no authorization
question.

## Smallest complete change

Understand the requested behavior and affected callers before choosing an
implementation. Apply the minimal-change policy in `AGENTS.md`: reuse existing
project code first, then platform/standard-library support or installed
dependencies. Add an abstraction, option, layer or dependency only when
acceptance needs it. Keep every required safety and product guard; do not
optimize for line count alone.

## Agent Handoffs

For implementation goals, use the project roles in order:

1. **Researcher** inspects requirements and repository evidence, then proposes
   the Goal Card. Researcher does not edit files.
2. **Planner** turns the Goal Card into an ordered plan with file ownership,
   dependencies, acceptance evidence, and checks. Planner does not edit files.
3. **Coordinator** implements the plan, resolves bounded implementation
   choices, and integrates changes.
4. **Tester** verifies the change against the Goal Card. Tester derives
   expectations from contracts or independent inputs and reports every failed
   check with its error and cause.
5. **Deployer** opens a requested PR to `main`; deploys or releases only when
   the Goal Card includes that outcome and project gates allow it.

Skip a stage only when its work is outside the goal, such as deployment for a
documentation-only change. Keep primary session responsible for integration,
durable records, and final judgment. Development agents are separate from
runtime travel-planner roles.

## Goal Lifecycle

Use the Goal API only when the user explicitly asks for a multi-turn goal. Do
not create a goal for routine tasks. Keep an active goal when compatible user
steering arrives. Mark it complete only after its acceptance criteria pass;
pause only when the user explicitly asks; mark blocked only after the same
blocker recurs for three consecutive goal turns without meaningful progress.

## Workflow

1. Read `AGENTS.md`, then the required project records in the order it specifies.
2. Run a git preflight with `git status --short`, current branch, upstream, and
   recent log. Identify unrelated dirty files and coordinate shared-file edits
   before touching them.
3. Select an execution lane from the Goal Card. Delegate only bounded work that
   benefits from it. Declare file ownership and preserve unrelated dirty hunks.
4. The primary session integrates results, reviews changed files, preserves the
   charter's product invariants and explicit user corrections, and keeps
   external providers behind typed interfaces. For storage work, distinguish
   PostgreSQL Compose snapshots from session-only live state and local SQLite.
   Check owner scope, explicit save, migration and recovery before claiming a
   storage change complete. Do not revive rejected behavior or silently broaden
   architecture/policy.
5. Update durable docs only when a checklist item is actually complete and the
   required evidence exists.
6. Run the Goal Card verification: narrowest relevant check first, then the full
   available checks from `AGENTS.md` when applicable. Do not run application,
   frontend, container, browser or live-provider checks for documentation or
   configuration-only work unless acceptance requires them. For deployed
   behavior, check the running image before citing source edits as live.
   Recreating the app clears session-only state. If checks are unavailable,
   report `N/A`.
7. If testing reports a specific failure, allow at most two
   coding-fix/testing-retest cycles. Stop after the second failed retest and
   report the remaining blocker.

## Commit And Push Gates

- Stage explicit files only after acceptance passes.
- Commit only when acceptance passes and the user explicitly requested a commit
  or PR.
- Push only when acceptance passes, a commit exists for this work, and the user
  explicitly requested a push or PR. Push feature branches only; never push
  directly to `main`.
- Open requested PRs against `main` after required checks pass. Do not merge
  unless the user explicitly asks.
- Deploy or release only when the accepted Goal Card includes that outcome and
  existing project gates allow it.
- Do not use force push, amend, rebase, hook bypass, or broad staging.
- If no upstream exists and push was explicitly requested, push the current
  branch to `origin` with `-u` only after confirming the branch name and remote
  are safe.
- Stop and report on authentication failure, branch protection, merge conflict,
  any remote push rejection including non-fast-forward, unexpected dirty state,
  failing checks, or any permission blocker.

## Completion Report

Report changed files, checks run and results, commit hash if created, push
result if performed, and remaining risks or blockers.
