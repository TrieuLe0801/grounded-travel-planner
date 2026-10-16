# Visual Itinerary Verification — 2026-10-16

Status: Historical map/car experiment. The user requested removal of the route
map later on 2026-10-16; ADR 0006 describes the current photo-only itinerary
and separate graph-inspection page. The checks below remain historical evidence.

## Implemented scope

- Project-local UI/UX Pro Max skill `2.15.0` installed under
  `.codex/skills/ui-ux-pro-max/` with its MIT license and source note. Its
  accessibility, responsive layout and reduced-motion guidance was adapted in
  `docs/ui-visual-itinerary.md`.
- Presentation-only enrichment looks up a bounded set of place images from
  Wikimedia Commons and coordinates from matching Wikipedia pages or
  OpenStreetMap Nominatim. Commons credit, license and file-page links are
  shown next to the image. Missing data does not change the current plan.
- The map numbers resolved stops in canonical chronological order and labels
  straight connectors as illustrative, not road directions. Clicking a marker
  or a labeled stop button moves an SVG car; a motion toggle and system reduced
  motion preference immediately place it at the selected stop.

## Verification

- `uv run pytest`: 48 passed on the host after the visual tests were added.
- isort, Black, flake8, Ruff, `uv lock --check` and `git diff --check` passed.
- Docker test target passed 48/48 on Linux/Python 3.10.22 after the test stage
  copied the versioned eval data and `scripts/live_smoke.py` it needs.
- Compose runtime rebuilt; health endpoint returned HTTP 200 with body `ok`.
- Live public lookups in the running container returned a Commons image with
  creator/license and a Wikipedia coordinate for both Imperial City and Thien
  Mu Pagoda in Hue. A host lookup returned a Commons image for Lô Lô Chải but
  no precise matching coordinate, so that stop correctly remains off the map.
- The generated map JavaScript passed `node --check`. A temporary fake-DOM and
  fake-Leaflet execution confirmed button click moves the car to stop 2,
  reduced motion places it at stop 1 immediately, and a rapid later click
  cancels the earlier destination. The temporary test files were removed.

## Limits

The visual service looks up at most 12 stops per plan to bound external calls;
additional stops remain visible in the text itinerary. Public image, geocoding,
tile and Leaflet assets need network access. No browser surface was available
to the agent for a screenshot or real pointer/keyboard interaction, so map tile
rendering and animation have not been visually inspected in a real browser.
No actual road-routing geometry, driving distance or driving duration is
claimed.
