# Auth0 account archive: offline and isolated PostgreSQL checks

Date: 2026-11-03
Branch: `feature/travel-ground-planner`

Follow-up verification: 2026-11-04.

No Auth0 tenant settings were present in the ignored `.env`. No email OTP or
cross-browser Auth0 login was tested. The running app container was not
recreated and the live PostgreSQL schema was not changed.

## Backup and restore

- `pg_dump -Fc` from the running PostgreSQL 17 database wrote an owner-only
  backup outside Git at
  `../grounded-travel-planner-data/auth0-preflight-2026-11-03.dump`.
- `pg_restore --list` succeeded in the PostgreSQL container. The dump was
  restored to an isolated `travel_planner_auth0_restore_test` database.
- Original and restored `saved_tours` each held five rows. An ordered MD5 of
  `id`, `saved_at` and exact `plan_snapshot` text matched:
  `c55128259658cf664fd1b60e7b0ce150`.

## Migration and account behavior

- `scripts/migrate_saved_tours_account_ownership.py --postgres` ran twice on
  the isolated restore. Both invocations exited 0. The five-row checksum was
  unchanged. `app_users`, `auth_identities`, `auth_sessions` and
  `saved_tours_by_user_saved_at_id` were present afterward.
- An isolated PostgreSQL process created a fake verified identity and account
  session. A new repository instance read the session, accepted its CSRF
  token and saw an empty account-scoped archive. Revocation made the session
  unreadable. No Auth0 request was made.
- Host suite: `uv run pytest -q` passed 146 tests, with one optional test
  skipped. Isort, Black, flake8, Ruff, `uv lock --check`, frontend
  typecheck/build and `docker compose config --quiet` passed. The suite
  includes mocked RSA ID-token issuer, audience, nonce and expiry checks.
- `docker buildx build --target test` passed its container pytest gate:
  146 passed, 1 optional PostgreSQL test skipped.
- A disposable PostgreSQL check ran 16 concurrent logins for one OIDC identity.
  All mapped to one internal account. A session survived repository reconnect,
  passed CSRF verification, then became unreadable after revocation.
- The first concurrency smoke exposed a PostgreSQL text error from a NUL
  separator in the advisory-lock key. The key now uses an unambiguous
  length-prefixed issuer; a regression test and the 16-login PostgreSQL rerun
  passed.
- Final read-only check of the live archive still returned five rows and the
  original checksum. The root endpoint returned HTTP 200. Runtime image
  `sha256:59b4bada35b94df9396c6c7c7856d6d8e41b2cfe1a0ef0ca6b70eaf73fd9fd91`
  was built, but the running app stayed on
  `sha256:d40fd6f5bdb20d5ccf605ba1b8b2deb3a43e71964a6c563552f0acfad6606bad`.

The live migration, app recreation, email OTP, account A/B browser access,
and recovery policy remain pending. Recreating the app will clear its
session-only itinerary and transcript.

The SQLite migration command also initializes its separate Auth database at
`GTP_AUTH_DB_PATH` (default `.local/auth.sqlite`). `--auth-db` overrides that
path for controlled local migration.
