# Implementation Plan

Status: Active
Last updated: 2026-11-20

This plan tracks remaining acceptance and concise changes that affect it.
Product requirements and accepted architecture are defined in the
[project charter](project-charter.md) and [ADRs](adr/README.md).

## Implemented update: UI trend proposal — 2026-11-20

Implemented the proposal's high-priority landing and itinerary changes. On
phone, sign-in actions now precede the introduction and fit in the first
390×844 viewport. The itinerary header places destination, date, day count and
explicit snapshot-save action together. Multi-day itineraries provide
keyboard-accessible links to each day; one-day plans omit that navigation.
Missing photos use a compact message while actual source links, photo credits,
estimated durations and unverified-hours labels remain visible. English day
counts use singular/plural forms, and language/calendar controls meet the
project's 44px target.

`npm run check`, `npm run build`, `git diff --check` and 17 mocked Chromium
checks passed. Screenshots were generated at 390, 768, 1024 and 1440 px; the
landing and itinerary were inspected at phone and desktop sizes. The suite
checked reduced motion, page overflow, reset confirmation, pending-turn
language switching and existing source/photo/chat behavior. Live Auth0,
provider, saved-tour ownership and deployed flows were not exercised.

## Implemented update: plan-first React layout — 2026-11-20

When a current plan exists, the itinerary and explicit save action appear
without the trip setup form above them. The existing New Trip action still
confirms before resetting the session. Day cards now span the content width;
on desktop, place details sit beside the sourced photo and its credit. The
public landing guide begins sooner and uses wider illustrated cards. Existing
guide SVGs and provider-attributed place photos supply the imagery; no new
unsourced image or decorative animation was needed.

Frontend check/build, `git diff --check`, and 18 mocked Playwright checks
passed; two duplicate mobile viewport sweeps were skipped. Screenshots at
390, 768, 1024 and 1440 px were inspected. The offline suite passed 246
tests with one optional PostgreSQL skip using test-only model names. Python
quality checks passed. No live Auth0, provider, owner-isolation or deployed
flow was exercised.

## Implemented update: React interface refresh — 2026-11-20

The public landing and authenticated planner now use clearer bilingual task
copy and a consistent visual hierarchy. Itinerary cards, chat, saved tours,
profile and administrator views reuse the existing blue palette, typography
and controls. Chat before a plan still accepts ordinary questions and explains
that a plan is needed to edit specific stops. On tablet and desktop, chat opens
from the sticky authenticated header; the phone keeps its floating control.
Source links, estimated durations and photo credits remain visible.

`npm run check`, `npm run build`, `git diff --check` and 16 Playwright checks
passed. Two duplicate mobile-project screenshot sweeps were intentionally
skipped. Mocked browser screenshots were reviewed at 390, 768, 1024 and 1440
px for overflow, obscured actions and reduced motion. Live Auth0, provider,
saved-tour ownership and deployed behavior were not exercised.

## Implemented update: public usage guide — 2026-11-19

The unauthenticated React landing page offers a bilingual five-step usage
guide before sign-in. It covers account entry, trip input, cited and estimated
information, chat changes and explicit tour saving. The guide stays within the
public landing view, with direct sign-in actions retained. Each step has a local
SVG illustration and restrained motion. Guide cards appear when they enter
the viewport. Users scroll to the guide without a guide jump button. Animation
respects reduced-motion settings.

The illustrated update passed `npm run check`, `npm run build`,
`git diff --check`, isort, Black, flake8 and Ruff. The offline suite passed 246
tests; one optional PostgreSQL test was skipped. Browser visual, mobile and
reduced-motion checks did not run because browser access was unavailable.

`npm run check`, `npm run build`, `git diff --check`, isort, Black, flake8 and
Ruff passed. The offline suite passed 246 tests; one optional PostgreSQL test
was skipped. Browser and live authentication checks did not run.

## Implemented update: itinerary and chat feedback — 2026-11-19

The React itinerary page uses plain Vietnamese and English progress text for
itinerary creation. Chat progress and submission errors stay in the chat
panel. Ordinary chat responses do not create an itinerary-page notice. A
committed or rejected chat itinerary change shows a short localized status on
the itinerary page without repeating the chat response.

`npm ci --offline`, `npm run check`, `npm run build` and `git diff --check`
passed. Browser QA did not run.

## Implemented update: authenticated view refresh — 2026-11-17

React stores saved-tour, profile and administrator views in the `view` query
parameter; itinerary remains at `/`. During the account check, the UI shows a
neutral loading state, then restores the view for an authenticated account.
Unauthenticated visitors see the public landing page, and non-admin accounts
cannot restore the administrator view. The plan and conversation rehydrate
from the same server session; trip data is not stored in the URL. Graph
inspection remains hidden and is not a product view.

`npm run check`, `npm run build` and `git diff --check` passed for PR #20.
Browser refresh QA and deployment remain pending; the active app uses another
checkout.

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
