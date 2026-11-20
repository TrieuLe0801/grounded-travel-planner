# Public Landing Page

This page introduces the planner and gates the private itinerary workspace on
verified sign-in.

## Layout

- Keep the first screen short and calm: brand, language control, a concise
  description of the sightseeing app and its purpose, product benefits, and
  separate sign-in and registration actions.
- Offer a bilingual usage guide from the landing view before sign-in. Explain
  trip setup, source and estimate labels, chat changes, and explicit saving.
  Users scroll below the introduction to see the guide; do not add a guide jump
  button. Use local, decorative SVG illustrations for the five steps. Keep
  direct sign-in and registration actions easy to reach.
- Keep SSO, email-code, and other authentication mechanics out of the app
  description. Use Auth0 for both actions; the registration action requests
  Auth0's signup screen. Do not add a local password form or collect profile
  fields in the app.
- Use the existing blue palette, Lexend headings, Source Sans 3 body, and Lucide
  icons. Do not add scroll-triggered storytelling or unsourced travel photos.
- Use restrained entrance animation when guide cards enter the viewport, only
  when reduced motion is not requested.
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

## Exploration redesign

Use a deep blue editorial cover with a concise exploration heading, factual
product description, source/chat benefits and local decorative landscape and
compass artwork. The artwork is abstract, not a representation of a real place.
The sign-in card remains a separate white surface with the existing direct
Google, email/password, registration and email-code actions. On phones it comes
first, preserving sign-in access in the initial viewport.

The guide reads as five numbered chapters on paper cards. Keep all five local
SVG illustrations and bilingual explanations. Chapter numbers and generous
spacing provide hierarchy; avoid fabricated itinerary previews or destination
recommendations. Existing reduced-motion-aware guide entry behavior remains.
