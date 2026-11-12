# Cloudflare Tunnel Deployment

## Current state — 2026-11-12

`https://citedtrip.app` is the sole public app origin. The existing remotely
managed `cloudeflared-tunnel` publishes it to `http://app:8000`. Its connector
and the planner app share `grounded-travel-planner_public-ingress`; PostgreSQL
is not attached to that network. No additional connector or host port is used.

The app uses `GTP_AUTH_PUBLIC_ORIGIN=https://citedtrip.app`. The temporary
additional-origin setting, ngrok Compose service, token setting, and Traffic
Policy were removed. Auth0 login on the custom domain redirects to the expected
callback and reaches the hosted login page. Full OTP, planner and logout checks
still require a browser sign-in.

## Auth0 allowlist cleanup

In **Auth0 Dashboard → Applications → Applications → the current app → Settings
→ Application URIs**, keep these entries:

- Allowed Callback URLs: `https://citedtrip.app/api/auth/callback`
- Allowed Logout URLs: `https://citedtrip.app/`

Remove the former ngrok entries if present:

- `https://inventionless-contortively-destinee.ngrok-free.dev/api/auth/callback`
- `https://inventionless-contortively-destinee.ngrok-free.dev/`

Keep any unrelated development entries. The Auth0 dashboard cleanup is pending
because this session has no dashboard connection.

## Tunnel configuration

Use the existing `cloudeflared-tunnel`; do not create another Tunnel or copy
its token. Its published application route is:

- Hostname: `citedtrip.app`
- Service: `http://app:8000`
- HTTP Host Header override: empty
- Cloudflare Access: not enabled; the app authenticates through Auth0

The route is dashboard-managed. Cloudflare creates the DNS record for a
published application route. Keep the connector and app on the dedicated
ingress network, with PostgreSQL only on the planner's default network.

The connector belongs to the Visual Assistant Compose project's `publish`
profile. A full Compose shutdown stops it and temporarily takes all routes on
the shared Tunnel offline. After such a shutdown, restore it from that project
with:

```sh
docker compose --profile publish up -d cloudflared
```

## Verification

On 2026-11-12, requests using a browser User-Agent returned HTTP 200 for the
root and `/api/health`. `/api/auth/login` redirected with callback
`https://citedtrip.app/api/auth/callback` and reached the Auth0 hosted page
with HTTP 200. A generic Python User-Agent received Cloudflare error 1010 while
a Chrome User-Agent succeeded. OTP callback, authenticated planner access and
logout were not completed in this check.
