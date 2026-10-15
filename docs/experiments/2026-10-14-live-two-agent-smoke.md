# Live Two-Agent Smoke — 2026-10-14

Status: Passed after two bounded integration fixes

## Scope

Executed `scripts/live_smoke.py` with the ignored local `.env`. The smoke used
the real OpenAI `gpt-5.5` model, Tavily search and LangSmith tracing for a
one-day Hue sightseeing request. Credential values were not printed, written to
tracked files or placed in prompts/trace metadata.

## Final result

- Outcome: `committed`.
- Model: `gpt-5.5` for Coordinator and Planner.
- Graph steps: 8 of 8 maximum.
- Tavily search calls: 1 of 2 maximum.
- Repair attempts: 1 of 1 maximum.
- Validation issues after repair: none.
- Returned citations committed to the plan: 5.
- LangSmith runs matching the smoke `thread_id`: 14.
  - Root runs: 4.
  - Child runs: 10.
  - `thread_id` metadata present on every matching run: true.
- Streamlit entrypoint started on `127.0.0.1:8512`; its health endpoint returned
  HTTP 200 with body `ok`, then the temporary server was stopped.

The five committed URLs originated from the live Tavily result set. They
included destination travel pages and one YouTube result. Provenance validation
passed, but domain quality/diversity ranking is a later evaluation concern.

## Defects found and fixed

1. A Tavily content snippet exceeded the typed 1,000-character boundary.
   The adapter now truncates title/snippet fields and skips malformed records.
2. OpenAI strict response-format validation rejected Pydantic's `HttpUrl`
   `format: uri`. The LangChain adapter now uses structured function calling,
   which `gpt-5.5` supports, and an offline regression test pins this behavior.
3. Search accounting now records an attempted external search even if a later
   Planner model step fails.

## Commands

```powershell
uv run --env-file .env python scripts\live_smoke.py
uv run pytest
```

Live smoke is intentionally separate from pytest; automated tests remain
offline and use injected fake model, search and trace providers.
