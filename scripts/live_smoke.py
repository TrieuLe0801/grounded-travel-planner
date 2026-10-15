"""Explicit live OpenAI/Tavily/LangSmith smoke gate; never run from pytest."""

from __future__ import annotations

import json
import os
import warnings
from datetime import date

from grounded_travel_planner.contracts import TripRequest
from grounded_travel_planner.service import TravelPlannerService


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
            filter_value = (
                'and(eq(metadata_key, "thread_id"), '
                f'eq(metadata_value, "{thread_id}"))'
            )
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", DeprecationWarning)
                runs = list(
                    client.list_runs(
                        project_name=project,
                        filter=filter_value,
                        limit=100,
                    )
                )
            summary["langsmith"] = {
                "run_count": len(runs),
                "root_count": sum(run.parent_run_id is None for run in runs),
                "child_count": sum(run.parent_run_id is not None for run in runs),
                "thread_metadata_on_all": all(
                    (run.extra or {}).get("metadata", {}).get("thread_id") == thread_id
                    for run in runs
                ),
            }
        except Exception as error:  # noqa: BLE001 - report live gate safely
            summary["langsmith"] = {
                "error_type": type(error).__name__,
                "verified": False,
            }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if response.committed else 1


if __name__ == "__main__":
    raise SystemExit(main())
