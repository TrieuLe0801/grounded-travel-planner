# LangSmith V2 Query Smoke — 2026-10-15

Status: Passed

The original `scripts/live_smoke.py` now uses the supported async
`Client.runs.query()` API instead of deprecated `list_runs()`. It resolves the
project ID, filters by the session `thread_id`, and reads `is_root` and
`thread_id` from each returned run. Offline fake-client tests cover the query
arguments and async iteration without making provider calls.

## Live result

Ran `uv run --env-file .env python scripts/live_smoke.py` after the migration.
The `gpt-5.5`/Tavily flow committed a Hue plan with five citations, five graph
steps, one search and no repairs. The v2 LangSmith query returned 25 runs:
seven root and 18 child. Every returned run had the same session `thread_id`.

This verifies the migrated query on the installed LangSmith SDK and the current
local project. It does not measure source editorial quality or the separate
two-turn chat-edit trace.
