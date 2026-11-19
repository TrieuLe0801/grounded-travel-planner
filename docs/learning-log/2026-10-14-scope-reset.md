# Learning Log — 2026-10-14 Scope Reset

This log keeps recent user decisions and operational events that help explain
current status. The [charter](../project-charter.md) and accepted ADRs are the
source of truth for product and architecture. Historical test output belongs
with its CI run or experiment artifact.

## 2026-11-19 — Itinerary and chat feedback

- The React itinerary page uses plain progress text while creating an
  itinerary. Chat progress and submission errors stay in the chat panel.
- Ordinary chat responses do not show a page-level notice. Committed or
  rejected itinerary changes from chat show a short localized status, without
  repeating the assistant's chat response.
- `npm ci --offline`, `npm run check`, `npm run build` and `git diff --check`
  passed. Browser QA did not run.

## 2026-11-17 — Authenticated view refresh

- PR #20 keeps the current React workspace view across refresh. Saved tours,
  profile and administrator views use the `view` query parameter; itinerary
  remains at `/`. The app restores private views only after checking the
  account, and non-admin accounts cannot restore the administrator view.
- The plan and conversation rehydrate from the same server session. Trip data
  is not stored in the URL, and graph inspection remains hidden.
- `npm run check`, `npm run build` and `git diff --check` passed. Browser QA,
  container recreation and deployment were not run; the active app uses another
  checkout.

## 2026-11-17 — Local Compose refresh

- Local Compose rebuilt the app from commit 34e20ba. The app and PostgreSQL
  were healthy; the local root returned HTTP 200. The Auth0 connection setting
  was present in the container, and its value was not recorded here.
- PostgreSQL was not recreated. Recreating the app cleared session-only
  itinerary, conversation and pending-turn state.
- The latest offline suite and Python/frontend checks predate this rebuild:
  246 tests passed, one optional PostgreSQL test was skipped. No tests,
  browser flow or live Auth0 request ran during the refresh.

## 2026-11-17 — Merged-account tombstone cleanup

- The user requested cleanup of a merged, non-administrator tombstone. Before
  the change, a database backup was verified and a guarded transaction was
  dry-run. The tombstone was then marked deleted and its email cleared; the
  merge mapping and audit history were retained.
- Post-check found no identities, sessions or tours on the target. The active
  administrator and their tours remained unchanged. No Auth0 request ran
  because the tombstone had no Auth0 identity.

## 2026-11-16 — Account-flow integration

- PR #16 and PR #17 were integrated with three-method identity linking,
  duplicate-account reconciliation and administrator deletion. Merged,
  deleting and deleted accounts cannot authenticate or be reactivated;
  account-owned tours and audit history are protected.
- The integrated offline suite passed 246 tests; one optional PostgreSQL test
  was skipped because its opt-in settings were unset. Python quality checks
  and frontend check/build passed. Browser account flows and live Auth0
  deletion were not exercised.

## 2026-11-15 — Account and host decisions

- The user confirmed www.citedtrip.app as the public host. ADR 0022 and the
  deployment record are authoritative for ingress and callback configuration;
  browser callback, OTP, planner and logout checks remain open.
- A user-confirmed duplicate application account was reconciled after backup
  validation and a rollback dry-run. The chosen existing account retained its
  tours; identities and access history were transferred under the guarded
  operator procedure. Runtime linking by email alone remains prohibited.
- Historical LangSmith usage is included through a persistent account alias;
  existing trace tags are not rewritten. See ADR 0023 and the implementation
  record for the account-usage behavior.

## Durable decisions

| Decision | Canonical record |
|---|---|
| City/place sightseeing scope and product invariants | [Project charter](../project-charter.md) |
| Coordinator, Planner and Chat responsibilities | [ADR 0004](../adr/0004-city-sightseeing-two-agent-runtime.md), [ADR 0009](../adr/0009-coordinator-routed-chat-agent-and-trip-extension.md) |
| Bounded session context and shared Tavily node | [ADR 0011](../adr/0011-bounded-session-context-and-chat-search.md), [ADR 0012](../adr/0012-shared-tavily-tool-node.md) |
| Saved-tour storage and account ownership | ADRs 0014–0016 and 0021 |
| Administrator access, usage and deletion | [ADR 0023](../adr/0023-admin-access-and-account-usage.md) |
| Cloudflare public ingress | [ADR 0022](../adr/0022-cloudflare-tunnel-public-ingress.md) |

The old POC remains archived. Do not treat roadmap or planning progress as
evidence that the application, a browser flow or a live provider was verified.
