# ADR 0021 - Mandatory Authenticated Planner Entry

Status: Accepted
Date: 2026-11-08
Amended: 2026-11-16

User amendment — 2026-11-16: Users may explicitly link Google, Auth0 database
password, and email OTP identities to one internal account UUID. Every link
requires a recent session for the original account, CSRF, fresh authentication
of the added identity, a verified matching email, the same issuer, and an
identity not owned by another account. Email equality alone never grants
account ownership.

User amendment — 2026-11-16: Existing duplicate application accounts may be
reconciled only by an operator after confirming ownership of both identities,
creating a backup, and pausing writes. The operator names the canonical and
secondary UUIDs. A dry-run is default; applying the merge moves all secondary
identities and saved-tour ownership, revokes secondary sessions, preserves
snapshot IDs/content and access-audit history, records the secondary UUID as a
canonical-account alias for historical LangSmith usage, and marks the old
account merged. Access-status or administrator-role conflicts fail closed; a
merge never grants administrator rights. This does not link Auth0 user
profiles, merge automatically by email, or change Auth0 tenant settings.

User amendment — 2026-11-15: The account menu opens Personal information.
It shows which Google, database-password and email-code identities are linked
to the internal application account. A Google-first user may create a separate
Auth0 database password through hosted signup and email verification, then
authenticate that database identity again to link it to the original UUID.
Existing password or OTP users can link Google through the existing fresh-login
flow. Password changes use Auth0's database-connection reset email. All links
require a recent original-account session, CSRF, fresh authentication of the
new identity, verified matching email and an unowned issuer/subject. A matching
email alone never links or transfers saved tours. Email OTP remains available.
Auth0 tenant configuration and browser checks are separate acceptance gates.
User amendment — 2026-11-15: Registration uses an Auth0 database password
connection with a password and confirmation field. Auth0 enforces a minimum of
eight characters including an uppercase letter, a number and a special
character; its verification email must be confirmed before app access. A
verified user signs in again to use the planner. Existing Google SSO and email
OTP remain available. The app validates `email_verified=true` in the signed ID
token before creating an account or session. No administrator grant is needed
for a new verified account or SSO identity. Auth0 tenant configuration and
delivery remain separate live checks.

User amendment — 2026-11-15: A verified Google identity may be linked manually
to the matching existing administrator account when the user explicitly
requests it. This is a one-time, operator-run repair with exact identity and
account-state checks, a database backup, session revocation, and audit record.
Runtime account lookup still uses issuer and subject; it never links accounts
automatically by email. Do not generalize this repair to other identities.

User amendment — 2026-11-15: An existing registered user may use Google SSO
without registering again and must retain the same internal account and saved
tours. A returning Auth0 issuer/subject already resolves to that account. For a
new Google subject, the user first signs in to the existing account, then
explicitly links Google after a fresh Google authentication. Require a recent
existing-account session, the same verified email, and proof of the Google
identity. Never grant ownership of the existing account from email equality
alone. If a separate Google account has data or other identities, stop linking
and resolve ownership without discarding either account's records.

User amendment — 2026-11-16: An active administrator may permanently delete
another application account and its Auth0 user profiles. The administrator
confirms this irreversible action in the bilingual admin page. The backend uses
a server-only Auth0 Management API M2M client with only the `delete:users`
scope. It deletes every stored issuer/subject pair, including the original
login subject and manually linked identities; it never resolves a target by
email. A provider failure leaves application account data unchanged. After
Auth0 confirms deletion, the application revokes sessions and marks the account
`deleting` until its owned saved tours are removed. An administrator can retry
local cleanup; retries repeat the idempotent Auth0 deletes. Completion removes
identity and legacy usage-alias rows, clears the account email and administrator
flag, and retains a `deleted` tombstone for access-audit foreign keys. It
retains `account_merges` rows and merge/access audit history so historical usage
aliases remain traceable; merged secondary tombstones cannot be deleted. Admins
cannot delete themselves or the last active administrator. Account deletion
does not rewrite or delete historical LangSmith traces.

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

- Keep Auth0 Universal Login and the existing email passwordless flow. Add an
  Auth0 database connection for password signup; keep passwords in Auth0. The
  generic SSO route omits `connection` so Auth0 can reuse an active tenant
  session. Direct Google, email/password and email-code actions select fixed
  connections. Users without an active Auth0 session can use the database
  password or existing email one-time-code flow. Use Authorization Code with PKCE, `state`,
  `nonce`, signed ID-token validation, and the opaque server-side account session
  defined by ADR 0016. Require a verified email claim before app access. Do not
  add app-owned passwords or provider tokens in browser JavaScript.
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
- Show verified email and linked sign-in methods in Personal information,
  alongside saved tours and sign-out. Start password signup/reset and explicit
  Google, email OTP, and password identity links from this page; Auth0 keeps all
  credentials. Administrators manage Auth0 credentials through the Auth0
  Dashboard and can block, regrant, or delete application accounts through the
  protected admin page. Account export and user self-service deletion still
  need separate decisions.
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
- Automatically merge accounts when verified email addresses match: rejected
  because email equality does not prove ownership of both identities and could
  transfer saved tours or administrator access. Require explicit authentication
  of both identities; use operator reconciliation only for existing UUID
  conflicts.
- Persist live plans and transcripts by account: rejected because the existing
  session-only boundary remains active; only an explicit save creates a durable
  read-only tour snapshot.

## Consequences

- Anonymous visitors can read the public landing page but cannot start or use a
  planner session through the React UI or protected API routes.
- Account changes in one browser cannot expose the previous account's live
  itinerary or transcript.
- First-time sign-in creates the Auth0 identity and local internal account
  mapping. A returning identity reuses its internal account and saved tours.
  Email is display data, not the saved-tour owner key. A new Google identity
  matching an existing email needs explicit linking after both sign-ins.
- SSO requires an active Auth0 browser session. Users without one can use the
  password or existing email-code flow; the tenant must keep that passwordless connection
  enabled. The application does not classify accounts by email or link new
  Auth0 subjects to existing accounts by email alone.
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
