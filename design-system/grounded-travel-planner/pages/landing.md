# Public Landing Page

This page introduces the planner and gates the private itinerary workspace on
verified sign-in.

## Layout

- Keep the first screen short and calm: brand, language control, headline,
  grounded-planning benefits, and one prominent sign-in action.
- State that Auth0 sends a one-time code by email. Do not add a local password
  form or collect profile fields before sign-in.
- Explain that a live trip stays in the browser session and only an explicit
  save stores a read-only tour snapshot.
- Use the existing blue palette, Lexend headings, Source Sans 3 body, and Lucide
  icons. Do not add scroll-triggered storytelling or unsourced travel photos.
- Keep Vietnamese default and English selectable. Carry the selected locale
  through the Auth0 return URL and apply it to the authenticated session.

## Access and feedback

- Do not request planner session state until `/api/auth/me` confirms an
  authenticated account.
- Show a clear loading state while checking sign-in and a retryable error if
  the account endpoint fails.
- After sign-in, display the verified email, saved tours, and sign-out in the
  account menu.
- Use one primary CTA, visible focus, keyboard-accessible controls, and a
  responsive layout without horizontal overflow.
