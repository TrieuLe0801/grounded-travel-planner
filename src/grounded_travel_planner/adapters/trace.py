"""Trace sinks with safe redaction and shared thread_id metadata."""

import re
from collections.abc import Mapping
from datetime import datetime, timezone
from threading import Lock
from typing import Any
from uuid import uuid4

from grounded_travel_planner.providers import TraceSink
from utils.redaction import redact_mapping

# Arbitrary long strings include account hashes and source/thread identifiers.
# Only recognizable credential prefixes are safe to redact from free text.
_CREDENTIAL_PATTERN = re.compile(r"(?i)(?:sk-|tvly-|bearer\s+)[A-Za-z0-9._-]{8,}")

_CREDENTIAL_FIELDS = frozenset(
    {
        "api_key",
        "apikey",
        "access_token",
        "refresh_token",
        "id_token",
        "authorization",
        "password",
        "secret",
        "client_secret",
        "token",
        "credentials",
    }
)


def redact_trace_content(value: Any) -> Any:
    """Keep complete trace content while removing recognizable credentials."""

    if isinstance(value, Mapping):
        return {
            key: (
                "[REDACTED]"
                if str(key).lower() in _CREDENTIAL_FIELDS
                else redact_trace_content(item)
            )
            for key, item in value.items()
        }
    if isinstance(value, (list, tuple)):
        return [redact_trace_content(item) for item in value]
    if isinstance(value, str):
        return _CREDENTIAL_PATTERN.sub("[REDACTED]", value)
    return value


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
    def configure_client() -> Any:
        """Configure visible LangChain inputs and outputs with secret redaction."""

        from langsmith import Client
        from langsmith.run_trees import configure

        client = Client(
            hide_inputs=False, hide_outputs=False, anonymizer=redact_trace_content
        )
        configure(client=client)
        return client

    def _get_client(self) -> Any:
        if self._client is None:
            with self._client_lock:
                if self._client is None:
                    from langsmith import Client

                    self._client = Client(
                        hide_inputs=False,
                        hide_outputs=False,
                        anonymizer=redact_trace_content,
                    )
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
            run_id = uuid4()
            client.create_run(
                id=run_id,
                name=name,
                run_type="chain",
                inputs=safe_payload,
                project_name=self._project_name,
                extra={"metadata": {"thread_id": thread_id}},
            )
            client.update_run(
                run_id, outputs={"ok": True}, end_time=datetime.now(timezone.utc)
            )
        except Exception:  # noqa: BLE001 - observability must not break planning
            return
