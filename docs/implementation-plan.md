# Implementation Plan

Status: Active
Last updated: 2026-11-17

This plan tracks remaining implementation acceptance. Product requirements and
accepted architecture are defined in the [project charter](project-charter.md)
and [ADRs](adr/README.md); completed change history is not repeated here.

## Current environment

On 2026-11-17, local main fast-forwarded to commit 34e20ba. The local Compose
app was rebuilt as image
sha256:286a871aff073cd2a37586c14a557f96aadc0ac96a588c1f8277a1a3a79c3138.
The app and PostgreSQL were healthy, the local root returned HTTP 200, and the
configured Auth0 password-connection setting was present in the container.
PostgreSQL was not recreated. App recreation cleared session-only itinerary,
conversation and pending-turn state.

This is local Compose evidence. It does not establish browser acceptance or
completion of a live Auth0 flow.

## Remaining work

### 1. Auth0 and account-flow acceptance

- Confirm the Auth0 application and database connection are enabled for the
  configured public host, www.citedtrip.app.
- In a browser, verify password sign-in, signup, email verification, email-code
  sign-in, callback, planner access and logout.
- Verify existing-account identity linking, account status controls and the
  administrator usage/deletion flows. Do not claim live deletion acceptance
  without an actual authorized Auth0 flow and post-check.

### 2. Saved tours and UI acceptance

- In a browser, verify explicit save, list, detail and delete for the signed-in
  owner, including isolation from another account.
- Review the React interface at phone and desktop widths. Check Home reset,
  account actions and navigation between chat and graph while a turn is pending.

### 3. Live quality evaluation

- Label representative live sources and measure relevance, place coverage and
  host diversity.
- Evaluate Chat accuracy across multiple factual questions.
- Exercise live reorder and replace intents separately from offline tests.

### 4. Release readiness

Any production rollout remains a separate decision. Preserve the existing
backup, migration, CI, branch-protection and deployment gates.

## Verification baseline

The latest integrated source verification was recorded on 2026-11-16:
246 offline tests passed and one optional PostgreSQL test was skipped because
its opt-in settings were unset. Python quality checks and frontend check/build
also passed before the Compose rebuild. No test suite ran during the
2026-11-17 Compose update; no live Auth0 request or browser flow ran.

See [project status](../PROJECT_STATUS.md) for the concise evidence snapshot,
the [learning log](learning-log/2026-10-14-scope-reset.md) for recent
operational decisions, and CI/experiment artifacts for historical check output.
