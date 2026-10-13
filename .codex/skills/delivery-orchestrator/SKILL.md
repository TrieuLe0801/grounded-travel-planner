---
name: delivery-orchestrator
description: Coordinate this repository's development agents for a concrete coding goal through planning, implementation, verification, and optionally user-authorized commit/push; do not use for travel-planner runtime agent design.
---

# Delivery Orchestrator

Use this skill only with a concrete development goal for this repository. The
primary Codex session stays responsible for integration and final judgment.

## Required Input

Confirm the request includes:

- the development goal and acceptance criteria;
- whether the user explicitly requested a commit;
- whether the user explicitly requested a push.

Implicit skill invocation never authorizes commit or push. If commit or push
intent is absent, complete the code workflow and report what remains.

## Workflow

1. Read `AGENTS.md`, then the required project records in the order it specifies.
2. Run a git preflight with `git status --short`, current branch, upstream, and
   recent log. Identify unrelated dirty files and coordinate shared-file edits
   before touching them.
3. Assign bounded work sequentially to the project development agents:
   `planner` for the implementation plan, `coding` for scoped edits, then
   `testing` for verification. These are Codex development helpers, not runtime
   travel-research specialist agents.
4. The primary session integrates results, reviews changed files, preserves the
   charter's product invariants, and keeps external providers behind typed
   interfaces.
5. Update durable docs only when a checklist item is actually complete and the
   required evidence exists.
6. Run the narrowest relevant check first, then the full available checks from
   `AGENTS.md` when applicable. If checks are unavailable, report `N/A`.
7. If testing reports a specific failure, allow at most two
   coding-fix/testing-retest cycles. Stop after the second failed retest and
   report the remaining blocker.

## Commit And Push Gates

- Stage explicit files only after acceptance passes.
- Commit only when acceptance passes and the user explicitly requested a commit.
- Push only when acceptance passes, a commit exists for this work, and the user
  explicitly requested a push.
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
