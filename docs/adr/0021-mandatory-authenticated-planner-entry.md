# ADR 0021 - Mandatory Authenticated Planner Entry

Status: Accepted
Date: 2026-11-08
Amended: 2026-11-14

## Context

ADR 0016 selected Auth0 Universal Login with email OTP for saved-tour ownership,
but retained anonymous itinerary planning. The user now requires sign-in before
using the planner and requested a public introduction page with account entry.
The user also requested SSO for existing Auth0 accounts while preserving the
current email-code flow for users without an Auth0 session, using the existing
Auth0 tenant without adding another connection.
The React frontend and FastAPI adapter already implement an Auth0 BFF, while
planner sessions and live trip state remain in process memory.

## Decision

- Keep Auth0 Universal Login and the existing email passwordless flow. Omit the
  `connection` parameter from `/authorize` so Auth0 can reuse an active tenant
  session for SSO. Users without an active Auth0 session continue through the
  existing email one-time-code flow. Use Authorization Code with PKCE, `state`,
  `nonce`, signed ID-token validation, and the opaque server-side account session
  defined by ADR 0016. Do not add an Auth0 connection, app-owned passwords, or
  provider tokens in browser JavaScript.
- Make the public React landing page the only unauthenticated product view.
  Check `/api/auth/me` before requesting planner state. Carry the selected UI
  language through the safe local Auth0 return target and store it in the
  authenticated planner session after login.
- Require a valid Auth0 application session for planner session creation,
  reads, resets, language changes, turns, visuals, and saved operations that
  depend on a live plan. Direct unauthenticated API requests return `401`.
- Add the verified internal account UUID as owner of each volatile planner
  session. Require owner equality on every session-backed operation. On login,
  bind an unowned session from the same browser to the account; replace a
  session owned by a different account. The plan, transcript, summary, locale,
  and pending turn remain session-only.
- On logout, revoke the application auth session, remove the current volatile
  planner session, and clear the account and planner cookies. A submitted
  background turn may finish, but its result has no session to collect it.
- Keep account controls limited to verified email, saved tours, and sign-out.
  Auth0 remains the credential and user-profile system; administrators manage
  accounts through the Auth0 Dashboard. Account deletion/export and roles need a
  separate policy decision before app controls are added.
- Keep the root landing page public and static. Do not require authentication
  for read-only public assets or health checks. The private planner APIs remain
  authoritative for access control.

## Alternatives Considered

- Keep anonymous planning and gate only the archive: rejected because it does
  not meet the new product requirement.
- Add a local password/signup system: rejected because it duplicates Auth0's
  credential, email verification, recovery, and user lifecycle services.
- Put identity tokens in browser storage and call APIs as a public SPA:
  rejected because the existing same-origin FastAPI BFF already owns sessions,
  CSRF protection, quotas, and account-scoped storage.
- Persist live plans and transcripts by account: rejected because the existing
  session-only boundary remains active; only an explicit save creates a durable
  read-only tour snapshot.

## Consequences

- Anonymous visitors can read the public landing page but cannot start or use a
  planner session through the React UI or protected API routes.
- Account changes in one browser cannot expose the previous account's live
  itinerary or transcript.
- First-time sign-in creates the Auth0 identity and local internal account
  mapping. Email is display data, not the saved-tour owner key.
- SSO requires an active Auth0 browser session. Users without one use the
  existing email-code flow; the tenant must keep that passwordless connection
  enabled. The application does not classify accounts by email or link new
  Auth0 subjects to existing accounts.
- Auth0 tenant setup, production email delivery, callback/logout allowlists,
  live OTP, cross-browser QA, and controlled database rollout remain explicit
  deployment checks. Offline tests do not prove those live behaviors.
- The retained Streamlit interface remains a local migration aid. The public
  Compose entry point continues to serve the React/FastAPI product.

## Review Triggers

- Add social login, passkeys, enterprise identity, or another Auth0 connection.
- Add self-service account deletion/export, roles, or application-managed
  account profile fields.
- Persist live itineraries, chat, language preferences, or pending work.
- Expose the retained Streamlit interface as another public product entrypoint.

## Supersedes

This ADR supersedes ADR 0016's statement that anonymous planning remains
available. ADR 0016's Auth0 protocol, cookie/session controls, owner-scoped
saved tours, explicit snapshot saves, legacy claim path, and migration
requirements remain accepted.

This ADR also supersedes ADR 0020 only where its turn quota accepts an
anonymous session principal. Production planning turns now require Auth0 and
are limited by verified account UUID; all other token and quota controls remain
accepted.
