# ADR 0019 - GitHub Actions CI And Mac Deployment

Status: Accepted
Date: 2026-11-05

## Context

The app runs in Docker Compose on an Apple Silicon Mac. PostgreSQL data lives in
a host directory outside Git, while live plans, chat history and sessions stay
in app memory. The repository has no CI workflow. Auth0 account ownership is
implemented, but its live database migration and app rollout are still pending
under ADR 0016.

## Decision

- Run Python tests, Python formatting/lint checks, frontend typecheck/build and
  Compose configuration validation on GitHub-hosted Ubuntu runners for pushes
  and pull requests to `feature/travel-ground-planner`.
- Use a macOS `launchd` poller to check the public GitHub Actions API every five
  minutes. Deploy a push commit only after its CI workflow succeeds. Pull
  requests run only on GitHub-hosted runners.
- Require local Mac setting `GTP_DEPLOY_ENABLED=true` before deployment. Keep it
  `false` until the explicit Auth0 database migration and rollout are complete.
- Keep deployment `.env` and local path configuration on the Mac. The poller
  needs no GitHub token or inbound network access. Do not put provider
  credentials or database passwords in workflow files or GitHub Actions
  secrets.
- Rebuild and health-check only the `app` Compose service. Do not recreate the
  PostgreSQL service or run database migrations automatically. Restore the
  previous app image if the replacement fails health checks.
- Serialize deployments. App recreation may clear session-only plans and chat
  history; saved tours remain in the external PostgreSQL data directory.

## Alternatives Considered

- GitHub self-hosted runner on the Mac: rejected because this is a public
  repository and fork pull requests can target persistent runners.
- SSH from GitHub-hosted runners: rejected because the Mac is a local target and
  would need inbound network access and a stored SSH deployment credential.
- Deploy unverified commits: rejected because CI must pass before app code runs
  on the Mac.
- Run database migrations during every deploy: rejected because the Auth0
  rollout requires a tested backup, paused writes and a separately verified
  account migration.

## Consequences

- CI runs automatically on the active feature branch. Runtime changes deploy
  automatically only when the user session is active, Mac stays awake,
  Docker Desktop is available, the LaunchAgent runs and
  `GTP_DEPLOY_ENABLED=true`.
- The Mac poller checks at five-minute intervals and waits for a passing push
  workflow before fetching source.
- Each app deployment restarts the service and loses in-memory session state.
- PostgreSQL migrations, Auth0 tenant setup and account rollout remain explicit
  release operations.

## Review Triggers

- Change the active deployment branch or move the app off the local Mac.
- Replace Docker Compose or the external PostgreSQL data directory.
- Complete the Auth0 rollout and set local `GTP_DEPLOY_ENABLED=true`.
