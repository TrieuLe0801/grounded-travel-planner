# Live Chat Tavily Search Smoke — 2026-10-19

Historical smoke for the pre-ADR-0012 version, when Chat performed the provider
call inside its agent method and emitted `chat.search.*` events. The current
shared graph-tool smoke is recorded in
`docs/experiments/2026-10-19-live-shared-tool-node-smoke.md` and emits
`tool.tavily.*` events.

The explicit script `scripts/live_chat_search_smoke.py` exercised the active
Chat response path with a current-information question about the opening hours
of the Imperial Citadel in Hue. The script reports counts and trace metadata
only; it does not print credentials, raw search query, response text or source
URLs.

Command:

```powershell
uv run python scripts/live_chat_search_smoke.py
```

Observed result:

- Chat selected one Tavily search and received five provider sources.
- The turn remained `unchanged`; Chat did not create or mutate a plan.
- LangSmith contained both `chat.search.start` and `chat.search.success` events.
- The trace runs returned for the turn carried its same `thread_id`.
- The smoke script reported `verified: true`.

This confirms the live Chat/Tavily/LangSmith path for one ordinary factual
question. It does not establish broad answer accuracy, source relevance or
opening-hour verification; those still require representative evaluation.
