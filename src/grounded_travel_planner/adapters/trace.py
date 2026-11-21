"""Trace sinks with safe redaction and shared thread_id metadata."""

from collections.abc import Mapping
from threading import Lock
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

    def __init__(
        self, project_name: str | None = None, *, client: Any | None = None
    ) -> None:
        self._project_name = project_name
        self._client = client
        self._client_lock = Lock()

    @staticmethod
    def configure_private_client() -> Any:
        """Configure automatic LangChain traces to omit inputs and outputs."""

        from langsmith import Client
        from langsmith.run_trees import configure

        client = Client(hide_inputs=True, hide_outputs=True)
        configure(client=client)
        return client

    def _get_client(self) -> Any:
        if self._client is None:
            with self._client_lock:
                if self._client is None:
                    from langsmith import Client

                    self._client = Client(hide_inputs=True, hide_outputs=True)
        return self._client

    def record_event(
        self,
        name: str,
        payload: Mapping[str, Any],
        *,
        thread_id: str,
    ) -> None:
        safe_payload = redact_mapping(payload)
        try:
            client = self._get_client()
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
