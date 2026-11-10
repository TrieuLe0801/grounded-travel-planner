---
name: travel-planner-security-review
description: Review security boundaries in Grounded Travel Planner using project contracts and source evidence. Use for explicit security review or audit work, not routine feature implementation.
---

# Grounded Travel Planner Security Review

Use for a user-requested security review or a manager-assigned focused review.
Read `AGENTS.md`, the active charter and only the accepted ADRs relevant to the
changed boundary. Work from this repository's code and contracts.

## Review method

1. Set scope. Name the actor, account/session, protected data or action, entry
   point, expected control and observable effect.
2. Trace input through authorization, validation, state/storage/provider use,
   and the output or side effect. Check alternate paths to the same effect.
3. Report a finding only when source and a safe local observation show a
   reachable control failure and concrete impact. Separate confirmed findings,
   unresolved checks and disproved candidates. A missing best practice alone is
   not a vulnerability.
4. Use deterministic local evidence. Mock Auth0, model, Tavily, LangSmith and
   external services. Do not inspect secrets, call live providers, modify shared
   data, or claim deployment behavior from source alone.
5. Report affected paths, principal, violated control, impact, evidence and the
   smallest useful fix. State what was not checked.

For broader reviews, prioritize correctness and data safety, security, expected
load, risky logic without a focused check, material performance, then provably
unnecessary duplication. Do not report style preferences or hypothetical risks
as findings.

## Project boundaries

- Auth0 owns credentials. FastAPI validates identity and owns opaque account
  sessions. Private planner APIs require authentication and bind live sessions
  to the internal account UUID. Email is display data, not an owner key.
- Keep session cookies secure by default and preserve CSRF checks for protected
  mutations. Do not trust forwarded client identity headers for authorization
  or quota principals.
- Live itinerary, transcript, locale and pending work stay in the owning
  session. Only an explicit save creates a durable snapshot.
- Saved tours are immutable and owner-scoped. Compose uses PostgreSQL; SQLite is
  the local fallback. Check query owner scope, bounded keyset pagination and
  that archive reads do not invoke providers or mutate live plans.
- User text, model output and search results are untrusted. Verify deterministic
  input, schedule and source-reference checks before plan commit. Sources must
  come from provider results; do not invent URLs or restore the disabled
  `source_place_mismatch` gate.
- Keep prompts and traces free of credentials, cookies, raw private context and
  secrets. Preserve turn, token, search and graph execution bounds.
- Treat container, deployment, browser and live-provider behavior as unverified
  until each is checked in its actual target environment.
