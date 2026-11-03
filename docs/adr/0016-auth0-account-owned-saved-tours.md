# ADR 0016 - Auth0 Accounts for Saved Tours

Status: Accepted for implementation; deployment pending
Date: 2026-11-03

## Context

The PostgreSQL saved-tour archive is scoped to a long-lived browser cookie.
The user selected Auth0 email OTP so a verified person can reach the same
saved tours across browsers. The live itinerary, transcript, language and
pending turn must remain in their existing session.

## Decision

- Use Auth0 Universal Login with its email passwordless connection. FastAPI
  runs Authorization Code with state, nonce and PKCE, validates the signed ID
  token, and maps the stable issuer and subject to an internal UUID. Email is
  display data, not an owner key.
- FastAPI issues an opaque, `HttpOnly`, `Secure`, `SameSite=Lax` account cookie.
  PostgreSQL stores its verifier hash, account UUID, CSRF hash, expiry and
  revocation state. Idle expiry is 30 minutes and absolute expiry is 30 days.
  Archive writes and logout require a session-bound CSRF token. Logout revokes
  the app session, then sends the browser to Auth0's logout endpoint using a
  configured fixed return origin. Provider tokens do not reach the browser or
  the itinerary runtime.
- Anonymous planning remains available. Saved-tour save, list, detail, delete
  and claim require a verified account. Every archive query uses the internal
  account UUID. Missing authentication returns 401; another account's tour ID
  returns 404. Explicit save, immutable snapshot content, and keyset paging
  remain as before.
- Add account tables and nullable `owner_user_id` through an explicit,
  write-paused migration after a tested backup. Keep legacy `owner_hash` and
  unclaimed rows. A user can claim older rows only with the original browser
  cookie and an authenticated account session. Conflicting plan revisions
  remain intact and receive an explicit conflict report. The legacy cookie
  cannot read a claimed row.
- Keep SQLite for local tests and fallback. Compose uses its existing
  PostgreSQL archive for accounts, auth sessions and saved tours. No failure
  changes the app to another writable backend. PostgreSQL RLS remains a
  separate defense layer after application owner checks are verified.

## Consequences

Auth0 tenant settings, exact callback/logout URLs, production email delivery,
and a fixed public origin are required for live login. Account login does not
restore the live itinerary. The current running app stays on the prior
browser-cookie behavior until the database migration and application rollout.
The old-cookie claim window and account deletion/export policy need a separate
decision before public deployment.

## Supersedes

This ADR supersedes ADR 0014 and ADR 0015 only where they limit saved-tour
ownership to one browser or exclude accounts. Their snapshot, explicit-save,
storage and session-only live-state decisions remain accepted.
