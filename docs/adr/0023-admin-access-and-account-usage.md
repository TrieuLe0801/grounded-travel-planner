# ADR 0023 - Administrator Access and Account Usage

Status: Accepted; Compose deployed, browser QA pending
Date: 2026-11-14

User amendment — 2026-11-15: Administrator approval is no longer required for
new accounts or SSO. New verified Auth0 identities start active. An existing
pending identity becomes active on its next verified login; this transition is
audited. Blocked accounts remain blocked. The admin page retains block and
regrant controls and LangSmith usage reporting.

User amendment — 2026-11-15: Existing registered users can link a newly
authenticated Google identity to their existing account without administrator
approval. The original account UUID, saved-tour ownership, access status and
administrator flag remain authoritative. Matching email alone never transfers
an account or grants its administrator role; a conflicting Google account with
data or other identities needs separate resolution.

User amendment — 2026-11-15: After a user-confirmed duplicate account merge,
retain an explicit former-UUID-to-canonical-UUID usage alias in the account
database. Administrator usage queries include both LangSmith `account_ref`
values and group the returned model runs under the canonical account. LangSmith
remains the source of token and cost data; existing trace metadata is not
rewritten. Never infer a usage alias from a matching email. Add the alias only
after verifying the exact merge and backing up the database.

User amendment — 2026-11-16: An active administrator may delete another
application account from the admin page. Require session CSRF, a confirmation,
and server-side Auth0 Management API credentials granted only `delete:users`.
Delete every stored Auth0 identity subject, including the original profile ID;
do not select by email. Reject self-deletion and preserve at least one active
administrator. Auth0 failure leaves local records unchanged. After Auth0
success, revoke app sessions and expose a retryable `deleting` state until
owner-scoped saved tours are removed. Then remove identity and usage-alias rows,
scrub account email/admin status, and retain a `deleted` tombstone with its
access audit events. Deletion does not erase historical LangSmith traces.

## Context

ADR 0021 keeps Auth0 responsible for credentials and leaves account roles and
application access controls for a separate decision. ADR 0020 records redacted
model usage in LangSmith when available. The user requested an administrator
page to manage access and view each account's token usage and corresponding
cost. The user then specified LangSmith as the source for both figures.

## Decision

- Keep Auth0 Universal Login and the internal account UUID. Store application
  access (`pending`, `active`, `blocked`, `deleting`, `deleted`) and the
  administrator flag in the existing account database. Existing accounts
  migrate as active; new verified identities start active. Bootstrap the first
  administrator from an existing Auth0-backed account in an explicit
  maintenance step. A unique existing email may resolve the internal UUID; the
  target email stays outside tracked files.
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
