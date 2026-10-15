# Implementation Plan

Status: Active
Last updated: 2026-10-14

## Phase 1A - Core Runtime — Implemented

Acceptance:

- Create an importable `grounded_travel_planner` package.
- Keep reusable modules in `src/utils/`.
- Add typed provider interfaces for model, search and tracing.
- Add LangChain `ChatOpenAI` structured-output adapter.
- Add Tavily search adapter that returns normalized URLs only.
- Add LangSmith trace sink that propagates one `thread_id`.
- Implement a LangGraph runtime with exactly Coordinator and Planner nodes.
- Coordinator classifies and explains; Planner produces every candidate and owns
  all search calls.
- Validate input, schedule and source references before committing a candidate.
- Preserve the previous plan when validation fails.

Checks:

- Compile/import the package with local dependencies.
- Do not claim live OpenAI, Tavily or LangSmith verification until credentials,
  network and an executable flow are run.

## Phase 1B - Streamlit Webapp — Implemented

Acceptance:

- One-page Streamlit UI with destination/place, start date and day count input.
- Session-only canonical plan and chat history.
- Chat can request add, remove, replace, reorder, day and time changes.
- Ordinary chat does not mutate plan state.
- Render estimated durations, unverified hours, validation issues and sources.
- Smoke-run the app with `.env` credentials.

## Phase 1C - Tests And Live Gates — Verified

Acceptance:

- Mocked unit tests cover providers, graph routing, validation and service
  commit semantics.
- Live Tavily/OpenAI/LangSmith verification is recorded separately and never
  substitutes for deterministic tests.
- Full quality checks pass or blockers are documented.

## Verification Evidence

- `uv run pytest`: 19 passed on 2026-10-14.
- isort, Black, flake8, Ruff, `uv lock --check` and `git diff --check` passed.
- `scripts/live_smoke.py`: final run committed a one-day Hue plan with
  `gpt-5.5`, one Tavily call, one bounded repair and five returned citations.
- LangSmith query found 14 matching root/child runs, all with the same
  `thread_id` metadata.
- Detailed live evidence: `docs/experiments/2026-10-14-live-two-agent-smoke.md`.

## Phase 1D - Local Container — Verified

Acceptance:

- Multi-stage locked build with a dedicated offline test target.
- Final runtime contains production dependencies only and runs as a non-root
  user.
- `.env` is excluded from the build context; Compose injects it only at runtime.
- Streamlit listens inside the container on `0.0.0.0:8501`; the host mapping is
  loopback-only.
- Healthcheck, image history, log scan, environment-presence check and one live
  successful plan are recorded before repository push.
- Dockerfile and uv base images retain Linux arm64 support for the Mac M1.

Evidence: `docs/experiments/2026-10-14-local-container-smoke.md`.
