# ADR 0015 - PostgreSQL Container for Saved Tours

Status: Accepted
Date: 2026-11-01

Account ownership and persistent auth sessions are added by ADR 0016 for the
next rollout. The current running PostgreSQL schema has not been migrated.

Amendment, 2026-11-01: The user directed PostgreSQL data into a separate host
directory outside the Git repository. The Compose database now bind-mounts
`${GTP_DATA_DIR:-../grounded-travel-planner-data}/postgres` instead of using the
`postgres-data` named volume. The former volume remains intact for recovery.

## Context

The user directed the project to run its database as a container in Docker
Compose. ADR 0014 selected SQLite for the explicitly saved tour archive. SQLite
is embedded in the app process and therefore cannot satisfy the new container
boundary. The current Compose volume holds a saved tour that must remain
accessible after the switch.

## Decision

- Run PostgreSQL 17 as a separate Compose service with a host data directory and
  health check. The app waits for database readiness. Do not publish the
  database port to the host.
- Store explicitly saved tour snapshots in PostgreSQL for the Compose app.
  Keep the existing API, browser owner credential, immutable snapshot data,
  idempotent owner/plan/revision key, and bounded keyset list contract. The
  current itinerary, transcript, summary and pending turn remain session-only.
- Keep the snapshot JSON as text so migration can retain its exact contents.
  Keep an owner/time/ID composite index for list queries. Use parameterized
  statements and a bounded connection pool.
- Keep SQLite support for local offline tests and as a migration source. Stop
  app writes, back up SQLite, copy records to PostgreSQL with their IDs, owner
  hashes, timestamps and snapshot bytes, verify the result, then switch the
  app. Retain the old SQLite volume through the recovery period. Do not
  silently import or overwrite data during ordinary app startup.
- Store the PostgreSQL password only in an ignored local environment file.
  Compose supplies it to the database and app containers. Keep the host data
  directory outside the repository. Back it up regularly; a bind mount alone
  does not protect against host loss.

## Consequences

- Compose now needs a healthy database container before the app starts.
  Database restart and app restart may clear the app's in-memory trip sessions,
  but saved tours remain in PostgreSQL.
- The app must surface database connection or schema failures without falling
  back to a second writable archive. This prevents divergent saved-tour data.
- The old SQLite volume remains available for rollback until a separate,
  explicit cleanup decision.
- The former PostgreSQL named volume remains available for rollback. Do not
  mount it and the host directory into two writable database containers at once.
- Search-history persistence, accounts, and cross-device identity remain
  outside this decision.

## Supersedes

ADR 0014's SQLite engine and Compose-volume choice for saved tours. Its
explicit-save, owner scope, immutable snapshot, and list behavior remain in
force.
