# Lô Lô Chải Add-Place Regression — 2026-10-15

Status: Offline fix verified; representative live edit passed on 2026-10-16.

## Reported behavior

The webapp rejected an add-place chat request with
`requested_change_not_applied` and kept the previous itinerary. The rejected
candidate itself is session-only and was not available for inspection. The
previous validator compared place names with exact casefolded text, so a
candidate named `Lo Lo Chai Village` would fail a request for `Lô Lô Chải`.

## Change

- Compare place names after Unicode accent normalization and allow generic
  village/hamlet descriptors around a multiword name.
- Require the number of matching places to increase while retaining the
  existing places; changing entry IDs alone does not invalidate an add.
- Ask Planner to keep the requested place name exactly and put alternate
  spellings in the description.
- Keep schedule, source-provenance and opening-hours checks unchanged.

## Verification

- The regression test accepts `Lô Lô Chải` → `Lo Lo Chai Village`, rejects
  `Lo Lo Chai Market`, and rejects a candidate that drops an existing stop.
- `uv run pytest`: 39 passed; isort, Black, flake8, Ruff, `uv lock --check` and
  `git diff --check` passed.
- The normal runtime image rebuilt and Compose reported healthy. The host
  health endpoint and Streamlit page each returned HTTP 200. A check inside the
  running container confirmed the accented alias matches.
- A separate Docker test-target rebuild was blocked by intermittent Docker Hub
  DNS resolution; the host test suite above completed.

The live add-place probe reached Coordinator but OpenAI returned HTTP 429 with
`billing_not_active` before classification. It made no Planner search or plan
mutation. Re-run a live add request after the model account is active to
determine whether the reported itinerary succeeds end to end.

Follow-up: the representative live add-place flow passed in the running
container on 2026-10-16. See `2026-10-16-live-lo-lo-chai-add.md`. The original
user's session was not available for an exact replay.
