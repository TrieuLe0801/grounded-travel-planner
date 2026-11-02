# Plan: account-owned saved tours with Auth0

Status: Auth0 selected by user for later implementation on Mac; no code deployed.
Date: 2026-11-02

## Goal and selected provider

Users sign in with an email one-time code, with no separate registration screen. A
verified first sign-in creates an account. The same account sees its saved tours
in Chrome, Edge, or another browser; a different account cannot list, read, or
delete them. Keep the existing PostgreSQL 17 Compose database as the archive.
Use **Auth0** as the OIDC identity service and its Universal Login email OTP
flow. Auth0 creates a passwordless user profile after the first verified OTP;
the app creates or finds its own internal user record after validating the
Auth0 identity. No separate registration screen or password database is
needed. Check the Auth0 tenant's current feature limits and email delivery
before deployment. [Auth0 OIDC][auth0-oidc] [Auth0 passwordless][auth0-otp]

This proposal **would change** the same-browser-only decision in ADR 0014 and
the cross-device non-goal in the charter. The provider choice is recorded in
the current learning log; update those records and add an auth ADR as part of
the later implementation. No current product behavior changes through this
document.

## Current boundary and intended boundary

- Today, `web/api.py` creates `gtp_saved_tours_owner` on explicit save. The
  archive stores its SHA-256 hash; list/detail/delete filter by that hash.
  Chrome and Edge have separate cookies. Compose selects PostgreSQL through
  `GTP_SAVED_TOURS_BACKEND=postgres`; local SQLite remains a test/fallback path.
- Preserve explicit save, validated immutable snapshots, exact source data,
  keyset pagination, read-only archive detail, and session-only live
  itinerary/transcript. Authentication does not put live plans in the database.
- After cutover, FastAPI resolves a server-authenticated `user_id` for every
  archive operation. Never accept owner ID, email, or provider subject from a
  request body or query parameter. No anonymous tour save after cutover.
- Keep credentials out of React storage and LangSmith traces. FastAPI handles
  auth and issues a separate opaque, persistent auth-session cookie. Store only
  a verifier hash, user ID, expiry, and revocation state in PostgreSQL. Keep
  `gtp_session` independent: changing login state must not reset an in-flight
  trip turn or language choice. Use `Secure`, `HttpOnly`, `SameSite`, and HTTPS;
  protect state-changing endpoints against CSRF and rotate the session on
  sign-in. A backend-held token pattern keeps provider tokens out of browser
  storage. [RFC 10017][browser-oauth] [OWASP sessions][owasp-session]

## Application and database work

1. **Schema and migration.** Back up the Compose database with a tested
   restore path. Add `app_users` (internal UUID), `auth_identities` (unique
   provider + issuer + subject, linked to user), `auth_sessions`, and nullable
   `saved_tours.owner_user_id`. Keep `owner_hash` during migration. Add the
   `(owner_user_id, saved_at DESC, id DESC)` list index. Define account-level
   idempotency for `plan_id` + revision. Do not build a large index silently at
   startup; use an explicit migration during a controlled write pause. Preserve
   tour IDs, timestamps, and exact `plan_snapshot` text. Do not key accounts by
   email: the stable OIDC identity is issuer + subject. [OIDC Core][oidc]
2. **Auth boundary.** Add a small typed Auth0/OIDC adapter for verified identity
   and sign-in operations. Add `GET /api/auth/me`, login, callback, and logout
   routes. Server auth sessions survive app container recreation; provider
   access/refresh tokens, if needed, stay server-side and encrypted.
   Set bounded idle/absolute expiry and revocation behavior before launch.
3. **Archive API.** Make save/list/detail/delete require auth. Filter every
   query by `owner_user_id`; other users' tour IDs return 404, missing auth
   returns 401. Retain the bounded cursor and list limit. Do not call model,
   Tavily, or LangSmith from archive endpoints. Apply the same owner check in
   SQLite tests and PostgreSQL runtime; never fall back to another writable
   database on auth or storage failure. Deny by default and check every
   request. [OWASP authorization][owasp-authz]
4. **Database defense.** Evaluate PostgreSQL Row Level Security after the
   application owner filter passes. If enabled, use a dedicated runtime role
   without `BYPASSRLS`, set verified user context transaction-locally, and test
   pool reuse. Table owners normally bypass RLS unless forced, so a policy
   alone is not evidence of isolation. [PostgreSQL 17 RLS][postgres-rls]
5. **React UI.** Add Vietnamese and English sign-in, sign-out, pending, and
   error states. Auth0 Universal Login owns OTP entry, expiration, and retry
   screens. Prompt sign-in when saving or opening saved tours; allow anonymous
   trip planning. After sign-in, refetch tours from API. Never persist user
   IDs, OTPs, or provider tokens in `localStorage`/`sessionStorage`.

## Auth0 setup and OIDC flow

1. Create an Auth0 tenant and **Regular Web Application**. Enable the Email
   passwordless connection for this application and use Universal Login with
   an Identifier First authentication profile. If other connections are also
   enabled, pass `connection=email` to `/authorize` so email OTP is selected.
   Configure the exact callback and logout URLs for Mac development and later
   HTTPS deployment. Keep local callback URLs out of production settings.
   Configure a production email provider before public use; Auth0's built-in
   sender is for testing. [Auth0 passwordless][auth0-otp]
   [Universal Login][auth0-universal-login]
   For Mac development, use a dedicated Auth0 development application and an
   exact loopback callback such as `http://localhost:8503/api/auth/callback`
   only if the app is served from that origin. Match scheme, host, port, path,
   and trailing slash in Auth0 settings. Production must use HTTPS and a
   separate application configuration. [Auth0 callback matching][auth0-callback]
