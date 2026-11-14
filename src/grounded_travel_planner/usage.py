"""Read account-attributed model usage and cost from LangSmith traces."""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
from collections.abc import Iterator, Mapping, Sequence
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Any

_account_ref: ContextVar[str | None] = ContextVar("account_trace_ref", default=None)
_EARLIEST_TRACE = datetime(1970, 1, 1, tzinfo=timezone.utc)
_SELECTS = [
    "ID",
    "RUN_TYPE",
    "START_TIME",
    "METADATA",
    "NAME",
    "PROMPT_TOKENS",
    "COMPLETION_TOKENS",
    "TOTAL_COST",
    "PRICE_MODEL_ID",
]


def account_trace_ref(account_id: str) -> str:
    """Make a stable opaque trace key from the random internal account UUID."""

    return hashlib.sha256(f"gtp-account-v1:{account_id}".encode()).hexdigest()


@contextmanager
def account_usage_context(account_id: str | None) -> Iterator[None]:
    """Bind a pseudonymous account key to the current model worker."""

    token = _account_ref.set(account_trace_ref(account_id) if account_id else None)
    try:
        yield
    finally:
        _account_ref.reset(token)


def current_account_trace_ref() -> str | None:
    return _account_ref.get()


@dataclass(frozen=True)
class UsageSummary:
    input_tokens: int = 0
    output_tokens: int = 0
    estimated_cost_usd: Decimal | None = None
    unpriced_calls: int = 0


class UsageError(RuntimeError):
    """LangSmith usage is unavailable or returned invalid data."""


class _Totals:
    def __init__(self) -> None:
        self.calls = 0
        self.input_tokens = 0
        self.output_tokens = 0
        self.cost = Decimal(0)
        self.unpriced_calls = 0

    def add(self, run: Any) -> None:
        input_tokens = run.prompt_tokens
        output_tokens = run.completion_tokens
        if any(
            not isinstance(value, int) or isinstance(value, bool) or value < 0
            for value in (input_tokens, output_tokens)
        ):
            return
        self.calls += 1
        self.input_tokens += input_tokens
        self.output_tokens += output_tokens
        raw_cost = run.total_cost
        if raw_cost is None or (
            raw_cost == 0 and getattr(run, "price_model_id", None) is None
        ):
            self.unpriced_calls += 1
            return
        try:
            cost = Decimal(str(raw_cost))
        except InvalidOperation as error:
            raise UsageError("Invalid LangSmith cost.") from error
        if not cost.is_finite() or cost < 0:
            raise UsageError("Invalid LangSmith cost.")
        self.cost += cost

    def summary(self) -> UsageSummary:
        return UsageSummary(
            input_tokens=self.input_tokens,
            output_tokens=self.output_tokens,
            estimated_cost_usd=(
                self.cost if self.calls and not self.unpriced_calls else None
            ),
            unpriced_calls=self.unpriced_calls,
        )


