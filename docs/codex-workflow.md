# Portable Codex development workflow

This repository keeps its Codex development workflow in Git:

| Path | Purpose |
|---|---|
| `AGENTS.md` | Project rules and required reading |
| `.codex/config.toml` | Agent concurrency; models inherit from the session |
| `.codex/agents/*.toml` | Researcher, planner, coordinator, tester, and deployer roles |
| `.codex/skills/*/SKILL.md` | Delivery, requirement clarification, UI, browser-evaluation, and security-review guidance |
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
4. Check that Codex discovers all five agents and the five project skills.
   Follow `AGENTS.md` for this repository's active workflow.

Browser checks use Playwright from `frontend/`: run
`npx playwright install chromium` once, then `npm run test:browser`. The local
test suite mocks the authentication boundary and runs desktop and mobile
Chromium. CI runs the same mocked suite. Tester uses the project browser
evaluation skill for browser acceptance and reports live flows separately.

Personal skills in `~/.agents/skills/` or `~/.codex/skills/`, including
`caveman`, are not part of this repository. Install them separately on the
other machine if wanted. Plugin-provided skills require the plugin there.
Personal instructions such as an absolute `~/.codex/RTK.md` reference also
need separate setup; they are not repository files.

## Another repository

Inspect both source and destination before copying. If the destination is not
supplied, finish the source inventory and request its path before transfer.
Inventory `AGENTS.md`, `.codex/config.toml`, agents, hooks and skills separately
from personal or plugin installations. Copy `.codex/agents/` and selected
project-authored skills only after adapting their product rules. Copy
`.codex/config.toml` after checking concurrency needs. Development models
inherit from the signed-in Codex session.
Rewrite `AGENTS.md` from the destination's actual decisions. Copy the hook
only for a compatible Python project with its formatting tools installed.
Remove travel-planner product rules, source paths, and verification commands
that do not apply. Preserve role responsibilities, but rewrite paths, model
choices and gates against the destination. Validate skill manifests, parse
agent/config TOML, inspect hook commands, check tracked files and ignored
secrets, and run the destination's relevant checks. Confirm model inheritance
or availability. Report what transferred, what changed and what remains
machine-local. Commit only when requested.

## Skill checks

Use the available skill manifest validator for each changed skill. Routine code
verification belongs to Tester and `AGENTS.md`, so this repository has no
separate project-change-verification skill. Transfer guidance is maintained
here rather than exposed as a separate skill. Record commands, results and
limits with the change.

## Skill and UI/UX review — 2026-11-20

The user requested a project reread, skill cleanup and selective learning from
[Hallmark](https://github.com/nutlope/hallmark). Its
[UI guidance](https://github.com/nutlope/hallmark/blob/main/skills/hallmark/SKILL.md)
was reviewed as reference material, not installed or copied.

| Area | Existing project evidence | Decision |
|---|---|---|
| Delivery | Five roles and ordered handoffs | Retain delivery skill and roles; Planner owns design, Coordinator implementation, Tester independent review. |
| UI | MASTER.md, landing spec, React tokens, real sources, bilingual copy and local SVG guide | Extend the existing UI skill with a scoped brief and interaction inventory. |
| Browser | Playwright fixtures and responsive checks | Retain browser skill; compare matching before/after states and exercise preserved actions. |
| Security | Auth0, CSRF and owner-scoped storage contracts | Retain explicit security-review skill; frequency alone does not remove a distinct safety responsibility. |
| Transfer | Setup instructions already maintained in this document | Remove the separate transfer skill and manifest; preserve its procedure here. |

No skill invocation telemetry is available. This cleanup is based on overlap
and current responsibilities, not a measured ranking of seldom-used skills.
Personal and plugin installations are outside this repository change.

Useful additions from the comparison are explicit audit/polish/redesign scope,
interaction preservation, and review that distinguishes contract failures from
reasoned design choices and optional finishing work. Existing accessibility,
real-content and browser guidance already covers much of the need.

Do not adopt Hallmark's theme selection, scripts, CSS stamps, rigid word limits,
blanket overflow clipping or illustration prohibition. The current Tailwind
system, local guide SVGs and data-rich itinerary govern those choices. No new
UI framework, image library, package or designer role is required.

## Engineering skill review — 2026-11-21

The user asked to review [mattpocock/skills](https://github.com/mattpocock/skills)
and update project skills and agents. We compared its bug diagnosis, code
review, and agent-writing guidance with the existing five roles and four
project skills. The delivery skill and Coordinator now require a focused,
observable failure before asserting a defect's cause. Tester checks that a
regression exercises the reported symptom and reviews the diff separately for
Goal Card fit and project-contract compliance. Researcher compares external
ideas with local gaps before recommending them. No external skill bundle or
issue-tracker setup was installed; existing project roles and gates remain.

## Requirements interview — 2026-11-21

After reviewing [grill-me](https://github.com/mattpocock/skills/blob/main/skills/productivity/grill-me/SKILL.md)
and [grilling](https://github.com/mattpocock/skills/blob/main/skills/productivity/grilling/SKILL.md),
the user requested a project skill for agents to clarify requirements. The new
`requirement-clarification` skill has a focused mode for blocking user decisions
and a deep-interview mode for an explicit request to explore design branches.
Researcher finds evidence before raising questions; Planner identifies remaining
decision dependencies; the primary session asks and records answers. This keeps
routine authorized work moving and avoids re-asking settled decisions. No
external skill file or runtime agent was adopted.

## Proposal interview handoff — 2026-11-23

Research and proposal work now includes a decision check before a recommendation
is presented. Researcher identifies unresolved product tradeoffs after reading
project evidence. The primary session interviews the user and passes answers to
Planner. Planner checks for new decision dependencies and sends any remaining
questions back to the primary session before finalizing a dependent plan.
Proposal-only work ends after this handoff and plan; implementation roles run
when a code change is in scope. The latency and 14-day trip proposal prompted
this clarification after its first draft omitted the interview.
