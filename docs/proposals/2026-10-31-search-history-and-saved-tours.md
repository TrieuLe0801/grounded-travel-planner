# Proposal: Search History and Saved Tours

Status: Search-history and account options remain research; saved-tour storage
is accepted under ADR 0014

Date: 2026-10-31

## Goal and current boundary

The user wants to retain their search history and revisit tour suggestions they
have accepted. Today `WebSession` holds one current plan, a bounded transcript
and a summary in process memory. The server discards idle sessions after one
hour, even if a browser retains its cookie. Reset and process restart also
lose that data. The charter and ADR 0008/0011 explicitly exclude durable
database state and accounts. This proposal therefore requires a new accepted
ADR and a charter amendment before implementation becomes active scope.

## Meaning of the two collections

| Collection | Record | When written | What the user can do |
|---|---|---|---|
| Search history | One structured, user-initiated trip request: destination, start date, day count, submitted time and outcome | Once an explicit create-trip request has valid input; update its outcome when the turn completes | Review and repeat the request |
| Saved tours | An immutable snapshot of the canonical, validated `SightseeingPlan`, with its source references, revision, save time and optional title | Only after a committed plan is visible and the user explicitly chooses **Lưu tour / Save tour** | List, inspect, delete or copy it into the current session |

The term *search history* means the user's trip searches, not Tavily's internal
queries. Record an unsuccessful validated trip search as failed, without a tour
snapshot, so the user can retry it. Do not store incomplete inputs, ordinary
chat, every Tavily call, full transcripts or rolling summaries as search
history. A search record and a saved tour may refer to the same trip, but they
are separate records: a successful search is not itself user acceptance.

`committed=True` means the application accepted a validated candidate. It is
not evidence that the user accepted or saved the suggestion. Only the explicit
save action creates a saved tour. Planner candidates, rejected edits and Chat
search citations cannot be saved as accepted tours. A plan revision can be
saved more than once only through another explicit action; the UI should make
duplicates visible or offer a clear replacement choice.

## Options

| Option | Advantages | Limits | Fit |
|---|---|---|---|
| Browser storage | Small initial backend change | Data stays on one browser, can be cleared, and same-origin scripts can read it; weak ownership and recovery | Prototype only |
| Server database with a persistent anonymous browser credential | Survives process restart on one browser | Losing the credential loses access; possession of it is ownership; no reliable cross-device recovery | Only if product explicitly chooses “this browser” history |
| Server database with authenticated user identity | History follows the person across sessions and devices; owner checks can be tested | Requires sign-in, account lifecycle and data-retention work | Recommended for “my saved tours” |

For a single-host local pilot, SQLite on a persistent host volume is a small
database option. Its WAL mode permits concurrent readers with a writer but
requires database users to share the same host. For multi-instance deployment,
use PostgreSQL. PostgreSQL can also enforce per-owner row access through row
security policies; application queries must still scope by authenticated
owner. Neither database choice alone establishes user identity.

## Recommended design, subject to product decision

1. Keep the current bounded session as the sole live plan and conversation.
   Add a separate typed archive repository behind the FastAPI adapter. The
   LangGraph nodes and `tavily_tool` do not read or write the archive.
2. Resolve a trusted `owner_id` at the HTTP boundary after authentication.
   Every list, read, save and delete operation is owner scoped. Treat an ID
   belonging to someone else as not found. Never use a user-supplied owner ID.
3. Store search history as structured request metadata, outcome and timestamps.
   Allocate one turn/search ID at submission so a repeated completion poll
   cannot duplicate the record. A completed result updates the existing record
   exactly once.
4. Save a deep copy of the visible canonical plan at its current `plan_id` and
   `revision`. Serialize the whole typed `SightseeingPlan` with a schema version,
   while indexing owner, destination and save time for lists. Keep source URLs,
   titles, estimates and verification flags exactly as committed. Do not store
   raw provider responses, prompts, credentials or LangSmith trace IDs.
5. Show the saved tour read-only, with its save time and a notice that hours,
   prices and other source facts may have changed. Opening a saved tour never
   silently makes it the active plan or claims fresh verification. “Use as
   current trip” copies it into a new session plan through a separate, bounded
   flow and requires a fresh validation policy before further edits. The copy
   cannot resume old pending work or transcript.
6. Provide a **Lịch sử / History** view with separate **Tìm kiếm / Searches**
   and **Tour đã lưu / Saved tours** tabs in Vietnamese and English. A search
   row offers “Search again”; a saved tour row opens its read-only details.
   Deletion is explicit and owner scoped. Keep the existing language preference
   independent of stored text and plan state.

Minimal logical data model:

```text
trip_searches(id, owner_id, destination, start_date, day_count,
              submitted_at, completed_at, outcome, saved_tour_id?)
saved_tours(id, owner_id, title?, plan_snapshot_json, schema_version,
            plan_id, revision, destination, start_date, day_count, saved_at)
```

Index both collections by `(owner_id, submitted_at DESC)` or
`(owner_id, saved_at DESC)` respectively. Bound page size, number of retained
records and snapshot size. Keep record deletion and any retention period in a
product policy rather than silently retaining searches forever. Restore and
deserialization must handle older schema versions explicitly.

## Implementation slices and acceptance

1. Decide identity scope (one browser or cross-device), retention, deletion and
   whether a saved tour may be restored into an editable current trip. Accept a
   new ADR and amend the charter, implementation plan and progress records.
2. Add the typed repository, migration and owner-scoped API. Keep archive writes
   outside background workers. Ensure a database failure does not turn a
   rejected candidate into a committed plan or corrupt the active session.
3. Add history and save/detail/delete UI with Vietnamese/English labels.
   Streamlit migration behavior must be decided explicitly; the JavaScript
   frontend remains the primary new UI under ADR 0008.
4. Verify offline that submission/poll retries do not duplicate searches, only
   an explicit save of a committed current revision creates a tour, sources
   remain unchanged, two owners cannot access each other's records, and an
   owner can revisit records after session expiry/restart. Verify no model or
   Tavily call occurs while listing saved tours. Run the repository's full
   Python checks and frontend build; run a database-backed Compose smoke before
   claiming persistent operation.

## Risks and decisions still needed

- **Identity:** the existing one-hour anonymous session cookie is not a
  durable account. If users must see tours on another device, choose an
  authentication approach before implementation. A persistent anonymous
  credential provides only browser-bound access and needs explicit recovery
  expectations.
- **Privacy:** trip destinations and dates are personal data. Specify a
  retention period, delete/export behavior, backups and access to archives.
  Use HTTPS and secure session cookies for deployed account access.
- **Staleness:** a saved snapshot preserves what was grounded at save time.
  Reopening it must not imply that opening hours or other facts are still
  verified. Any refresh needs a new bounded research and validation turn.
- **Scope:** current accepted decisions intentionally keep the runtime
  session-only. This research does not itself change those decisions or claim
  that persistence is implemented.

## References

- Existing project behavior: `src/grounded_travel_planner/web/api.py`,
  `src/grounded_travel_planner/contracts.py`, ADR 0004, ADR 0008 and ADR 0011.
- SQLite, [Write-Ahead Logging](https://www.sqlite.org/wal.html): reader/writer
  behavior and same-host constraint.
- PostgreSQL, [Row Security Policies](https://www.postgresql.org/docs/current/ddl-rowsecurity.html):
  owner-based access controls available to a multi-user deployment.
- OWASP, [Session Management Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Session_Management_Cheat_Sheet.html):
  session token protection and the limits of browser-held credentials.
