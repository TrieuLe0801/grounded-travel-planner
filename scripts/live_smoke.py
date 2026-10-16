"""Explicit live OpenAI/Tavily/LangSmith smoke gate; never run from pytest."""

from __future__ import annotations

import asyncio
import inspect
import json
import os
from datetime import date
from typing import Any

from grounded_travel_planner.contracts import TripRequest
from grounded_travel_planner.service import TravelPlannerService


async def _query_thread_runs(
    client: Any, project_name: str, thread_id: str
) -> list[Any]:
    """Return the selected v2 LangSmith runs for one app session thread."""
    project = client.read_project(project_name=project_name)
    pager = client.runs.query(
        project_ids=[str(project.id)],
        filter=f"eq(thread_id, {json.dumps(thread_id)})",
        page_size=100,
        selects=["IS_ROOT", "THREAD_ID"],
    )
    if inspect.isawaitable(pager):
        pager = await pager
    return [run async for run in pager]


def _summarize_thread_runs(runs: list[Any], thread_id: str) -> dict[str, object]:
    """Return counts and propagation status without exposing trace contents."""
    return {
        "run_count": len(runs),
        "root_count": sum(run.is_root is True for run in runs),
        "child_count": sum(run.is_root is False for run in runs),
        "thread_metadata_on_all": all(run.thread_id == thread_id for run in runs),
    }


def main() -> int:
    service = TravelPlannerService.from_environment()
    thread_id = service.create_session()
    response = service.handle_turn(
        thread_id=thread_id,
        message="Create a one-day sourced sightseeing plan for Hue.",
        request=TripRequest(
            destination="Hue",
            start_date=date(2026, 11, 1),
            day_count=1,
        ),
    )
    plan = response.current_plan
    citations = sorted(
        {
            str(source.url)
            for entry in (plan.entries if plan else [])
            for source in entry.place.source_references
        }
    )
    summary: dict[str, object] = {
        "outcome": response.status.value,
        "committed": response.committed,
        "model": service.config.model_name,
        "graph_steps": response.graph_steps,
        "search_calls": response.search_calls,
        "repair_attempts": response.repair_attempts,
        "issue_codes": [issue.code for issue in response.validation_issues],
        "citation_count": len(citations),
        "citations": citations,
        "langsmith": "not_checked",
    }
    project = os.getenv("LANGSMITH_PROJECT")
    if os.getenv("LANGSMITH_API_KEY") and project:
        try:
            from langsmith import Client

            client = Client()
            runs = asyncio.run(_query_thread_runs(client, project, thread_id))
            summary["langsmith"] = _summarize_thread_runs(runs, thread_id)
        except Exception as error:  # noqa: BLE001 - report live gate safely
            summary["langsmith"] = {
                "error_type": type(error).__name__,
                "verified": False,
            }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if response.committed else 1


if __name__ == "__main__":
    raise SystemExit(main())
