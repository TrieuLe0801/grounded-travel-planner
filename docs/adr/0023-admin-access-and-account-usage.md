# ADR 0023 - Administrator Access and Account Usage

Status: Accepted for implementation; deployment pending
Date: 2026-11-14

## Context

ADR 0021 keeps Auth0 responsible for credentials and leaves account roles and
application access controls for a separate decision. ADR 0020 records redacted
model usage in LangSmith when available. The user requested an administrator
page to manage access and view each account's token usage and corresponding
cost. The user then specified LangSmith as the source for both figures.

## Decision

- Keep Auth0 Universal Login and the internal account UUID. Store application
  access (`pending`, `active`, `blocked`) and the administrator flag in the
  existing account database. Existing accounts migrate as active; new
  identities start pending. Bootstrap the first administrator from an existing
  Auth0-backed account in an explicit maintenance step. A unique existing email
  may resolve the internal UUID; the target email stays outside tracked files.
- Check active access on every private planner and archive request. A block
  revokes all application authentication sessions, discards retained volatile
  sessions for that account, and prevents new work. In-flight provider calls may
  finish, but their session result must not be collected after a block. Regrant
  keeps the same account UUID, immutable saved tours, and historical usage; the
  person signs in again. An administrator cannot block themselves or the last
  active administrator.
- Keep account access changes in a durable audit table with actor, action, and
  time. Require a verified active administrator for reads and changes, and a
  valid session CSRF token for changes. The frontend is not an authorization
  boundary.
- Attach a stable, one-way account reference to LangSmith run metadata. Derive
  it from the random internal account UUID with a domain-separated SHA-256
  digest. Never send the raw account UUID, email, credentials, prompt or response
  in custom usage metadata. Query only LLM runs carrying that reference;
  aggregate leaf model calls, not parent trace totals, to avoid double counting.
- The administrator view reads LangSmith input/output token counts and
  `total_cost` for account totals and UTC-dated model detail. LangSmith model
  pricing determines cost, including any custom price mapping needed for a
  model. A missing cost stays unknown rather than becoming zero. The label
  identifies LangSmith as the source and does not claim a provider invoice.
  Older traces without the reference, sampled-out traces, missing usage, and
  traces past retention cannot contribute to totals. A LangSmith failure is
  shown as unavailable, not as zero usage; account access controls remain
  available. Runtime tracing, a LangSmith project and a read-capable API key
  must be configured for usage reporting.
- Apply an explicit, backed-up, write-paused account-access migration for
  PostgreSQL Compose and the local SQLite fallback. No model-usage database
  table or local price configuration is required. Keep saved-tour snapshots and
  live session storage contracts unchanged.

## Alternatives Considered

- A local per-call token ledger and price catalog: superseded by the user's
  LangSmith source decision before deployment.
- A durable account-to-thread mapping: rejected because querying all historical
  thread IDs adds storage and query work without improving LangSmith coverage.

## Consequences

The account administration page expands the account controls reserved by ADR
0021. This decision does not add app-managed passwords, persist live
itineraries or chat, or create Auth0 identities on an administrator's behalf.
Provider invoices can differ from LangSmith cost because usage, pricing and
retention differ. Live Auth0, migration, browser, LangSmith query and provider
usage checks remain separate deployment gates.

## Review Triggers

Review trace retention, sampling and query volume before treating these figures
as a complete billing record or using them for quotas.
