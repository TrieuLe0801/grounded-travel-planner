# ADR 0020 - Runtime Token And Turn Quotas

Status: Accepted
Date: 2026-11-06

## Context

The OpenAI adapter had no per-call output-token ceiling. The HTTP API limited
parallel work and ngrok limited requests by source IP, but one authenticated
person could use multiple sessions or IPs and other ingress paths did not share
that per-IP policy. Provider token usage was not surfaced as a redacted event.

The app has no measured token-cost baseline yet. The user asked to keep actual
budget values in runtime environment configuration and out of tracked files.
The running app must read configured limits to enforce them; Codex must not
display or record their values. The former ngrok ingress policy was retired
after Cloudflare Tunnel became the public ingress.

## Decision

- Bound OpenAI completion output by role: Coordinator 2,048 tokens, Planner
  8,192 tokens, and Chat 2,048 tokens by default. Runtime environment settings
  may override each cap; Pydantic bounds each setting to 256–16,384 tokens.
  Ollama receives the same role-specific generation ceiling through
  `num_predict`.
- Limit a sightseeing plan to 28 schedule entries, supporting up to four stops
  per day across the seven-day product maximum.
- Apply a thread-safe sliding-hour quota at `POST /api/turns`. A valid Auth0
  session uses the internal account UUID; anonymous planning uses the opaque
  session thread ID. The per-principal default is 20 accepted turns per hour.
  `GTP_TURN_LIMIT_PER_HOUR` overrides that default. An optional process-wide
  ceiling is controlled by `GTP_TURN_GLOBAL_LIMIT_PER_HOUR`; a blank value
  leaves that additional ceiling disabled.
- Return HTTP 429 with `Retry-After` before scheduling or appending a rejected
  user turn. Return a reserved quota slot when the worker queue rejects work.
  Do not trust forwarded-IP headers for the principal key.
- Record OpenAI input/output token counts as a `model.usage` LangSmith event
  only when tracing is enabled and usage metadata is available. Include the
  model, role, token counts and turn ID; use the existing thread ID metadata.
  Never include prompts, completions, account IDs, cookies or API keys. Missing
  usage metadata or trace failure must not change planning behavior.
- Keep actual environment values outside tracked files. `.env.example` has
  blank placeholders; the application reads configured values at runtime.

## Alternatives Considered

- Rely only on ngrok source-IP limits: rejected because they cover only that
  ingress and do not combine activity across an authenticated account's
  sessions or IPs.
- Persist quota counters in the saved-tour database: rejected because request
  controls are operational metadata and saved tours remain an immutable,
  owner-scoped archive.
- Claim a precise dollar ceiling from token counts: rejected because usage
  records do not include a versioned price table and configured model IDs can
  change. The app does not calculate USD spend.

## Consequences

- Per-call output size and HTTP turn frequency are bounded before model work.
- The limiter is process-local. It resets on restart and each replica has its
  own counters; a multi-replica deployment needs a shared quota store or an
  equivalent centralized ingress policy.
- The optional global limit is an hourly turn count, not a dollar limit. A
  monetary OpenAI spend ceiling remains a separate provider-project setting and
  is not configured by this repository change.
- The retired ngrok per-client-IP Traffic Policy no longer applies. Authenticated
  account quotas remain enforced in the app. Custom Cloudflare WAF or rate-limit
  rules were not part of this change and have not been verified.
- Compose runtime image was rebuilt and the app container recreated. The
  container is healthy, the app root returns HTTP 200, and the configured
  process-wide quota parses in the running container. No request exercised
  HTTP 429; LangSmith usage events, Auth0 callback behavior and provider spend
  enforcement remain unverified. Recreating the app cleared session-only plans;
  the PostgreSQL container and saved tours remained intact.

## Review Triggers

- Revisit default output caps after measured role-level usage shows they can be
  safely lowered without truncating valid itineraries.
- Move request quota state to shared storage before running multiple app
  replicas.
- Add a USD meter only with a reliable price source and a separately reviewed
  persistence, reset and reservation policy.
- Add managed edge/WAF controls and close direct origin access before claiming
  DDoS mitigation for production traffic.
