# ADR 0005 - Source-Backed Visual Itinerary

Status: Accepted
Date: 2026-10-16

## Context

The accepted two-agent runtime produces a validated text itinerary with source
references. The user wants place photos, a map of the itinerary, and a car that
moves to a selected stop. Search results do not currently contain reliable
image rights, coordinates or road-route geometry.

## Decision

Keep visual enrichment outside the canonical `SightseeingPlan` and the
Coordinator/Planner graph. A typed visual provider may look up public place
photos and coordinates after a plan is committed. Use Wikimedia Commons image
metadata with visible creator/license/file-page attribution. Use source-backed
coordinates from a matching Wikipedia article or OpenStreetMap Nominatim
result; reject ambiguous or out-of-range matches. Cache public lookup results
and bound calls. The Nominatim public endpoint must use an identifying
User-Agent, at most one request per second, and the required attribution.

Display mapped stops in chronological order on an OpenStreetMap-attributed map.
Until a routing provider returns actual road geometry, connect stops with
straight lines labeled as an illustrative sequence. On stop selection, animate
a car marker along the displayed connector, with keyboard controls and an
immediate final-position path for reduced-motion users. Missing or unavailable
photo/coordinate data produces a clear fallback without blocking plan/chat.

The project-local UI/UX Pro Max skill supplies design guidance; Streamlit
remains the app UI and no runtime agent is added.

## Consequences

- Visual HTTP calls are presentation-only and cannot become source evidence for
  plan validation or alter the canonical plan.
- Image availability, map tiles and public API limits affect presentation only.
- The map does not claim driving directions, travel distance or duration.
- Service policies, image licenses and attribution must be respected; a broader
  deployment would require a capacity review or different visual providers.

## Review Triggers

- A road-routing API or map-provider key is introduced.
- Visual data is persisted or shared between user sessions beyond public
  lookup caching.
- Public geocoding/tile usage grows beyond the documented low-volume limits.
