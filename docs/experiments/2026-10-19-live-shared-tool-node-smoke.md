# Live Shared Tavily Tool Node Smoke — 2026-10-19

The explicit smoke script exercised the current compiled graph and the shared
`tavily_tool` node with a current-information question about the Imperial
Citadel in Hue. It prints event names and result counts only, not credentials,
search query, response text or source URLs.

Command:

```powershell
uv run python scripts/live_chat_search_smoke.py
```

Observed result:

- Chat requested one Tavily search and received five provider sources.
- The turn remained `unchanged`; the graph did not create or modify a plan.
- LangSmith returned `tool.tavily.start` and `tool.tavily.success` events.
- All returned trace runs carried the same `thread_id` as the request.
- The smoke script reported `verified: true`.

This confirms one live request through the shared graph tool, not broad factual
accuracy, opening-hour verification or source relevance.
