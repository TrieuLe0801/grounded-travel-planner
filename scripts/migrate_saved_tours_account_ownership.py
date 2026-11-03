"""Explicitly add account ownership to a stopped saved-tour archive.

Back up the database and pause archive writes before running. This migration
does not claim tours or change IDs, timestamps, owner hashes, or snapshot text.
"""

from __future__ import annotations

import argparse
import os
import sqlite3
import sys
from pathlib import Path

import psycopg

from grounded_travel_planner.auth import AuthRepository, create_postgres_auth_schema
from grounded_travel_planner.saved_tours import (
    ACCOUNT_SAVED_TOURS_SCHEMA_VERSION,
    USER_SAVED_AT_ID_INDEX_NAME,
)


def migrate_sqlite(database_path: Path) -> None:
    """Add nullable account ownership and its keyset index atomically."""

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
        columns = connection.execute("PRAGMA table_info(saved_tours)").fetchall()
        if "owner_user_id" not in {str(column[1]) for column in columns}:
            connection.execute("ALTER TABLE saved_tours ADD COLUMN owner_user_id TEXT")
        connection.execute(
            f"CREATE INDEX IF NOT EXISTS {USER_SAVED_AT_ID_INDEX_NAME} "
            "ON saved_tours(owner_user_id, saved_at DESC, id DESC)"
        )
        connection.execute(
            f"PRAGMA user_version = {ACCOUNT_SAVED_TOURS_SCHEMA_VERSION}"
        )
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def migrate_postgres() -> None:
    """Add nullable account ownership and its index during a write pause."""

    settings = {
        "host": os.getenv("GTP_SAVED_TOURS_POSTGRES_HOST", ""),
        "port": os.getenv("GTP_SAVED_TOURS_POSTGRES_PORT", "5432"),
        "dbname": os.getenv("GTP_SAVED_TOURS_POSTGRES_DATABASE", ""),
        "user": os.getenv("GTP_SAVED_TOURS_POSTGRES_USER", ""),
        "password": os.getenv("GTP_SAVED_TOURS_POSTGRES_PASSWORD", ""),
        "connect_timeout": 5,
    }
    if not all(settings.values()):
        raise RuntimeError("PostgreSQL saved-tour settings are incomplete.")
    with psycopg.connect(**settings) as connection, connection.cursor() as cursor:
        cursor.execute("SELECT to_regclass('saved_tours')")
        if cursor.fetchone()[0] is None:
            raise RuntimeError("Database does not contain the saved_tours table.")
        create_postgres_auth_schema(connection)
        cursor.execute(
            "ALTER TABLE saved_tours ADD COLUMN IF NOT EXISTS owner_user_id TEXT"
        )
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS saved_tours_by_user_saved_at_id
            ON saved_tours (owner_user_id, saved_at DESC, id DESC)
            """)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    target = parser.add_mutually_exclusive_group(required=True)
    target.add_argument("--sqlite", type=Path, help="path to stopped SQLite archive")
    target.add_argument(
        "--postgres",
        action="store_true",
        help="use GTP_SAVED_TOURS_POSTGRES_* settings for stopped PostgreSQL archive",
    )
    parser.add_argument(
        "--auth-db",
        type=Path,
        default=Path(os.getenv("GTP_AUTH_DB_PATH", ".local/auth.sqlite")),
        help="local SQLite auth database path (used with --sqlite)",
    )
    arguments = parser.parse_args()
    try:
        if arguments.sqlite is not None:
            migrate_sqlite(arguments.sqlite)
            AuthRepository(arguments.auth_db).migrate()
            print(f"Saved-tour account migration completed: {arguments.sqlite}")
        else:
            migrate_postgres()
            print("Saved-tour account migration completed for PostgreSQL.")
    except (RuntimeError, sqlite3.Error, psycopg.Error) as error:
        print(f"Saved-tour account migration failed: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
