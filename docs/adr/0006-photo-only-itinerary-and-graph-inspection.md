# ADR 0006 - Photo-Only Itinerary and Graph Inspection Page

Status: Accepted
Date: 2026-10-16
Supersedes: ADR 0005

## Context

The itinerary map and car marker introduced under ADR 0005 produced an
unhelpful geographic view for the user. The user explicitly requested removal
of the route map. The user also requested a separate page with an image of the
runtime graph to inspect its architecture.

## Decision

Keep source-attributed place photos as optional presentation data. Stop looking
up coordinates, remove the route map and car interaction, and retain the text
itinerary when a photo is unavailable. Visual lookups remain outside the
Coordinator/Planner graph and cannot change the canonical plan.

Add a read-only Streamlit page that calls
`TravelPlannerService.get_graph_image()` to render a PNG from the compiled
LangGraph workflow. Show conditional branches and the repair loop, and expose
the topology data for inspection. Loading the page must not invoke the workflow,
call model/search/tracing services, or mutate session plan state. If Mermaid PNG
rendering is unavailable, use the local SVG topology renderer as a fallback.
The graph image is an architecture diagram, not a geographic route.

## Consequences

- The itinerary UI has no map tiles, geocoding requests, route geometry or car
  animation.
- Public photo results still require creator, license and source-page credit.
- The separate page adds navigation without adding a runtime agent or a new
  application state store.

## Review Triggers

- The user requests a geographic map again with a clear interaction goal.
- The compiled graph or Streamlit page structure changes enough to make the
  diagram layout misleading.
