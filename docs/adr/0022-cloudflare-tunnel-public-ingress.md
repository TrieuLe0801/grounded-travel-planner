# ADR 0022 - Cloudflare Tunnel Public Ingress

Status: Accepted
Date: 2026-11-12

## Context

The public app previously used an ngrok tunnel. The user registered
`citedtrip.app` and requested Cloudflare as the replacement ingress while
keeping Auth0 login available. Auth0 callback and logout URLs are derived from
one configured public origin, so changing that origin while ngrok remains
reachable can break login flows already in progress.

## Decision

- Reuse the existing remotely managed `cloudeflared-tunnel` for
  `citedtrip.app`; add a published application route to `http://app:8000`.
  Keep the existing connector in its current Compose project. Connect that
  connector and the planner app through the dedicated external
  `grounded-travel-planner_public-ingress` network. Do not attach the connector
  to the planner's default network, which also contains PostgreSQL.
- Keep the tunnel token in the existing Cloudflare connector's file-backed
  Compose secret. Do not copy it into the planner `.env` or create another
  connector replica for the same Tunnel.
- Do not publish the app port beyond its existing loopback binding. Leave the
  Tunnel origin's HTTP Host Header override empty so the original public
  hostname reaches the app. Do not add a Cloudflare Access login policy;
  Auth0 remains the product authentication system.
- Set `GTP_AUTH_PUBLIC_ORIGIN=https://citedtrip.app` as the sole public Auth0
  origin. Callback and logout URLs require an exact request `Host` match; do
  not trust forwarded host headers. Temporary multi-origin support was removed
  after cutover.
- Add the exact `https://citedtrip.app/api/auth/callback` and
  `https://citedtrip.app/` URLs to the Auth0 application's allowlists. The
  ngrok Compose service, token setting and Traffic Policy are now removed;
  remove its former callback/logout URLs from Auth0.

## Consequences

- The existing tunnel connector reaches the planner app through a dedicated
  ingress network; it cannot directly reach the planner PostgreSQL service.
  No new host port is exposed.
- A one-origin Auth0 flow can no longer be assumed during host migration; each
  callback, code exchange, and logout must resolve to the matching allowlisted
  origin.
- Recreating the app clears session-only itineraries, conversations, and
  pending turns. Explicitly saved PostgreSQL tours remain stored.
- The route is live and browser-like root/health checks pass. Auth0 login reaches
  the hosted page; OTP callback, planner access and logout still need a browser
  smoke test. The Auth0 dashboard still needs removal of the former ngrok URLs.

## Review Triggers

- Change the production hostname or move public ingress away from Cloudflare
  Tunnel.
- Add another public app origin or change Auth0 callback/logout behavior.
