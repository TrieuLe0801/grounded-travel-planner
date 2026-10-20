# Grounded Travel Planner UI overlay

Use this overlay together with the upstream UI/UX Pro Max catalog when changing
this repository's interface. The product is a React/Tailwind webapp served by a
thin FastAPI adapter; Streamlit remains a supporting interface during the
migration.

## Product constraints

- Write user-facing chat and safe fallbacks in Vietnamese. Preserve proper place
  names, quoted requests and source titles as supplied.
- The itinerary shows source-backed place photos with attribution when available.
  Do not add a route map, vehicle animation or map-based click interaction: the
  user removed that experience.
- The graph page is read-only. Render the PNG returned by `get_graph_image()`;
  use the existing SVG endpoint only as a presentation fallback. Loading this
  page must not start a planning turn.
- Keep the floating chat available across itinerary and graph views. A pending
  session turn may continue through navigation, but the UI must show its pending
  state and integrate its result exactly once when available.
- Do not imply driving routes, verified opening hours or factual certainty that
  the runtime does not provide. Preserve estimated and unverified labels.

## Interaction and accessibility

- Support keyboard opening, focus and Escape-to-close for the chat panel.
- Keep visible focus states, semantic labels for icon controls and responsive
  layout without horizontal overflow. Respect reduced-motion preferences.
- Avoid UI changes that duplicate plan validation, source grounding or session
  state logic already owned by the runtime.

## Evidence rules

- Use the upstream catalog for design choices, then implement within the current
  React/Tailwind component and API boundaries.
- Describe typecheck/build/static evidence precisely. Claim browser, container
  or live-provider verification only after it has actually run.
- Preserve current user decisions unless a newer request changes them.
