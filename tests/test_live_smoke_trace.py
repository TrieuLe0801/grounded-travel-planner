"""Offline checks for the supported LangSmith query used by the live smoke gate."""

from __future__ import annotations

import asyncio
import runpy
import sys
from pathlib import Path
from types import SimpleNamespace

SMOKE = runpy.run_path(Path("scripts/live_smoke.py"))
CHAT_SEARCH_SMOKE = runpy.run_path(Path("scripts/live_chat_search_smoke.py"))
query_thread_runs = SMOKE["_query_thread_runs"]
summarize_thread_runs = SMOKE["_summarize_thread_runs"]


class FakePager:
    def __init__(self, runs: list[SimpleNamespace]) -> None:
        self._runs = runs

    def __aiter__(self):
        async def iterate():
            for run in self._runs:
                yield run

        return iterate()


class FakeRuns:
    def __init__(self, pager: FakePager) -> None:
        self.pager = pager
        self.query_kwargs: dict[str, object] | None = None

    def query(self, **kwargs: object) -> FakePager:
        self.query_kwargs = kwargs
        return self.pager


def test_live_smoke_uses_v2_runs_query_for_thread() -> None:
    thread_id = "thread-123"
    fake_runs = FakeRuns(
        FakePager(
            [
                SimpleNamespace(is_root=True, thread_id=thread_id),
                SimpleNamespace(is_root=False, thread_id=thread_id),
            ]
        )
    )
    client = SimpleNamespace(
        read_project=lambda *, project_name: SimpleNamespace(id="project-456"),
        runs=fake_runs,
    )

    runs = asyncio.run(query_thread_runs(client, "travel-planner", thread_id))

    assert runs == fake_runs.pager._runs
    assert fake_runs.query_kwargs == {
        "project_ids": ["project-456"],
        "filter": 'eq(thread_id, "thread-123")',
        "page_size": 100,
        "selects": ["IS_ROOT", "THREAD_ID"],
    }
    assert summarize_thread_runs(runs, thread_id) == {
        "run_count": 2,
        "root_count": 1,
        "child_count": 1,
        "thread_metadata_on_all": True,
    }


def test_live_smoke_accepts_an_awaitable_v2_query() -> None:
    thread_id = "thread-123"
    pager = FakePager([SimpleNamespace(is_root=True, thread_id=thread_id)])

    class AwaitableRuns:
        async def query(self, **kwargs: object) -> FakePager:
            return pager

    client = SimpleNamespace(
        read_project=lambda *, project_name: SimpleNamespace(id="project-456"),
        runs=AwaitableRuns(),
    )

    assert asyncio.run(query_thread_runs(client, "travel-planner", thread_id)) == [
        pager._runs[0]
    ]


def test_chat_search_smoke_retries_in_one_event_loop(monkeypatch) -> None:
    loops = []
    sleeps = []
    closed = []

    class RetryingRuns:
        def query(self, **kwargs: object) -> FakePager:
            loops.append(asyncio.get_running_loop())
            if len(loops) == 1:
                return FakePager([])
            return FakePager(
                [
                    SimpleNamespace(name="tool.tavily.start", thread_id="thread-123"),
                    SimpleNamespace(name="tool.tavily.success", thread_id="thread-123"),
                ]
            )

    client = SimpleNamespace(
        read_project=lambda *, project_name: SimpleNamespace(id="project-456"),
        runs=RetryingRuns(),
        close=lambda: closed.append(True),
    )

    async def fake_sleep(seconds: int) -> None:
        sleeps.append(seconds)

    monkeypatch.setenv("LANGSMITH_PROJECT", "travel-planner")
    monkeypatch.setenv("LANGSMITH_API_KEY", "test-key")
    monkeypatch.setitem(
        sys.modules, "langsmith", SimpleNamespace(Client=lambda: client)
    )
    monkeypatch.setattr(asyncio, "sleep", fake_sleep)

    events = CHAT_SEARCH_SMOKE["_langsmith_search_events"]("thread-123")

    assert events == ({"tool.tavily.start", "tool.tavily.success"}, True)
    assert len(loops) == 2
    assert loops[0] is loops[1]
    assert sleeps == [2]
    assert closed == [True]
