# Live Chat Edit Smoke — 2026-10-15

Status: Passed

## Scope

Ran `scripts/live_chat_edit_smoke.py` with the ignored local `.env` and the
configured live OpenAI, Tavily and LangSmith adapters. The script creates a
one-day Hue plan and sends a follow-up chat request to remove the first place,
passing the previous plan and the same session `thread_id` to the service.

## Result

- Final create turn: committed revision 1 with five entries.
- Final chat edit: committed revision 2 with four entries.
- The requested entry ID was absent and all other entry IDs remained in the
  revised plan.
- Edit turn: five graph steps, zero searches, zero repairs and no validation
  issues.
- The edit response carried the same session `thread_id`.
- Graph, search and repair counts stayed within configured limits.

The final smoke was rerun after the repair-provenance fix. It confirms a live
successful chat edit through the service. It does not
inspect LangSmith's stored runs for this two-turn session or exercise the
Streamlit browser; offline tests cover the Streamlit interaction separately.

## Command

```powershell
uv run --env-file .env python scripts/live_chat_edit_smoke.py
```

The script prints counts, statuses and issue codes only; it does not print
credentials, source URLs or prompts.
