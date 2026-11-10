"""Offline checks for the supported LangSmith query used by the live smoke gate."""

from __future__ import annotations

import asyncio
import runpy
from pathlib import Path
from types import SimpleNamespace

SMOKE = runpy.run_path(Path("scripts/live_smoke.py"))
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
