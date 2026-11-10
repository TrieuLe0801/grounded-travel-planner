"""Disposable PostgreSQL benchmark for large saved-tour archives.

Run only inside an isolated Docker Compose project.  The script requires both
the Compose-only ``db`` hostname and ``GTP_POSTGRES_BENCHMARK=1``.  It creates
and removes a random schema, never reads or changes ``public.saved_tours``.
Synthetic rows use one owner and a deliberately tiny snapshot; results do not
predict production storage, contention, or real snapshot performance.
"""

from __future__ import annotations

import argparse
import os
import statistics
from collections.abc import Callable
from time import perf_counter
from uuid import uuid4

import psycopg
from psycopg import sql
from psycopg.rows import dict_row

from grounded_travel_planner.saved_tours import SavedTourRepository, SavedTourSummary

PAGE_SIZE = 50
BENCHMARK_OWNER_TOKEN = "postgres-benchmark-owner"
TINY_SNAPSHOT = '{"schema_version":1,"plan":{}}'


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rows", type=int, default=2_000_000)
    parser.add_argument("--deep-page", type=int, default=20_000)
    parser.add_argument("--samples", type=int, default=10)
    args = parser.parse_args()
    if args.rows < 1 or args.deep_page < 0 or args.samples < 1:
        parser.error(
            "--rows and --samples must be positive; --deep-page must be non-negative"
        )
    if args.deep_page * PAGE_SIZE >= args.rows:
        parser.error("--deep-page must identify a generated page")
    return args


def _connection_settings() -> dict[str, object]:
    if os.getenv("GTP_POSTGRES_BENCHMARK") != "1":
        raise RuntimeError(
            "Set GTP_POSTGRES_BENCHMARK=1 for this destructive benchmark."
        )
    settings: dict[str, object] = {
        "host": os.getenv("GTP_SAVED_TOURS_POSTGRES_HOST", ""),
        "port": os.getenv("GTP_SAVED_TOURS_POSTGRES_PORT", "5432"),
        "dbname": os.getenv("GTP_SAVED_TOURS_POSTGRES_DATABASE", ""),
        "user": os.getenv("GTP_SAVED_TOURS_POSTGRES_USER", ""),
        "password": os.getenv("GTP_SAVED_TOURS_POSTGRES_PASSWORD", ""),
        "connect_timeout": 5,
    }
    if settings["host"] != "db":
        raise RuntimeError("Benchmark only permits isolated Compose hostname 'db'.")
    if not all(settings.values()):
        raise RuntimeError("PostgreSQL benchmark settings are incomplete.")
    try:
        settings["port"] = int(str(settings["port"]))
    except ValueError as error:
        raise RuntimeError("PostgreSQL benchmark port is invalid.") from error
    return settings


def _milliseconds(call: Callable[[], object], samples: int) -> tuple[float, float]:
    timings: list[float] = []
    for _ in range(samples):
        started = perf_counter()
        call()
        timings.append((perf_counter() - started) * 1_000)
    ordered = sorted(timings)
    p95_index = min(len(ordered) - 1, round((len(ordered) - 1) * 0.95))
    return statistics.median(ordered), ordered[p95_index]


def _create_schema(
    connection: psycopg.Connection[dict[str, object]], schema: str
) -> None:
    schema_name = sql.Identifier(schema)
    with connection.cursor() as cursor:
        cursor.execute(sql.SQL("CREATE SCHEMA {}").format(schema_name))
        cursor.execute(sql.SQL("""
                CREATE TABLE {}.saved_tours (
                    id TEXT COLLATE "C" PRIMARY KEY,
                    owner_hash TEXT NOT NULL,
                    plan_id TEXT NOT NULL,
                    revision INTEGER NOT NULL,
                    title TEXT NOT NULL,
                    destination TEXT NOT NULL,
                    start_date TEXT NOT NULL,
                    day_count INTEGER NOT NULL,
                    saved_at TEXT COLLATE "C" NOT NULL,
                    plan_snapshot TEXT NOT NULL,
                    UNIQUE (owner_hash, plan_id, revision)
                )
                """).format(schema_name))


