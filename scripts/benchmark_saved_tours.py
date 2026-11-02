"""Optional local SQLite benchmark for saved-tour archive pagination.

This script is deliberately outside pytest and creates a disposable database by
default.  It inserts synthetic summary rows only; it never uses providers,
browser cookies, or a production archive.
"""

from __future__ import annotations

import argparse
import sqlite3
import statistics
import tempfile
from collections.abc import Callable
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from time import perf_counter

from grounded_travel_planner.contracts import (
    PlaceRecommendation,
    ScheduleEntry,
    SightseeingPlan,
    SourceReference,
)
from grounded_travel_planner.saved_tours import SavedTourRepository, SavedTourSummary


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rows", type=int, default=2_000_000)
    parser.add_argument("--deep-page", type=int, default=20_000)
    parser.add_argument("--samples", type=int, default=10)
    parser.add_argument("--database", type=Path)
    args = parser.parse_args()
    if args.rows < 1 or args.deep_page < 0 or args.samples < 1:
        parser.error(
            "--rows and --samples must be positive; --deep-page must be non-negative"
        )
    return args


def _synthetic_plan() -> SightseeingPlan:
    source = SourceReference(
        source_id="benchmark-source",
        title="Synthetic source",
        url="https://example.test/benchmark",
        snippet="Synthetic offline benchmark source.",
        retrieval_query="benchmark",
    )
    return SightseeingPlan(
        plan_id="benchmark-plan-write",
        destination="Benchmark",
        start_date=date(2026, 1, 1),
        day_count=1,
        entries=[
            ScheduleEntry(
                id="benchmark-entry",
                day_index=1,
                start_time=time(9),
                end_time=time(10),
                place=PlaceRecommendation(
                    place_id="benchmark-place",
                    name="Benchmark place",
                    description="Synthetic offline benchmark place.",
                    source_references=[source],
                ),
            )
        ],
        summary="Synthetic benchmark plan.",
    )


def _milliseconds(call: Callable[[], object], samples: int) -> tuple[float, float]:
    timings: list[float] = []
    for _ in range(samples):
        started = perf_counter()
        call()
        timings.append((perf_counter() - started) * 1_000)
    ordered = sorted(timings)
    p95_index = min(len(ordered) - 1, round((len(ordered) - 1) * 0.95))
    return statistics.median(ordered), ordered[p95_index]


def _insert_rows(database: Path, owner_hash: str, rows: int) -> None:
    """Use a single transaction and compact fixture payload to make setup measurable."""

    snapshot = '{"schema_version":1,"plan":{}}'
    origin = datetime(2026, 1, 1, tzinfo=timezone.utc)
    with sqlite3.connect(database) as connection:
        for first in range(0, rows, 10_000):
            batch_end = min(first + 10_000, rows)
            connection.executemany(
                """
                INSERT INTO saved_tours (
                    id, owner_hash, plan_id, revision, title, destination,
                    start_date, day_count, saved_at, plan_snapshot
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    (
                        f"{index:032x}",
                        owner_hash,
                        f"benchmark-plan-{index}",
                        1,
                        "Benchmark",
                        "Benchmark",
                        origin.date().isoformat(),
                        1,
                        (origin + timedelta(seconds=index)).isoformat(),
                        snapshot,
                    )
                    for index in range(first, batch_end)
                ),
            )


def _benchmark_cursor_at_page(
    database: Path,
    repository: SavedTourRepository,
    owner_token: str,
    page_number: int,
) -> str | None:
    """Build a cursor once with SQL; measured lookups always use keyset paging."""

    if page_number == 0:
        return None
    with sqlite3.connect(database) as connection:
        row = connection.execute(
            """
            SELECT id, saved_at FROM saved_tours
            WHERE owner_hash = ?
            ORDER BY saved_at DESC, id DESC
            LIMIT 1 OFFSET ?
            """,
            (repository.owner_hash(owner_token), page_number * 50 - 1),
        ).fetchone()
    if row is None:
        return None
    return repository.encode_cursor(
        SavedTourSummary(
            id=str(row[0]),
            title="",
            destination="",
            start_date="",
            day_count=1,
            revision=1,
            saved_at=str(row[1]),
        )
    )


def _run(database: Path, args: argparse.Namespace) -> None:
    owner_token = "benchmark-owner-token"
    repository = SavedTourRepository(database)
    setup_started = perf_counter()
    _insert_rows(database, repository.owner_hash(owner_token), args.rows)
    setup_seconds = perf_counter() - setup_started

    first_p50, first_p95 = _milliseconds(
        lambda: repository.list(owner_token), args.samples
    )
    deep_cursor = _benchmark_cursor_at_page(
        database, repository, owner_token, args.deep_page
    )
    if deep_cursor is None and args.deep_page:
        raise RuntimeError("--deep-page exceeds the generated archive")
    deep_p50, deep_p95 = _milliseconds(
        lambda: repository.list(owner_token, cursor=deep_cursor), args.samples
    )
    write_plan = _synthetic_plan()
    save_revisions = iter(range(2, args.samples + 2))
    save_p50, save_p95 = _milliseconds(
        lambda: repository.save(
            owner_token,
            write_plan.model_copy(update={"revision": next(save_revisions)}),
        ),
        args.samples,
    )
    delete_ids = iter(
        repository.save(
            owner_token,
            write_plan.model_copy(update={"revision": revision}),
        ).id
        for revision in range(args.samples + 2, (args.samples * 2) + 2)
    )
    delete_p50, delete_p95 = _milliseconds(
        lambda: repository.delete(owner_token, next(delete_ids)), args.samples
    )

    with sqlite3.connect(database) as connection:
        connection.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    wal_path = database.with_name(f"{database.name}-wal")
    wal_bytes = wal_path.stat().st_size if wal_path.exists() else 0
    print(
        f"rows={args.rows:,} database_bytes={database.stat().st_size:,} "
        f"wal_bytes={wal_bytes:,} setup_seconds={setup_seconds:.2f}"
    )
    print(f"first_page_ms p50={first_p50:.3f} p95={first_p95:.3f}")
    print(f"deep_page={args.deep_page:,} ms p50={deep_p50:.3f} p95={deep_p95:.3f}")
    print(f"save_ms p50={save_p50:.3f} p95={save_p95:.3f}")
    print(f"delete_ms p50={delete_p50:.3f} p95={delete_p95:.3f}")


def main() -> None:
    args = _parse_args()
    if args.database:
        args.database.parent.mkdir(parents=True, exist_ok=True)
        _run(args.database, args)
        return
    with tempfile.TemporaryDirectory(prefix="gtp-saved-tours-") as directory:
        _run(Path(directory) / "saved_tours.sqlite", args)


if __name__ == "__main__":
    main()