2. FastAPI initiates Authorization Code flow with state, nonce, and PKCE;
   callback exchanges the code server-side and validates the ID token's
   signature, issuer, audience, expiry, and nonce. Map issuer + subject to
   `app_users`, then issue the app's own opaque auth-session cookie. Keep
   provider tokens off React. This follows the backend-for-frontend pattern
   for a browser app. [RFC 10017][browser-oauth] [OIDC Core][oidc]
3. Keep the provider login page responsible for OTP request/entry. React needs
   only sign-in redirect, current-user, logout, and error states. Use separate
   development and production application settings so a local callback cannot
   be accidentally enabled in production. Validate exact callback matching,
   logout return URL, sign-out behavior, and tenant feature limits on Mac.

## Claiming existing cookie-owned tours

1. Keep the old `gtp_saved_tours_owner` cookie readable only for a dedicated
   claim flow during a defined migration window. The user must have both a
   verified account session and the original browser cookie. Never claim by
   matching email, destination, title, or tour ID alone.
2. `POST /api/saved-tours/claim` computes the legacy owner hash server-side,
   locks matching unclaimed rows, assigns `owner_user_id` in one transaction,
   and returns counts. Repeated claims are idempotent. If a row conflicts with
   the account's `plan_id` + revision, preserve both snapshots and stop with an
   explicit conflict report; define a lossless resolution before enforcing a
   unique account key. Do not silently discard a snapshot.
3. A claimed row becomes accessible only through the authenticated account.
   The legacy cookie alone must no longer grant access to it. Keep unclaimed
   rows and the backup until the migration/recovery policy is decided. Users
   who lost the original cookie cannot prove ownership through this flow.

## Mac implementation and acceptance sequence

1. On Mac, check out the branch and verify Docker Compose, `uv`, Node, and
   ignored `.env` values. Confirm the actual running app image and its DB
   volume. Back up PostgreSQL and test a restore in an isolated database before
   schema work. Never copy `.env`, dumps, cookies, or OTPs into Git or traces.
   Add placeholders to `.env.example` for the Auth0 domain/issuer, client ID,
   client secret, public app origin, and auth-session secret; keep real values
   only in ignored local environment files. Verify the selected origin against
   Compose's published port and cookie Secure setting before browser QA.
2. Implement schema, auth-session, repository, API, and claim flow with a
   mocked Auth0/OIDC provider. Implement Auth0 login and UI. Update
   ADR 0014/0015, charter, implementation plan, current log, status, progress
   JSON, and roadmap only after the chosen behavior is verified.
3. Run focused tests first, then `uv run pytest`, isort, Black, flake8, Ruff,
   frontend typecheck/build, Compose config, and isolated PostgreSQL
   integration. Verify migration row counts, IDs, snapshots, restore, and
   idempotency. Verify a new app container still sees auth sessions and tours.
4. Browser QA on the Mac: account A saves in Chrome and sees the same tour in
   Edge after email login; B sees none and receives 404 for A's detail/delete
   URL; unauthenticated writes receive 401. A claims a legacy Chrome tour and
   reads it in Edge. Test missing/expired/used OTP, logout, cookie clearing,
   CSRF attempt, direct-ID access, pagination, duplicate save, callback state
   mismatch, invalid/expired ID token, and Auth0 outage. Live Auth0/email QA
   is separate from mocked tests.
5. Roll out with a DB backup and migration checkpoint. Keep old columns and
   unclaimed rows until a documented recovery window ends. Rollback restores
   application behavior and database from a verified backup; never make
   already claimed tours readable solely by an old browser cookie.

## Open choices before coding

- Choose the production app domain and email sender. Confirm Mac local callback
  behavior and exact URL matching in Auth0's current configuration.
- Define auth-session idle/absolute lifetime, old-cookie claim window, account
  deletion/export policy, and response to a lost original cookie.
- Decide whether RLS is required for first release or a later defense-in-depth
  milestone after app-layer owner isolation is proven.
- Verify the actual Mac deployment's session/history persistence before
  changing it: this Windows checkout documents only saved snapshots in
  PostgreSQL and keeps the live plan/transcript in process memory.

[auth0-otp]: https://auth0.com/docs/authenticate/passwordless/authentication-methods/email-otp
[auth0-oidc]: https://auth0.com/docs/authenticate/protocols/openid-connect-protocol
[auth0-universal-login]: https://auth0.com/docs/authenticate/passwordless/passwordless-with-universal-login
[auth0-callback]: https://support.auth0.com/center/s/article/Callback-URL-Mismatch-Error-Is-Not-in-the-List-of-Allowed-Callback-URLs
[browser-oauth]: https://www.rfc-editor.org/rfc/rfc10017.html
[oidc]: https://openid.net/specs/openid-connect-core-1_0-18.html
[owasp-session]: https://cheatsheetseries.owasp.org/cheatsheets/Session_Management_Cheat_Sheet.html
[owasp-authz]: https://cheatsheetseries.owasp.org/cheatsheets/Authorization_Cheat_Sheet.html
[postgres-rls]: https://www.postgresql.org/docs/17/ddl-rowsecurity.html