def _insert_rows(
    connection: psycopg.Connection[dict[str, object]], schema: str, rows: int
) -> str:
    owner_hash = SavedTourRepository.owner_hash(BENCHMARK_OWNER_TOKEN)
    with connection.cursor() as cursor:
        cursor.execute(
            sql.SQL("""
                INSERT INTO {}.saved_tours (
                    id, owner_hash, plan_id, revision, title, destination,
                    start_date, day_count, saved_at, plan_snapshot
                )
                SELECT
                    lpad(to_hex(number), 32, '0'),
                    %s,
                    'benchmark-plan-' || number,
                    1,
                    'Benchmark',
                    'Benchmark',
                    '2026-01-01',
                    1,
                    to_char(
                        TIMESTAMPTZ '2026-01-01 00:00:00+00'
                        + number * INTERVAL '1 second',
                        'YYYY-MM-DD"T"HH24:MI:SS.US'
                    ) || '+00:00',
                    %s
                FROM generate_series(0, %s - 1) AS number
                """).format(sql.Identifier(schema)),
            (owner_hash, TINY_SNAPSHOT, rows),
        )
        cursor.execute(
            sql.SQL(
                "CREATE INDEX saved_tours_by_owner_saved_at_id "
                "ON {}.saved_tours (owner_hash, saved_at DESC, id DESC)"
            ).format(sql.Identifier(schema))
        )
    return owner_hash


def _cursor_for_page(
    connection: psycopg.Connection[dict[str, object]],
    schema: str,
    owner_hash: str,
    page_number: int,
) -> str | None:
    if page_number == 0:
        return None
    with connection.cursor() as cursor:
        cursor.execute(
            sql.SQL("""
                SELECT id, saved_at FROM {}.saved_tours
                WHERE owner_hash = %s
                ORDER BY saved_at DESC, id DESC
                LIMIT 1 OFFSET %s
                """).format(sql.Identifier(schema)),
            (owner_hash, page_number * PAGE_SIZE - 1),
        )
        row = cursor.fetchone()
    if row is None:
        return None
    return SavedTourRepository.encode_cursor(
        SavedTourSummary(
            id=str(row["id"]),
            title="",
            destination="",
            start_date="",
            day_count=1,
            revision=1,
            saved_at=str(row["saved_at"]),
        )
    )


def _list_page(
    connection: psycopg.Connection[dict[str, object]],
    schema: str,
    owner_hash: str,
    cursor_value: str | None,
) -> None:
    position = (
        SavedTourRepository.decode_cursor(cursor_value)
        if cursor_value is not None
        else None
    )
    query = sql.SQL("""
        SELECT id, title, destination, start_date, day_count, revision, saved_at
        FROM {}.saved_tours WHERE owner_hash = %s
        """).format(sql.Identifier(schema))
    parameters: list[object] = [owner_hash]
    if position is not None:
        query += sql.SQL(" AND (saved_at, id) < (%s, %s)")
        parameters.extend(position)
    query += sql.SQL(" ORDER BY saved_at DESC, id DESC LIMIT %s")
    parameters.append(PAGE_SIZE + 1)
    with connection.cursor() as database_cursor:
        database_cursor.execute(query, parameters)
        database_cursor.fetchall()


def _save(
    connection: psycopg.Connection[dict[str, object]],
    schema: str,
    owner_hash: str,
    revision: int,
) -> str:
    tour_id = uuid4().hex
    with connection.cursor() as cursor:
        cursor.execute(
            sql.SQL("""
                INSERT INTO {}.saved_tours (
                    id, owner_hash, plan_id, revision, title, destination,
                    start_date, day_count, saved_at, plan_snapshot
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """).format(sql.Identifier(schema)),
            (
                tour_id,
                owner_hash,
                "benchmark-write-plan",
                revision,
                "Benchmark",
                "Benchmark",
                "2026-01-01",
                1,
                f"2027-01-01T00:00:{revision:02d}+00:00",
                TINY_SNAPSHOT,
            ),
        )
    return tour_id


