"""Copy a stopped SQLite saved-tour archive into PostgreSQL without changing snapshots."""

from __future__ import annotations

import argparse
import os
import sqlite3
import sys
from pathlib import Path

import psycopg

from grounded_travel_planner.postgres_saved_tours import create_postgres_schema

COLUMNS = (
    "id",
    "owner_hash",
    "plan_id",
    "revision",
    "title",
    "destination",
    "start_date",
    "day_count",
    "saved_at",
    "plan_snapshot",
)
BATCH_SIZE = 1000


def migrate(sqlite_path: Path) -> int:
    """Copy in bounded batches; verify every SQLite row exactly on each run."""

    if not sqlite_path.is_file():
        raise RuntimeError(f"SQLite database does not exist: {sqlite_path}")
    if sqlite_path.with_name(f"{sqlite_path.name}-wal").exists():
        raise RuntimeError(
            "SQLite WAL file is present. Stop writes and checkpoint before migration."
        )
    connection_settings = {
        "host": os.getenv("GTP_SAVED_TOURS_POSTGRES_HOST", ""),
        "port": os.getenv("GTP_SAVED_TOURS_POSTGRES_PORT", "5432"),
        "dbname": os.getenv("GTP_SAVED_TOURS_POSTGRES_DATABASE", ""),
        "user": os.getenv("GTP_SAVED_TOURS_POSTGRES_USER", ""),
        "password": os.getenv("GTP_SAVED_TOURS_POSTGRES_PASSWORD", ""),
        "connect_timeout": 5,
    }
    if not all(connection_settings.values()):
        raise RuntimeError("PostgreSQL saved-tour settings are incomplete.")
    source = sqlite3.connect(
        f"{sqlite_path.resolve().as_uri()}?mode=ro&immutable=1", uri=True
    )
    try:
        integrity = source.execute("PRAGMA integrity_check").fetchone()
        if integrity != ("ok",):
            raise RuntimeError("SQLite integrity check failed.")
        table_exists = source.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='saved_tours'"
        ).fetchone()
        if table_exists is None:
            raise RuntimeError("SQLite saved_tours table does not exist.")
        source_cursor = source.execute(
            f"SELECT {', '.join(COLUMNS)} FROM saved_tours ORDER BY id"
        )
        copied = 0
        with psycopg.connect(**connection_settings) as target:
            create_postgres_schema(target, create_index=False)
            target.commit()
            while True:
                rows = source_cursor.fetchmany(BATCH_SIZE)
                if not rows:
                    break
                with target.cursor() as cursor:
                    cursor.executemany(
                        """
                        INSERT INTO saved_tours (
                            id, owner_hash, plan_id, revision, title, destination,
                            start_date, day_count, saved_at, plan_snapshot
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        ON CONFLICT (id) DO NOTHING
                        """,
                        rows,
                    )
                    cursor.execute(
                        f"SELECT {', '.join(COLUMNS)} FROM saved_tours "
                        "WHERE id = ANY(%s) ORDER BY id",
                        ([row[0] for row in rows],),
                    )
                    stored = cursor.fetchall()
                    if stored != rows:
                        raise RuntimeError(
                            "PostgreSQL rows differ from SQLite source; migration stopped."
                        )
                target.commit()
                copied += len(rows)
            create_postgres_schema(target)
            target.commit()
        return copied
    finally:
        source.close()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sqlite", required=True, type=Path)
    arguments = parser.parse_args()
    try:
        count = migrate(arguments.sqlite)
    except (RuntimeError, sqlite3.Error, psycopg.Error) as error:
        print(f"Saved-tour migration failed: {error}", file=sys.stderr)
        return 1
    print(f"Saved-tour migration verified {count} SQLite rows in PostgreSQL.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
