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