def _delete(
    connection: psycopg.Connection[dict[str, object]],
    schema: str,
    owner_hash: str,
    tour_id: str,
) -> None:
    with connection.cursor() as cursor:
        cursor.execute(
            sql.SQL(
                "DELETE FROM {}.saved_tours WHERE owner_hash = %s AND id = %s"
            ).format(sql.Identifier(schema)),
            (owner_hash, tour_id),
        )
        if cursor.rowcount != 1:
            raise RuntimeError("Benchmark row deletion failed.")


def _sizes(
    connection: psycopg.Connection[dict[str, object]], schema: str
) -> tuple[int, int, int]:
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT pg_database_size(current_database()) AS database_bytes,
                   pg_total_relation_size(%s::regclass) AS table_bytes,
                   pg_relation_size(%s::regclass) AS index_bytes
            """,
            (
                f"{schema}.saved_tours",
                f"{schema}.saved_tours_by_owner_saved_at_id",
            ),
        )
        row = cursor.fetchone()
    if row is None:
        raise RuntimeError("Could not read benchmark storage sizes.")
    return int(row["database_bytes"]), int(row["table_bytes"]), int(row["index_bytes"])


def _run(args: argparse.Namespace) -> None:
    settings = _connection_settings()
    schema = f"benchmark_saved_tours_{uuid4().hex}"
    with psycopg.connect(**settings, row_factory=dict_row) as connection:
        try:
            setup_started = perf_counter()
            _create_schema(connection, schema)
            owner_hash = _insert_rows(connection, schema, args.rows)
            connection.commit()
            setup_seconds = perf_counter() - setup_started

            first_p50, first_p95 = _milliseconds(
                lambda: _list_page(connection, schema, owner_hash, None), args.samples
            )
            deep_cursor = _cursor_for_page(
                connection, schema, owner_hash, args.deep_page
            )
            if deep_cursor is None:
                raise RuntimeError("Deep-page cursor could not be created.")
            deep_p50, deep_p95 = _milliseconds(
                lambda: _list_page(connection, schema, owner_hash, deep_cursor),
                args.samples,
            )
            next_revision = iter(range(2, args.samples + 2))
            save_p50, save_p95 = _milliseconds(
                lambda: _save(connection, schema, owner_hash, next(next_revision)),
                args.samples,
            )
            delete_ids = [
                _save(connection, schema, owner_hash, revision)
                for revision in range(args.samples + 2, (args.samples * 2) + 2)
            ]
            next_delete_id = iter(delete_ids)
            delete_p50, delete_p95 = _milliseconds(
                lambda: _delete(connection, schema, owner_hash, next(next_delete_id)),
                args.samples,
            )
            connection.commit()
            database_bytes, table_bytes, index_bytes = _sizes(connection, schema)
            print(
                f"rows={args.rows:,} database_bytes={database_bytes:,} "
                f"table_bytes={table_bytes:,} index_bytes={index_bytes:,} "
                f"setup_seconds={setup_seconds:.2f}"
            )
            print(f"first_page_ms p50={first_p50:.3f} p95={first_p95:.3f}")
            print(
                f"deep_page={args.deep_page:,} ms p50={deep_p50:.3f} "
                f"p95={deep_p95:.3f}"
            )
            print(f"save_ms p50={save_p50:.3f} p95={save_p95:.3f}")
            print(f"delete_ms p50={delete_p50:.3f} p95={delete_p95:.3f}")
        finally:
            with connection.cursor() as cursor:
                cursor.execute(
                    sql.SQL("DROP SCHEMA IF EXISTS {} CASCADE").format(
                        sql.Identifier(schema)
                    )
                )
            connection.commit()


def main() -> int:
    _run(_parse_args())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
