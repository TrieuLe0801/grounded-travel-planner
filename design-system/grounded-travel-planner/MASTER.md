# Grounded Travel Planner Design System

Product UI uses an approachable, source-first travel-planning style. Follow
existing React/Tailwind components and tokens in `frontend/src/index.css`.

## Visual language

- Use blue `#2563eb` as the primary action color, light blue surfaces, white
  cards, and slate text.
- Use Lexend for headings and Source Sans 3 for body text.
- Use Lucide icons already provided by the app. Do not use emoji as icons.
- Keep gradients and shadows subtle. Do not add stock travel photography or
  imagery without source and license evidence.
- Keep one dominant action per view. Use the app's existing focus rings and
  reduced-motion behavior.

## Interaction

- Use semantic buttons and links with visible keyboard focus and clear labels.
- Keep pointer targets at least 44px high, with clear loading and error states.
- Design mobile-first. Avoid horizontal overflow and hover-only actions.
- Preserve the distinction between estimates, verified facts, and provider
  source data. Never imply booking, guaranteed hours, or unsupported routing.
- Keep the current itinerary and chat session-only. A saved tour is a separate,
  explicit, read-only snapshot.

## Travel journal composition

The interface uses an editorial travel-journal composition: a deep blue cover,
large destination headings, numbered day chapters and chronological stop markers.
Primary actions remain blue `#2563eb`; paper surfaces remain white/light blue
with slate text. The cover's `#172f56` background is a supporting blue tone, not
an alternative action color. Existing fonts and Lucide icons remain unchanged.

Use named component classes for the cover, departure form, day chapters and
saved-tour index. Abstract mountain/compass artwork is local decorative SVG,
hidden from assistive technology; it does not depict an actual destination or
route. It has no animation. Actual destination imagery still requires provider
source, creator and license credit. Never replace missing photos with this art.

The destination and date lead the itinerary cover. Revision is secondary;
explicit save stays adjacent. Day chapters retain full-width layouts and
chronological times; source and estimate labels stay with each stop. Saved
snapshots reuse this journal layout without editing or save controls.
