---
name: evaluation-and-test
description: Evaluate and test assigned changes to this repository's development or runtime agents with deterministic evidence, focused regression coverage, and security boundary checks when relevant. Use for testing-agent assignments and agent behavior evaluations; a full security audit requires an explicit audit request.
---

# Evaluation and Test

Use this skill for a bounded assignment to the project `testing` development agent. Read the repository `AGENTS.md` and its required records first. Preserve existing dirty work and the assigned file scope. The development agent is distinct from the runtime Coordinator, Planner, and Chat agents.

## Plan the evaluation

1. Turn the assigned behavior and user corrections into observable pass/fail criteria. Record the source revision or dirty state, affected paths, fixture inputs, and relevant trust boundaries.
2. Make a small coverage list of behavior × boundary × test surface. Include ordinary success, rejection/failure, and a cross-boundary case only when the changed behavior reaches that boundary. Mark each item `tested`, `blocked`, `deferred`, or `out_of_scope`, with its evidence or exact gap. Prior passing tests are context, not current coverage when the relevant source changed.
3. Choose the narrowest useful check first. Add a regression test when it proves a missing behavioral contract. Keep automated tests deterministic and offline: mock model, Tavily, LangSmith, and other external providers. Run broader project gates only when relevant to the assignment.
4. Compare the observed output and state with the acceptance criteria. Inspect the actual command exit status and failure details; do not infer a pass from a test name, a green static check, or an earlier run.

## Security-sensitive agent behavior

When an assignment touches untrusted user text, search results, model output, memory, tools, provider fallback, or session state, use [references/agent-security-evaluation.md](references/agent-security-evaluation.md). This is focused test guidance, not authorization to run a repository-wide security audit.

Adapted from Cloudflare's [security-audit skill](https://github.com/cloudflare/security-audit-skill): map trust boundaries before testing; require a concrete boundary and observable result for a security claim; have a fresh reviewer try to disprove a consequential candidate when independent delegation is available; and keep confirmed, unresolved, and disproved security candidates distinct. Do not treat a persuasive prompt injection, missing best practice, or defense-in-depth gap alone as a vulnerability.

## Evidence and handoff

Report the exact commands and outcomes, tests added or changed, coverage and unrun checks, reproducible failures, and the relevant source/fixture paths. Distinguish static, offline, browser, container, and live-provider evidence. A security candidate is `confirmed` only when current source and a bounded local result establish the boundary failure; otherwise record the exact unresolved fact as `needs_validation` or the contrary evidence as `rejected`. Assign severity only to a confirmed security finding with demonstrated impact. Do not turn a blocked check into a pass.

Do not invoke live providers, deployed endpoints, paid APIs, or shared infrastructure as part of automated tests. Any separately authorized live check must use the agreed environment and be reported separately from offline results. Do not change application code unless the assignment includes a specific fix.
