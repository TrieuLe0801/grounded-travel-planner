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

## User Amendment — 2026-11-24 — Remember Login

The public sign-in card offers an unchecked “Remember login” option for Google,
database password, email OTP, and signup. Without the option, the account cookie
is a browser-session cookie and the server retains the 30-minute idle limit.
With the option, the account cookie persists for up to 30 days and the server
session expires 30 days after the verified callback, regardless of activity.
The choice travels only in signed, short-lived OIDC state and the server-owned
session record. Existing sessions default to the 30-minute idle policy after
the explicit database migration. Logout, administrator revocation, CSRF, owner
checks and recent-authentication requirements still apply. Remembering an
account does not persist the live itinerary or conversation.

## User Amendment — 2026-11-24 — No Fixed Remember-Login Deadline

The user selected remembered account sessions without a fixed server expiry.
New opted-in sessions keep the server-side expiry fields at the maximum signed
64-bit value; existing remembered sessions retain their original 30-day limit.
Ordinary sessions still expire after 30 minutes of inactivity. The app refreshes
the persistent account cookie after a successful `/api/auth/me` check on entry,
focus, or a 24-hour heartbeat while the authenticated tab is visible. Each
refresh sets a 400-day `Max-Age`; Chrome caps persistent cookies at 400 days
([Chrome Developers](https://developer.chrome.com/blog/cookie-max-age-expires)).
Browser cookie limits, cookie deletion, or a long absence can still require a
new sign-in; the product must not promise literal permanent access. Logout,
administrator revocation, CSRF, owner checks and recent-authentication
requirements remain in force. A stolen remembered cookie
can remain usable until revoked, so this choice increases credential exposure.
No additional schema migration is needed beyond the pending remember-login
flag migration. Live itinerary and conversation state remain session-only.
