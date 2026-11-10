# Mandatory Sign-In And Account Management Proposal

Date: 2026-11-08
Status: Selected for implementation by the user

## Finding

The React/FastAPI product already uses Auth0 Universal Login with email OTP,
Authorization Code plus PKCE, `state`, `nonce`, signed ID-token validation,
opaque `HttpOnly` account cookies, CSRF protection, and persistent revocable
application sessions. Saved-tour access already uses the server's internal
account UUID. The gap is access control: the React app creates a planner session
before checking Auth0, and planning/session APIs accept anonymous requests.

Auth0's Authorization Code flow is designed for regular web apps where the
client secret stays on the server. Auth0's current Universal Login guidance
requires selecting the email passwordless connection when that flow is
configured. Auth0 also provides a hosted user-profile store and dashboard/API
for account administration. See the linked primary references below.

## Options

| Option | Assessment |
|---|---|
| Keep anonymous planning; require accounts only for saved tours | Rejected because users must sign in before entering the planner. |
| Add app-owned passwords and registration forms | Rejected because it duplicates credential storage, verification, recovery, and account lifecycle already provided by Auth0. |
| Use Auth0 email OTP, server-side sessions, and account-bound planner sessions | Selected. It reuses the existing provider and BFF, keeps tokens out of browser JavaScript, and supports cross-browser access to explicitly saved tours. |
| Put Auth0 access tokens in the browser and call app APIs as a public SPA | Rejected because the same-origin FastAPI BFF already owns session checks, CSRF, rate limits, and saved-tour access. |

## Selected Design

1. Serve a public, bilingual landing page. It explains grounded itinerary
   planning, source attribution, estimated facts, session-only live trips, and
   explicit saved snapshots. One primary action sends the user to Auth0 email
   OTP. Do not collect a password or profile fields in the app.
2. Check `/api/auth/me` before requesting planner state. An unauthenticated
   browser sees only the landing page. A failed account check shows an error
   and retry path.
3. Enforce authentication in FastAPI for planner session creation, reads,
   resets, language changes, turns, visuals, and session-backed saves. A UI
   check alone is not an access control boundary.
4. Bind each volatile `WebSession` to the verified internal account UUID. Every
   session read or mutation must match that owner. Adopt an unowned session
   from the same browser on successful login; rotate sessions owned by another
   account. Do not persist live itineraries, chat, locale, or pending work.
5. On logout, revoke the application auth session, remove the in-memory planner
   session, and clear both cookies. A later account cannot read the previous
   account's itinerary or transcript. Already submitted background work may
   finish, but its result has no session that can collect it.
6. Keep account management small: show the verified email, saved tours, and
   sign-out. Auth0 owns credentials and account records; administrators use the
   Auth0 Dashboard. The app does not store passwords or provide user-role,
   admin, account-deletion, or export screens. Define deletion/export policy
   separately before exposing self-service account lifecycle actions.
7. Keep account identity keyed by verified Auth0 issuer and subject, mapped to
   an internal UUID. Email remains display data, never an archive owner key.

## Verification Boundary

Mocked tests can verify access gates, session ownership, callback binding,
logout cleanup, CSRF, and archive isolation. They cannot verify tenant
configuration, OTP delivery, live callback exchange, cross-browser behavior,
or production rollout. Those require the configured Auth0 tenant and browser
QA.

## References

- [Auth0 Authorization Code Flow](https://auth0.com/docs/get-started/authentication-and-authorization-flow/authorization-code-flow)
- [Auth0 Authorization Code Login](https://auth0.com/docs/get-started/authentication-and-authorization-flow/authorization-code-flow/add-login-auth-code-flow)
- [Auth0 passwordless email with Universal Login](https://support.auth0.com/center/s/article/Passwordless-login-not-triggered-using-the-New-Universal-Login-with-Identifier-First-Profile)
- [Auth0 sessions and cookies](https://auth0.com/docs/manage-users/sessions)
- [Auth0 user profiles](https://auth0.com/docs/manage-users/user-accounts/user-profiles)
- [Existing Auth0 account-ownership decision](../adr/0016-auth0-account-owned-saved-tours.md)
