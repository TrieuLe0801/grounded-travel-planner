# Local Container Verification — 2026-10-14

Status: Passed

## Environment

- Host: Windows/amd64 with Docker Desktop-compatible engine context.
- Docker client: `29.6.2-rd`.
- Docker Engine: `29.5.3`, Linux/amd64.
- Docker Compose: `v5.3.1`.
- Docker Buildx: `v0.35.0`.
- Runtime base: `python:3.10-slim-bookworm`.
- uv binary image: `ghcr.io/astral-sh/uv:0.13.1`.
- Both base-image manifests include `linux/arm64`; no architecture was
  hard-coded, so an Apple Silicon machine can build the native arm64 variant.

## Build and test evidence

- `docker build --check .`: passed with no warnings.
- `docker compose config --quiet`: passed without rendering environment values.
- Test target image: `grounded-travel-planner:test`.
- In-container platform: Linux with CPython `3.10.22`.
- In-container pytest: 19/19 passed after the unverified-hours regression fix.
- Runtime image: `grounded-travel-planner:local`.
- Updated runtime image ID: `sha256:d5440a9e6a8fd776b34762b2e9d3d54788d28723ad4d08c19e68f4b0e3f1c9d6`.
- Runtime image size: 217,659,204 bytes.
- Runtime image platform: Linux/amd64 on this machine.

## Runtime evidence

- Compose bound the app to host `127.0.0.1:8513` and container port `8501`.
- Docker health status: healthy.
- Host `/_stcore/health`: HTTP 200, body `ok` before and after live checks.
- Runtime identity: UID/GID `10001`, user/group `app`.
- `/app/.env`: absent.
- Required OpenAI, Tavily and LangSmith variable names were present at runtime;
  values were not printed.
- Image-history credential-pattern matches: 0.
- Startup-log traceback/error matches: 0.
- Startup-log secret-value-pattern matches: 0.

## Live provider checks from the container

1. Hoi An request: rejected after the bounded repair because opening-hour and
   source-place evidence did not satisfy validation. No candidate was committed.
2. Hue request: committed successfully with five graph steps, one Tavily search,
   zero repairs, six returned citations and no validation issues.

The first result is expected safe-failure behavior, not a container failure. It
demonstrates that container execution does not bypass the same grounding policy
used on the host.

## Cleanup

`docker compose down` stopped and removed only this project's app container and
network. The explicitly tagged `grounded-travel-planner:test` and
`grounded-travel-planner:local` images were retained for local inspection. No
global prune or unrelated container/image operation was used.
