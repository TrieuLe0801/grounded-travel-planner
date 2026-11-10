# Vietnamese Chat Smoke — 2026-10-16

Status: Passed for one live add-place turn and offline UI/fallback coverage.

## Scope

The webapp now uses Vietnamese for form/chat labels and its generated create
request. Coordinator accepts Vietnamese user requests and is instructed to
reply in Vietnamese; Planner is instructed to write user-visible itinerary
text in Vietnamese while retaining place names and source titles. Deterministic
fallback responses are also Vietnamese.

## Verification

- `uv run pytest`: 40 passed, including an AppTest with Vietnamese create,
  successful edit and rejected edit messages, plus a Vietnamese ordinary-chat
  fallback test.
- isort, Black, flake8, Ruff, `uv lock --check` and `git diff --check` passed.
- The locked runtime image rebuilt and the Compose app became healthy.
- Ran `scripts/live_lo_lo_chai_smoke.py` inside the container with a Vietnamese
  add request. Coordinator returned `add_place` for Lô Lô Chải; Planner used
  one search, no repair, and committed revision 2 while preserving the old
  stop. The assistant's live reply was in Vietnamese.

The live run exercises the service used by Streamlit with a newly sourced
test plan. It does not replay the user's earlier session or automate a browser
chat interaction. Source titles retain their original language.
