"""Offline saved-tour smoke for the Compose app container and PostgreSQL service.

Run only against a disposable Compose project:
``python scripts/postgres_saved_tours_smoke.py``.
It creates a temporary SQLite v2 archive, migrates it into PostgreSQL, then
checks migration preservation plus save/list/detail/delete and owner isolation.
No model, search or tracing provider is called.
"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from datetime import date, time
from pathlib import Path

from grounded_travel_planner.contracts import (
    PlaceRecommendation,
    ScheduleEntry,
    SightseeingPlan,
    SourceReference,
)
from grounded_travel_planner.postgres_saved_tours import PostgresSavedTourRepository
from grounded_travel_planner.saved_tours import SavedTourRepository


def _plan(plan_id: str, *, destination: str) -> SightseeingPlan:
    source = SourceReference(
        source_id=f"{plan_id}-source",
        title="Smoke fixture source",
        url="https://example.test/smoke-source",
        snippet="Offline smoke fixture.",
        retrieval_query=destination,
    )
    return SightseeingPlan(
        plan_id=plan_id,
        destination=destination,
        start_date=date(2026, 11, 1),
        day_count=1,
        revision=1,
        entries=[
            ScheduleEntry(
                id=f"{plan_id}-entry",
                day_index=1,
                start_time=time(9),
                end_time=time(10),
                place=PlaceRecommendation(
                    place_id=f"{plan_id}-place",
                    name="Smoke fixture place",
                    description="Deterministic saved tour.",
                    source_references=[source],
                    opening_hours="unverified",
                ),
            )
        ],
    )


def _repository() -> PostgresSavedTourRepository:
    required = (
        "GTP_SAVED_TOURS_POSTGRES_HOST",
        "GTP_SAVED_TOURS_POSTGRES_DATABASE",
        "GTP_SAVED_TOURS_POSTGRES_USER",
        "GTP_SAVED_TOURS_POSTGRES_PASSWORD",
    )
    missing = [key for key in required if not os.getenv(key)]
    if missing:
        raise RuntimeError(
            f"Missing PostgreSQL environment values: {', '.join(missing)}"
        )
    return PostgresSavedTourRepository(
        host=os.environ["GTP_SAVED_TOURS_POSTGRES_HOST"],
        database=os.environ["GTP_SAVED_TOURS_POSTGRES_DATABASE"],
        user=os.environ["GTP_SAVED_TOURS_POSTGRES_USER"],
        password=os.environ["GTP_SAVED_TOURS_POSTGRES_PASSWORD"],
        port=int(os.getenv("GTP_SAVED_TOURS_POSTGRES_PORT", "5432")),
    )


def _migrate(sqlite_path: Path) -> None:
    command = [
        sys.executable,
        "scripts/migrate_saved_tours_to_postgres.py",
        "--sqlite",
        str(sqlite_path),
    ]
    result = subprocess.run(command, check=False, capture_output=True, text=True)
    if result.returncode:
        raise RuntimeError(result.stderr.strip() or "PostgreSQL migration failed.")


def main() -> int:
    repository = _repository()
    owner_one = "compose-smoke-owner-one"
    owner_two = "compose-smoke-owner-two"
    migrated_plan = _plan("compose-smoke-migrated-plan", destination="Hue")
    live_plan = _plan("compose-smoke-live-plan", destination="Da Nang")

    with tempfile.TemporaryDirectory(prefix="postgres-saved-tours-smoke-") as directory:
        sqlite_path = Path(directory) / "legacy.sqlite"
        legacy = SavedTourRepository(sqlite_path)
        legacy_saved = legacy.save(owner_one, migrated_plan)
        _migrate(sqlite_path)

    migrated = repository.get(owner_one, legacy_saved.id)
    if migrated is None or migrated.payload() != legacy_saved.payload():
        raise RuntimeError("Migrated saved-tour snapshot differs from SQLite source.")

    saved = repository.save(owner_one, live_plan)
    repeated = repository.save(owner_one, live_plan)
    page = repository.list(owner_one, limit=50)
    detail = repository.get(owner_one, saved.id)
    isolated = repository.get(owner_two, saved.id) is None and not repository.delete(
        owner_two, saved.id
    )
    deleted = repository.delete(owner_one, saved.id)
    if not (
        repeated.id == saved.id
        and any(item.id == saved.id for item in page.items)
        and detail is not None
        and detail.payload() == saved.payload()
        and isolated
        and deleted
        and repository.get(owner_one, saved.id) is None
    ):
        raise RuntimeError("PostgreSQL saved-tour repository contract failed.")
    print("PostgreSQL saved-tour smoke passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
