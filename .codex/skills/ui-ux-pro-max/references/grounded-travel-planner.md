# Grounded Travel Planner UI overlay

Use this overlay together with the upstream UI/UX Pro Max catalog when changing
this repository's interface. The product is a React/Tailwind webapp served by a
thin FastAPI adapter; Streamlit remains a supporting interface during the
migration.

## Product constraints

- Vietnamese is the default UI and assistant language; English is also
  selectable. Keep that preference in the current session and apply changes to
  future turns without resetting itinerary, conversation or pending work.
- Keep user messages, proper place names, quoted requests and source titles as
  supplied. Do not translate source evidence or existing conversation content
  when the user changes the UI language.
- The itinerary shows source-backed place photos with attribution when available.
  Do not add a route map, vehicle animation or map-based click interaction: the
  user removed that experience.
- The graph inspection page is hidden from product navigation. Keep its
  rendering and diagnostic endpoints read-only.
- Keep the floating chat available across itinerary and saved-tour views. A
  pending session turn may continue through navigation, but the UI must show
  its pending state and integrate its result exactly once when available.
- Save a tour only after the user explicitly chooses to save the validated
  current plan. Saved-tour detail is a read-only snapshot; show original source
  references and the stale-facts notice. Keep owner-scoped list pages bounded
  and use the API continuation cursor instead of client-side full-history loads.
- Keep live conversation and itinerary session-only. A new app session may still
  show saved tours owned by the same browser; do not imply account sync.
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