class UsageRepository:
    """LangSmith-backed account usage reader for administrator views."""

    def __init__(
        self, *, client: Any | None = None, project_name: str | None = None
    ) -> None:
        self._client = client
        self._project_name = project_name
        self._project_id: str | None = None

    @classmethod
    def from_environment(cls) -> UsageRepository:
        return cls(project_name=os.getenv("LANGSMITH_PROJECT"))

    def _client_or_raise(self) -> Any:
        if not self._project_name:
            raise UsageError("LANGSMITH_PROJECT is required for usage.")
        if self._client is None:
            if not os.getenv("LANGSMITH_API_KEY"):
                raise UsageError("LANGSMITH_API_KEY is required for usage.")
            from langsmith import Client

            # The SDK query uses an async HTTP client. Do not retain it across
            # separate asyncio.run loops used by synchronous FastAPI endpoints.
            return Client()
        return self._client

    def _project_id_or_raise(self, client: Any) -> str:
        if self._project_id is None:
            project = client.read_project(project_name=self._project_name)
            self._project_id = str(project.id)
        return self._project_id

    @staticmethod
    def _bounds(start: str | None, end: str | None) -> tuple[datetime, datetime]:
        try:
            lower = datetime.fromisoformat(start) if start else _EARLIEST_TRACE
            upper = datetime.fromisoformat(end) if end else datetime.now(timezone.utc)
        except ValueError as error:
            raise UsageError("Invalid usage date range.") from error
        if lower.tzinfo is None or upper.tzinfo is None:
            raise UsageError("Invalid usage date range.")
        return lower, upper

    async def _query(
        self,
        client: Any,
        project_id: str,
        refs: Sequence[str],
        lower: datetime,
        upper: datetime,
    ) -> list[Any]:
        filter_value = (
            f"eq(metadata_value, {json.dumps(refs[0])})"
            if len(refs) == 1
            else f"in(metadata_value, {json.dumps(list(refs))})"
        )
        pager = client.runs.query(
            project_ids=[project_id],
            run_type="LLM",
            filter=f'and(eq(metadata_key, "account_ref"), {filter_value})',
            min_start_time=lower,
            max_start_time=upper,
            page_size=1000,
            selects=_SELECTS,
        )
        if asyncio.iscoroutine(pager):
            pager = await pager
        return [run async for run in pager]

    def _runs_for_users(
        self,
        user_ids: Sequence[str],
        *,
        start: str | None,
        end: str | None,
    ) -> dict[str, list[Any]]:
        if not user_ids:
            return {}
        refs = {account_trace_ref(user_id): user_id for user_id in user_ids}
        lower, upper = self._bounds(start, end)
        if lower >= upper:
            return {user_id: [] for user_id in user_ids}
        try:
            client = self._client_or_raise()
            try:
                project_id = self._project_id_or_raise(client)
                queried = asyncio.run(
                    self._query(client, project_id, list(refs), lower, upper)
                )
            finally:
                if self._client is None:
                    client.close()
        except UsageError:
            raise
        except Exception as error:  # Keep provider error private.
            raise UsageError("LangSmith usage is unavailable.") from error
        grouped: dict[str, list[Any]] = {user_id: [] for user_id in user_ids}
        for run in queried:
            metadata = getattr(run, "metadata", None)
            if not isinstance(metadata, Mapping):
                continue
            user_id = refs.get(metadata.get("account_ref"))
            if user_id is None or getattr(run, "run_type", None) != "LLM":
                continue
            at = getattr(run, "start_time", None)
            if not isinstance(at, datetime) or at.tzinfo is None:
                continue
            if lower <= at < upper:
                grouped[user_id].append(run)
        return grouped

    def summary_for_users(
        self,
        user_ids: Sequence[str],
        *,
        start: str | None = None,
        end: str | None = None,
    ) -> dict[str, UsageSummary]:
        grouped = self._runs_for_users(user_ids, start=start, end=end)
        result: dict[str, UsageSummary] = {}
        for user_id, runs in grouped.items():
            totals = _Totals()
            for run in runs:
                totals.add(run)
            if totals.calls:
                result[user_id] = totals.summary()
        return result

    def detail_for_user(
        self, user_id: str, *, start: str | None = None, end: str | None = None
    ) -> list[dict[str, object]]:
        runs = self._runs_for_users([user_id], start=start, end=end)[user_id]
        return self._details(runs)

    def usage_for_user(
        self, user_id: str, *, start: str | None = None, end: str | None = None
    ) -> tuple[UsageSummary | None, list[dict[str, object]]]:
        """Return totals and model breakdown from the same LangSmith query."""

        runs = self._runs_for_users([user_id], start=start, end=end)[user_id]
        totals = _Totals()
        for run in runs:
            totals.add(run)
        return (totals.summary() if totals.calls else None, self._details(runs))

    @staticmethod
    def _details(runs: Sequence[Any]) -> list[dict[str, object]]:
        by_model: dict[tuple[str, str, str], _Totals] = {}
        for run in runs:
            metadata = run.metadata
            provider = str(metadata.get("ls_provider") or "unknown")
            model = str(metadata.get("ls_model_name") or run.name or "unknown")
            role = str(metadata.get("agent_role") or "unknown")
            totals = by_model.setdefault((provider, model, role), _Totals())
            totals.add(run)
        return [
            {
                "provider": provider,
                "model": model,
                "role": role,
                "calls": totals.calls,
                "input_tokens": totals.input_tokens,
                "output_tokens": totals.output_tokens,
                "unpriced_calls": totals.unpriced_calls,
                "estimated_cost_usd": totals.summary().estimated_cost_usd,
            }
            for (provider, model, role), totals in sorted(by_model.items())
            if totals.calls
        ]
