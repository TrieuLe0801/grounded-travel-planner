---
name: travel-planner-ui
description: Design or change the Grounded Travel Planner interface using its local product, accessibility, and evidence rules. Use for React/Tailwind or retained Streamlit UI work.
---

# Grounded Travel Planner UI

Use this skill for product interface changes. Read `AGENTS.md`, the relevant
charter sections and accepted UI ADRs first. Inspect the existing component and
API flow before changing presentation.

## Scope and design brief

Choose the scope from the request: an audit reports findings without edits;
polish improves the named surface within its current layout; redesign changes
the requested layout while preserving product behavior. Do not turn a component
fix into a page redesign. Infer routine choices from project evidence; ask only
when missing information changes scope or acceptance.

Planner records a compact brief: affected view and files, user task, primary
action, existing components/tokens to reuse, real content available, missing
facts, and observable acceptance. Cite the relevant source paths. Inventory
links, fields, handlers, navigation, focus behavior and loading/error/empty
states before changing the surface. For a redesign, include baseline screenshots
when the app can run; report their absence rather than inventing a baseline.

Use the current itinerary as the workspace's main content. Keep trip identity,
day navigation, explicit save, sources and estimates easy to scan. Preserve the
landing's direct sign-in actions and five local SVG guide steps. Do not force
marketing-page compositions or word limits onto itinerary data and controls.

## Product boundaries

- React/Tailwind is the current product UI with a thin same-origin FastAPI
  adapter. Streamlit remains a supporting migration interface. Keep itinerary
  rules, source grounding and canonical state in Python.
- Vietnamese is the default; English is selectable. Keep locale in the session,
  capture it when a turn starts, and preserve in-flight work during a language
  switch. Keep dates in ISO form in APIs and localize their display.
- The public landing page is the only anonymous product view. Check the
  authenticated account before requesting planner state. Never put provider
  tokens in browser storage.
- Home and New Trip begin a fresh live trip while preserving language, account
  and saved tours. Ask for confirmation before discarding an existing plan.
- Keep the live plan and conversation session-only. Saving is explicit and
  creates an immutable, read-only tour snapshot with its original sources.
- Keep the graph inspection view out of product navigation and read-only.
  Preserve the user's removal of route maps and vehicle animation.
- Preserve source attribution, estimated durations and unverified-hours labels.
  Do not imply booking, guaranteed opening hours or unsupported travel routes.
- Keep localized feedback as stable catalog keys and resolve it during render;
  changing language must update visible errors and statuses without resetting
  the plan or pending work.
- Keep the React trip-start calendar in-app and localize its month, weekdays and
  controls. Browser-native date labels follow browser locale. Send date values
  as ISO strings.

## Local design and interaction

- Follow `design-system/grounded-travel-planner/MASTER.md` when present. For
  landing changes, also read `design-system/grounded-travel-planner/pages/landing.md`.
- Reuse existing React components, CSS tokens, Lucide icons and loading/error
  patterns. Do not add a design system, package, stock image or new visual
  language when the current one supports the task.
- Use browser/platform controls only when they meet locale and accessibility
  requirements. Keep the trip-start calendar in-app because native date labels
  follow the browser locale.
- Keep layouts mobile-first, without horizontal overflow. Use semantic controls,
  visible focus, keyboard access, reduced-motion behavior and pointer targets of
  at least 44px.
- Keep chat available across itinerary and saved-tour views. A pending result
  stays session-owned and integrates exactly once after navigation.
- Treat saved-tour details as read-only. Keep owner-scoped pages bounded and
  follow API pagination rather than loading the full archive in the browser.

## Design pass

- Start with the user's task, the page's main action, and the real content it
  must show. Write concise Vietnamese and English copy before polishing layout;
  headings should name the task or object, and actions should say what happens.
- Show the actual planner interface, source labels, estimates, and saved-tour
  behavior when describing the product. Avoid decorative mock data, placeholder
  claims, and imagery presented as a real place without source and license
  evidence. Preserve visible source and photo credits required by the charter.
- Use one coherent layout grid and the existing type, color, spacing, and
  control styles. Give each section a clear purpose and keep content edges
  aligned; adapt section height to content rather than forcing a fixed screen.
- Add motion only when it clarifies entry, feedback, or state. Keep controls
  responsive to hover, press, and keyboard focus; all content remains visible
  with reduced motion and without hover. Do not add shader, scroll scene, or
  animation package just to decorate a travel page.
- Inspect the rendered page over HTTP at phone, tablet, and desktop widths
  when visual acceptance is in scope. Review screenshots as well as automated
  assertions for clipped content, empty visuals, misaligned edges, contrast,
  long translated copy, and loading or error states. Fix observed failures
  before reporting the UI ready.

## Review and handoff

Coordinator hands Tester the brief, changed paths, before/after interaction
inventory, and states that need browser checks. Reuse existing Playwright
fixtures before adding coverage. An audit must distinguish observed defects
from suggestions; a screenshot does not establish that a control works.

- Acceptance blockers: broken actions, lost content or source credits, invented
  claims, unreadable contrast, inaccessible focus, clipped controls, or violated
  session/locale/save contracts. Fix and verify these before claiming readiness.
- Design concerns: weak hierarchy, repetitive wrappers, competing actions or
  decoration without a task purpose. Explain the user impact and proposed fix;
  retain a deliberate pattern when project content justifies it.
- Finishing suggestions: minor spacing or typographic refinements beyond the
  requested acceptance. Report separately; do not expand scope to chase taste.

Keep new styling within the existing token vocabulary. Fix overflow at its
layout cause; never hide a broken layout with page-wide clipping. Prefer explicit
transition properties and inexpensive motion with reduced-motion fallback.
Tester reviews independently against the brief and product contracts, compares
matching states and viewports, and reports unresolved findings with evidence.

## Evidence

Run only the checks required by the user request and project acceptance. Report
static, frontend-build, browser, container and live-provider evidence
separately. Claim browser behavior only after browser interaction; claim a
deployed change only after checking the running image.
For browser behavior or visual evaluation, follow
`.codex/skills/travel-planner-browser-evaluation/SKILL.md` and use Playwright.
