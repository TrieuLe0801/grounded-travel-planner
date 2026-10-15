"""Trace sinks with safe redaction and shared thread_id metadata."""

from collections.abc import Mapping
from typing import Any

from grounded_travel_planner.providers import TraceSink
from utils.redaction import redact_mapping


class NoOpTraceSink(TraceSink):
    def record_event(
        self,
        name: str,
        payload: Mapping[str, Any],
        *,
        thread_id: str,
    ) -> None:
        return None


class LangSmithTraceSink(TraceSink):
    """Best-effort LangSmith event sink; failures never affect app state."""

    def __init__(self, project_name: str | None = None) -> None:
        self._project_name = project_name

    def record_event(
        self,
        name: str,
        payload: Mapping[str, Any],
        *,
        thread_id: str,
    ) -> None:
        safe_payload = redact_mapping(payload)
        try:
            from langsmith import Client

            client = Client()
            run = client.create_run(
                name=name,
                run_type="chain",
                inputs=safe_payload,
                project_name=self._project_name,
                extra={"metadata": {"thread_id": thread_id}},
            )
            client.update_run(run.id, outputs={"ok": True})
        except Exception:  # noqa: BLE001 - observability must not break planning
            return
