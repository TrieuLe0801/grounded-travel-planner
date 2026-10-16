# Visual Itinerary UI System

Source guidance: the project-local UI/UX Pro Max skill (`2.15.0`) and its
travel-itinerary design-system search. This document adapts that guidance to
the existing one-page Streamlit app; the generated landing-page storytelling
pattern and GSAP page transition are not used.

## Layout and tokens

- Keep the trip form, validated plan and chat in one readable column. Put the
  geographic view before the detailed day cards on a committed plan.
- Use a warm light surface (`#FFF7ED`), white cards, dark text (`#0F172A`),
  orange (`#EA580C`) for the selected stop/car and teal (`#0891B2`) for the
  chronological connector. Text labels accompany every state color.
- Body text stays at least 16 px with clear headings, 8 px spacing rhythm and
  wrapping place names/links. At 375 px, the map and stop controls stack without
  horizontal scrolling; desktop can show the map beside its stop list.
- Reserve image space with a stable aspect ratio and lazy load below the fold.
  Show creator, license and source-page links directly under an actual image.

## Map interaction

- Number stops exactly as `visible_schedule_entries` does. Only resolved
  coordinates appear as markers; a stop without coordinates remains in the
  itinerary with a clear map-unavailable note.
- The connector is a geographic sequence, not driving directions. Keep an
  OpenStreetMap attribution visible on the map.
- A marker and a labeled 44 px minimum button activate the same stop. Show
  visible focus and `aria-pressed` on the selected button.
- Clicking a stop moves one SVG car marker along the displayed connector.
  Repeated clicks cancel the prior motion and finish at the latest selection.
  `prefers-reduced-motion` and a visible motion toggle place the car immediately
  at the selected stop. The selected stop is also announced in text.
- If map scripts or tiles cannot load, retain the ordered stop list and source
  links; visual enrichment never blocks plan/chat.
