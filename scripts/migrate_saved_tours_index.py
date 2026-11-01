"""Explicitly migrate saved-tour list indexes to the keyset-pagination schema."""

from __future__ import annotations

import argparse
import sqlite3
import sys
from pathlib import Path

from grounded_travel_planner.saved_tours import (
    LEGACY_OWNER_INDEX_NAME,
    OWNER_SAVED_AT_ID_INDEX_NAME,
    SAVED_TOURS_SCHEMA_VERSION,
)


def migrate(database_path: Path) -> None:
    """Atomically install the v2 list index and record its schema version."""

    if not database_path.is_file():
        raise RuntimeError(f"Database does not exist: {database_path}")
    connection = sqlite3.connect(database_path, timeout=30, isolation_level=None)
    try:
        connection.execute("PRAGMA busy_timeout = 30000")
        connection.execute("BEGIN IMMEDIATE")
        table_exists = connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'saved_tours'"
        ).fetchone()
        if table_exists is None:
            raise RuntimeError("Database does not contain the saved_tours table.")
        version = int(connection.execute("PRAGMA user_version").fetchone()[0])
        index_exists = connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'index' AND name = ?",
            (OWNER_SAVED_AT_ID_INDEX_NAME,),
        ).fetchone()
        if version >= SAVED_TOURS_SCHEMA_VERSION and index_exists is None:
            raise RuntimeError(
                "Database claims v2 but its saved-tour index is missing."
            )
        if version < SAVED_TOURS_SCHEMA_VERSION:
            connection.execute(
                f"CREATE INDEX IF NOT EXISTS {OWNER_SAVED_AT_ID_INDEX_NAME} "
                "ON saved_tours(owner_hash, saved_at DESC, id DESC)"
            )
            connection.execute(f"PRAGMA user_version = {SAVED_TOURS_SCHEMA_VERSION}")
        connection.execute(f"DROP INDEX IF EXISTS {LEGACY_OWNER_INDEX_NAME}")
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("database", type=Path, help="path to the SQLite database")
    arguments = parser.parse_args()
    try:
        migrate(arguments.database)
    except (RuntimeError, sqlite3.Error) as error:
        print(f"Saved-tour migration failed: {error}", file=sys.stderr)
        return 1
    print(f"Saved-tour migration completed: {arguments.database}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
