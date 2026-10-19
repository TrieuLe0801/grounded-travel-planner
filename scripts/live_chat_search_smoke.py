"""Explicit live gate for the shared Tavily graph tool and LangSmith event."""

from __future__ import annotations

import asyncio
import inspect
import json
import os
import time
from typing import Any

from grounded_travel_planner.service import TravelPlannerService


async def _query_thread_runs(
    client: Any, project_name: str, thread_id: str
) -> list[Any]:
    project = client.read_project(project_name=project_name)
    pager = client.runs.query(
        project_ids=[str(project.id)],
        filter=f"eq(thread_id, {json.dumps(thread_id)})",
        page_size=100,
        selects=["NAME", "IS_ROOT", "THREAD_ID"],
    )
    if inspect.isawaitable(pager):
        pager = await pager
    return [run async for run in pager]


def _langsmith_search_events(thread_id: str) -> tuple[set[str], bool]:
    project_name = os.getenv("LANGSMITH_PROJECT")
    if not os.getenv("LANGSMITH_API_KEY") or not project_name:
        return set(), False
    from langsmith import Client

    client = Client()
    for attempt in range(5):
        runs = asyncio.run(_query_thread_runs(client, project_name, thread_id))
        if any(
            run.name in {"tool.tavily.start", "tool.tavily.success"} for run in runs
        ):
            return (
                {run.name for run in runs if run.name.startswith("tool.tavily.")},
                all(run.thread_id == thread_id for run in runs),
            )
        if attempt < 4:
            time.sleep(2)
    return set(), False


def main() -> int:
    service = TravelPlannerService.from_environment()
    thread_id = service.create_session()
    response = service.handle_turn(
        thread_id=thread_id,
        message=(
            "Tìm thông tin cập nhật về giờ mở cửa Đại Nội Huế và cho tôi biết "
            "nguồn tham khảo."
        ),
    )
    event_names, thread_ids_match = _langsmith_search_events(thread_id)
    verified = bool(
        response.search_calls == 1
        and response.source_references
        and "tool.tavily.start" in event_names
        and "tool.tavily.success" in event_names
        and thread_ids_match
    )
    print(
        json.dumps(
            {
                "status": response.status.value,
                "chat_search_calls": response.search_calls,
                "chat_source_count": len(response.source_references),
                "tavily_tool_events": sorted(event_names),
                "thread_id_matches": thread_ids_match,
                "verified": verified,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0 if verified else 1


if __name__ == "__main__":
    raise SystemExit(main())
