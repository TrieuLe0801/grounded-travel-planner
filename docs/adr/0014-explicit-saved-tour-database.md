# ADR 0014 - Explicitly Saved Tours in SQLite

Status: Accepted
Date: 2026-10-31
Amended: 2026-11-01 for large saved-tour archives
Storage engine superseded by ADR 0015 on 2026-11-01

## Context

The user directed the app to use a database for tour suggestions they approve
for saving. The HTTP adapter currently keeps one live itinerary in memory;
reset, session expiry and process restart lose it. ADR 0008 and ADR 0011
deliberately made the itinerary and transcript session-only. A committed plan
means validation succeeded, but does not mean the user approved long-term
storage.

## Decision

- Add a separate saved-tour archive backed by SQLite on a persistent local
  Compose volume. The live canonical plan, transcript, summary, language and
  pending turn remain session-only. LangSmith is not app storage.
- Save only after an explicit user action on the current validated canonical
  plan. Store an immutable versioned snapshot, including the exact committed
  source references, estimates and verification flags. Saving does not run
  Planner, Chat or Tavily. Failed/rejected proposals and ordinary chat are not
  saved.
- Give the browser a separate long-lived random HttpOnly owner credential.
  Store only its hash in SQLite. Scope all archive reads and writes by that
  owner. This supports revisiting tours from the same browser after the live
  session expires or the app restarts. It does not provide accounts, recovery
  after cookie loss, or cross-device access.
- Repeated saves of the same `plan_id` and revision for an owner return the
  existing saved record. Show saved tours read-only, with save time and a
  notice that source facts may be stale. Provide owner-scoped deletion.
- Design the saved-tour archive for more than two million rows on one host.
  Keep list reads bounded and owner-scoped, sorted by `(saved_at DESC, id DESC)`
  with an opaque keyset cursor. A composite index on
  `(owner_hash, saved_at DESC, id DESC)` matches that filter and order. Fetch
  list metadata without loading plan snapshots; fetch one snapshot for detail.
  Retain the unique `(owner_hash, plan_id, revision)` constraint for idempotent
  saves. No count query runs on each list request.
- Create the new index directly for a fresh archive. An existing archive must
  be migrated explicitly, after backup and during a write pause, because
  building an index over millions of rows can take time and disk space. The
  application must not perform that rebuild implicitly at startup. Preserve
  snapshot bytes and IDs during migration.
- Keep this decision limited to saved tours. Search-history persistence and
  restoring a saved tour as the live editable plan require separate decisions.

## Alternatives Considered

- Browser-only storage: cannot reliably survive browser-data loss or provide a
  server-owned archive with access checks.
- Database with user accounts: supports multiple devices and recovery but adds
  identity, account lifecycle and retention scope that was not requested.
- Persist every successful commit automatically: a validated proposal is not
  the user's approval to save it.
- Save raw Tavily results or transcripts: unnecessary for viewing accepted
  plans and expands personal-data retention.

## Consequences

- The app needs a writable durable volume and database initialization in its
  deployment. A plain unconfigured single-process run can use a local ignored
  database path.
- A browser owner cookie is a bearer credential. Its loss loses access; its
  disclosure grants access. HTTPS deployment must protect it with a Secure
  cookie and access to the database and backups must be restricted.
- Saved snapshots preserve evidence as it was at save time, not fresh facts.
  Viewing them must not claim current opening hours or other current details.
- Keyset pagination remains stable when new rows are inserted ahead of the
  current page; deletion can reduce a subsequent page. The cursor represents
  an ordering position, not a permanent snapshot of the whole archive.
- SQLite remains a single-host database with serialized writes. Reassess the
  engine if measurements show sustained writer contention or if app replicas
  need coordinated writes. Row count alone does not require that change.
- The React interface provides save/list/detail/delete. Streamlit continues as
  the migration fallback but does not expose the new archive in this slice.

## Review Triggers

- Users need account-based access, cross-device sync or cookie-loss recovery.
- The app moves beyond a single-host SQLite deployment or needs multi-instance
  writes.
- Measured list latency, storage growth or write contention become unsuitable
  at representative archive size, snapshot size and owner skew.
- The product adds search history, restore/edit, export or a retention period.

## Supersedes

ADR 0008 and ADR 0011 are amended only for explicitly saved tour snapshots.
Their session-only live-plan, transcript, summary and turn behavior remain
accepted.
