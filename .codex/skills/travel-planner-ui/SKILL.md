---
name: travel-planner-ui
description: Design or change the Grounded Travel Planner interface using its local product, accessibility, and evidence rules. Use for React/Tailwind or retained Streamlit UI work.
---

# Grounded Travel Planner UI

Use this skill for product interface changes. Read `AGENTS.md`, the relevant
charter sections and accepted UI ADRs first. Inspect the existing component and
API flow before changing presentation.

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

## Evidence

Run only the checks required by the user request and project acceptance. Report
static, frontend-build, browser, container and live-provider evidence
separately. Claim browser behavior only after browser interaction; claim a
deployed change only after checking the running image.
