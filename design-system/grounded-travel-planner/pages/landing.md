# Public Landing Page

This page introduces the planner and gates the private itinerary workspace on
verified sign-in.

## Layout

- Keep the first screen short and calm: brand, language control, a concise
  description of the sightseeing app and its purpose, product benefits, and
  separate sign-in and registration actions.
- Keep SSO, email-code, and other authentication mechanics out of the app
  description. Use Auth0 for both actions; the registration action requests
  Auth0's signup screen. Do not add a local password form or collect profile
  fields in the app.
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
- Give sign-in the primary visual treatment and registration a clear secondary
  treatment. Keep visible focus, keyboard access, and a responsive layout
  without horizontal overflow.
