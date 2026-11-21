"""Create runtime-model settings tables during a stopped-app maintenance window.

Back up the account database and pause application writes before running.
"""

from __future__ import annotations

import argparse
import os
import sqlite3
import sys
from pathlib import Path

import psycopg

from grounded_travel_planner.auth import (
    AuthError,
    AuthRepository,
    migrate_postgres_runtime_model_settings_schema,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    target = parser.add_mutually_exclusive_group(required=True)
    target.add_argument("--sqlite", type=Path, help="existing SQLite account database")
    target.add_argument(
        "--postgres", action="store_true", help="use PostgreSQL account settings"
    )
    args = parser.parse_args()
    try:
        if args.sqlite is not None:
            if not args.sqlite.is_file():
                raise AuthError("SQLite auth database does not exist.")
            AuthRepository(args.sqlite).migrate_runtime_model_settings()
        else:
            settings = {
                "host": os.getenv("GTP_SAVED_TOURS_POSTGRES_HOST", ""),
                "port": int(os.getenv("GTP_SAVED_TOURS_POSTGRES_PORT", "5432")),
                "dbname": os.getenv("GTP_SAVED_TOURS_POSTGRES_DATABASE", ""),
                "user": os.getenv("GTP_SAVED_TOURS_POSTGRES_USER", ""),
                "password": os.getenv("GTP_SAVED_TOURS_POSTGRES_PASSWORD", ""),
                "connect_timeout": 5,
            }
            if not all(settings.values()):
                raise AuthError("PostgreSQL auth settings are incomplete.")
            with psycopg.connect(**settings) as connection:
                migrate_postgres_runtime_model_settings_schema(connection)
    except (AuthError, sqlite3.Error, psycopg.Error, ValueError) as error:
        print(f"Runtime model settings migration failed: {error}", file=sys.stderr)
        return 1
    print("Runtime model settings migration completed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
