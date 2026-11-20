---
name: travel-planner-browser-evaluation
description: Test and evaluate Grounded Travel Planner browser flows with Playwright, recording observable results and limits.
---

# Browser testing and evaluation

Use this project-authored skill when acceptance requires a browser interaction,
responsive or accessibility check, or evaluation of a live user flow. Read
`AGENTS.md`, the accepted Goal Card, relevant charter and UI contracts, then
inspect the affected page and API path. Tester owns routine verification.

## Playwright workflow

1. For deterministic UI regressions, add a focused test under
   `frontend/tests/browser/`. Mock external providers and API responses at the
   browser boundary. Use role/label locators and assertions on visible behavior.
2. Run `npm run test:browser` from `frontend/`. Its config starts the local Vite
   server, runs desktop and mobile Chromium projects, and retains screenshots
   and traces for failures. Run `npx playwright install chromium` first if the
   browser binary is absent. Do not claim a check passed from a test listing.
3. For live Auth0, saved-tour, or provider evaluation, use the actual deployed
   app and an authorized test account. Record target URL, revision, browser,
   scenario, expected and observed result. Keep live credentials and session
   artifacts out of Git; treat traces as sensitive because they can contain
   page and network data. Never use mocked results as live acceptance evidence.
4. For source or Chat quality, Playwright may drive and capture the UI, but
   score factual correctness against independent source evidence and the
   project's evaluation criteria. A screenshot alone cannot establish source
   relevance, answer accuracy, or LangSmith tracing.

For visual acceptance, capture and inspect rendered pages at representative
phone, tablet, and desktop widths (for example 390, 768, 1024 and 1440 px).
Review alignment, overflow, missing images, long localized copy, contrast,
focus, loading/error states, and reduced motion. Use Playwright assertions for
repeatable failures and explain any judgment based on screenshot inspection.

Report each check as passed, failed, skipped, or not run, with exact command,
target, result, and reason for every non-pass. Browser success does not prove
backend validation, provider quality, owner isolation, or deployment unless
those behaviors were actually exercised and observed.

## Design preservation checks

For redesign or polish, compare the changed surface with the pre-change
inventory supplied by Coordinator: links, fields, handlers, navigation, focus,
and content obligations. Exercise affected actions; visual similarity alone
cannot prove preservation. Compare before/after screenshots at matching viewport,
locale and state. If no baseline exists, state that limit explicitly.

Use the existing 390, 768, 1024 and 1440 px cases where applicable. Include long
Vietnamese/English labels, empty and populated itineraries, missing photos,
pending turns and error recovery when affected. Verify first-viewport sign-in,
keyboard day navigation, explicit save and source/photo labels when those
surfaces change. Check focus is not obscured by sticky or floating controls.

Independently assess the UI brief. Separate contract/accessibility failures
that block acceptance from design concerns requiring a reasoned decision and
optional finishing suggestions. Record the visible impact and artifact for
each finding; no numeric quality score or pass claim without observed evidence.
