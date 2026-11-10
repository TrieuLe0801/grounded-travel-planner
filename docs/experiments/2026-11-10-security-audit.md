# Application Security Audit — 2026-11-10

## Scope and method

Source review covered authenticated FastAPI planner mutations and their React
callers, Auth0 issuer handling, both HTTP and retained Streamlit graph views,
and both SQLite fallback repositories. Protected data/actions were account
sessions, live trip state, Auth0 client credentials, graph details and local
saved-tour/auth files. Checks used mocked providers and disposable temporary
directories; no live provider, deployment, secret or real database was
inspected.

## Confirmed findings and fixes

### Missing CSRF checks on planner mutations

- The `POST /api/session`, `POST /api/session/reset`, `PUT
  /api/session/language` and `POST /api/turns` routes authenticated the account
  and checked session ownership but did not validate the session CSRF token.
- A request that reached these routes with the victim's auth cookie could
  create/reset a session, change its language or submit a turn. Reset discards
  session-only itinerary/chat state; turns can consume the account quota and
  trigger model work. `SameSite=Lax` limits ordinary cross-site POSTs, but does
  not replace CSRF protection for same-site cross-origin contexts.
- Each route now validates `X-CSRF-Token` before changing state. React sends the
  in-memory token from `/api/auth/me`; it is not persisted. Regression coverage
  checks missing and invalid tokens are rejected before mutation and valid
  tokens preserve expected behavior.

### Graph views made external render requests

- The public `GET /api/graph/image` route and retained Streamlit diagnostic page
  called LangGraph's Mermaid PNG renderer. Its default API path sends graph
  source to Mermaid.ink on each request, so an unauthenticated HTTP read or
  local page render could cause outbound traffic and expose graph structure to
  a third party; repeated requests also repeat that work.
- Both views now render the compiled topology locally as SVG, and the
  `TravelPlannerService.get_graph_image()` PNG call path was removed. Offline
  API and Streamlit tests verify local rendering without a graph turn or
  provider call. No live Mermaid request was made during this audit.

### Auth0 issuer accepted cleartext HTTP

- The configured issuer was interpolated into the token endpoint URL. An `http`
  issuer could send the Auth0 client secret without TLS during code exchange.
- `Auth0OidcProvider` now accepts only a valid HTTPS origin (no user info,
  path, query or fragment) before constructing endpoints. Tests reject HTTP and
  malformed/non-origin values. No tenant configuration or credential was read.

### SQLite fallback files inherited permissive modes

- A safe temporary-path reproduction observed a `0755` storage directory and
  `0644` SQLite database file under the host umask. The fallback stores account
  metadata and private saved-tour snapshots; another local user able to traverse
  that directory could read them.
- Before SQLite connects, both repositories now restrict the database and
  existing WAL/SHM/journal sidecars to `0600`; missing directories are created
  with `0700`. Existing configured directories are left unchanged. Tests use
  temporary paths and assert permissions before SQLite opens the files.

## Verification

- `uv run pytest`: 185 passed, 1 optional PostgreSQL test skipped.
- Frontend `npm run check` and `npm run build` passed.
- isort, Black, flake8, Ruff and `git diff --check` passed.
- Tests used local fakes; no live Auth0, model, search, tracing or Mermaid
  service was called. No browser, deployed endpoint, Compose image, actual
  PostgreSQL deployment or real `.local` database was checked. The fixes are
  source changes and have not been deployed.
