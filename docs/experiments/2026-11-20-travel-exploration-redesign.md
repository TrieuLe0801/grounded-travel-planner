# Travel and exploration interface redesign

## Request and goal

On 2026-11-20, the user requested research and implementation of a travel and
exploration style for the user interface. The goal is a visibly distinct travel
guide composition across the public landing, trip setup, itinerary, archive and
chat, while preserving existing product behavior. After acceptance, the user
explicitly requested a commit, push, pull request to `main` and worktree cleanup.
Merge and deployment remain outside this request.

## Research and design brief

The existing interface presents large text blocks and repeated blue cards.
Baseline screenshots show a clear functional interface but little sense of
discovery. Two first-party travel references informed content organization:

- [Lonely Planet destinations](https://www.lonelyplanet.com/destinations)
  organizes discovery around destinations and city guides.
- [Visit Norway trip planning](https://www.visitnorway.com/plan-your-trip/)
  groups practical planning information by traveler task.

These references support destination hierarchy and practical grouping, not a
claim that their visual assets or layouts have been reproduced. No external
photography, package or unsupported travel recommendation is needed.

The selected direction is an exploration guide: an editorial landing, a
distinct trip preparation form, destination-led itinerary headings, chapter-like
days and chronological stop cards. Retain the established blue/white/slate
palette, Lexend and Source Sans 3, Lucide icons and all five local guide SVGs.
Decorative compass treatments do not represent an actual route or destination.

## Preservation and acceptance

- Keep Google, password, registration and email-code actions, language controls,
  skip link and all five guide steps. Primary sign-in remains visible at 390×844.
- Keep destination, localized in-app date picker, ISO API dates, 1–7 day count,
  validation and pending feedback.
- Keep explicit save, reset confirmation, keyboard day navigation, time ranges,
  estimates, unverified-hours labels, sources and photo creator/license credits.
- Keep ordinary chat, edit examples, focus, errors, pending work and locale
  switching without losing session state.
- Keep saved snapshots read-only and preserve archive/account actions.
- Check phone, tablet and desktop at 390, 768, 1024 and 1440 px; review screenshots
  and run frontend type/build and mocked Playwright checks. Live Auth0, providers,
  storage ownership and deployment require separate evidence.

## Baseline

Branch `feat/redesign-ui`, baseline revision `e9f1f50`, clean worktree before
implementation. Initial browser command could not find Playwright; installing
the existing lockfile with `npm ci --offline` resolved the missing dependencies.
`npm run test:browser` then passed 32 checks and skipped two duplicate mobile
viewport sweeps. Baseline artifacts were copied to
`/tmp/gtp-redesign-baseline/` before editing; these are local temporary artifacts.
The desktop landing screenshot was inspected directly.

## Implementation and verification

Implementation updates `frontend/src/main.tsx`, `index.css` and `i18n.ts`, with
the visual rules recorded in the two existing design-system documents. The
landing has a deep blue editorial cover and static, decorative local SVG art.
Trip setup uses a departure form; itinerary headings and day numbers use a
travel-journal hierarchy. The saved index and chat share the same treatment.
Existing event handlers and provider integrations are unchanged.

### Verification results

- Passed: `cd frontend && npm run check` and `npm run build`, independently
  executed by Tester after implementation.
- Passed: `cd frontend && npm run test:browser`: 34 passed, two skipped in the
  final run (18.7 seconds). The skips are duplicate mobile viewport sweeps;
  the desktop project exercises all four target widths.
- Passed: `git diff --check` and progress JSON parsing.
- Not run: Python pytest/isort/Black/flake8/Ruff, because no Python code or
  configuration changed. Live Auth0, provider, database ownership and deployed
  acceptance were not run; browser API responses are mocked.

Tester independently ran the initial 32-test suite and added regression checks
for read-only saved detail, source/photo credit preservation, chat input focus
and Escape, plus English landing screenshots. Tester then hit its usage limit.
The primary session completed the final test run and visual review. One chat
screenshot caught the opening animation mid-frame; the supplemental capture now
requests reduced motion and shows the settled panel. No product fix was needed.

Screenshots are generated under `frontend/test-results/` for landing and
itinerary at 390, 768, 1024 and 1440 px, English landing, Vietnamese setup,
saved detail and open chat. These local artifacts are overwritten by test runs.
Direct review included landing at tablet/desktop widths and English phone,
itinerary at phone/desktop, saved detail desktop and chat phone. Compared with
the baseline, the dark editorial cover, local landscape art, clearer destination
hierarchy and numbered chapters give the requested travel-guide identity.
Reviewed controls and text remain readable; sources and photo credits remain
visible. The flat blue photo is deliberately mocked test data, not an app photo.

The five-step guide remains long on mobile by design, preserving the existing
illustrations and instructions. No acceptance-blocking visual defect was found
in the reviewed states. This is not a blanket accessibility or live-product
certification. No deployment was performed. Publication follows the user's
subsequent commit, push and pull-request instruction.
