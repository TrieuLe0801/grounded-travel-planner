# Cloudflare Tunnel Deployment

## Current state — 2026-11-15

`https://www.citedtrip.app` is the current public app origin, as confirmed by
the user. Read-only checks from this workspace returned HTTP 200 for its root
and health endpoint; the login route returned an Auth0 authorization URL with
the `www` callback. The existing remotely managed `cloudeflared-tunnel` serves
the app through `http://app:8000`. Its connector
and the planner app share `grounded-travel-planner_public-ingress`; PostgreSQL
is not attached to that network. No additional connector or host port is used.

Set `GTP_AUTH_PUBLIC_ORIGIN=https://www.citedtrip.app`. The temporary
additional-origin setting, ngrok Compose service, token setting, and Traffic
Policy were removed. The full Auth0 callback, OTP, planner and logout checks
still require a browser sign-in.

## Auth0 allowlist cleanup

In **Auth0 Dashboard → Applications → Applications → the current app → Settings
→ Application URIs**, keep these entries:

- Allowed Callback URLs: `https://www.citedtrip.app/api/auth/callback`
- Allowed Logout URLs: `https://www.citedtrip.app/`

Remove the former ngrok entries if present:

- `https://inventionless-contortively-destinee.ngrok-free.dev/api/auth/callback`
- `https://inventionless-contortively-destinee.ngrok-free.dev/`

Keep any unrelated development entries. Remove the older apex entries only
after confirming no active flow uses them. The Auth0 dashboard allowlist and
cleanup remain unverified from this workspace.

## Tunnel configuration

Use the existing `cloudeflared-tunnel`; do not create another Tunnel or copy
its token. Its published application route is:

- Hostname to confirm in Cloudflare Dashboard: `www.citedtrip.app`
- Service: `http://app:8000`
- HTTP Host Header override: empty
- Cloudflare Access: not enabled; the app authenticates through Auth0

The route is dashboard-managed. Cloudflare creates the DNS record for a
published application route. Keep the connector and app on the dedicated
ingress network, with PostgreSQL only on the planner's default network.

The connector belongs to the Visual Assistant Compose project's `publish`
profile. Use its `compose.grounded-travel-planner.yaml` overlay to run the
remotely managed named Tunnel and attach the connector to the shared ingress
network. A full Compose shutdown stops it and temporarily takes all routes on
the shared Tunnel offline. After such a shutdown, restore it from the Visual
Assistant repository root with:

```sh
docker compose -f compose.yaml -f compose.grounded-travel-planner.yaml --profile publish up -d cloudflared
```

The companion [Visual Assistant PR](https://github.com/TrieuLe0801/visual-assistant/pull/3)
adds this durable overlay. Keep the tunnel token in its existing ignored
`.secrets/cloudflare_tunnel_token` file.

## Verification

On 2026-11-12, requests using a browser User-Agent returned HTTP 200 for the
root and `/api/health`. `/api/auth/login` redirected with callback
`https://citedtrip.app/api/auth/callback` and reached the Auth0 hosted page
with HTTP 200. A generic Python User-Agent received Cloudflare error 1010 while
a Chrome User-Agent succeeded. OTP callback, authenticated planner access and
logout were not completed in this check.

On 2026-11-15, read-only checks returned HTTP 200 for
`https://www.citedtrip.app/` and `/api/health`. The login route returned HTTP
307 with `https://www.citedtrip.app/api/auth/callback` in its Auth0 authorization
URL. The apex host did not resolve from this workspace. Auth0 allowlist,
callback exchange and logout were not checked.
