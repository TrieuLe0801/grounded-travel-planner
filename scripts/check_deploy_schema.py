"""Verify database columns required by the new app before replacing its container.

Add each future explicit PostgreSQL migration's required columns here. This
check is read-only and never performs a migration.
"""

from __future__ import annotations

import os
import sys

import psycopg

REQUIRED_COLUMNS = {
    "auth_sessions": {"remember_login"},
}


def check_required_columns(connection: psycopg.Connection) -> None:
    with connection.cursor() as cursor:
        cursor.execute("""SELECT table_name, column_name
            FROM information_schema.columns
            WHERE table_schema = current_schema()""")
        available = {(str(table), str(column)) for table, column in cursor.fetchall()}
    missing = sorted(
        f"{table}.{column}"
        for table, columns in REQUIRED_COLUMNS.items()
        for column in columns
        if (table, column) not in available
    )
    if missing:
        raise RuntimeError(
            "Required database migration is missing: " + ", ".join(missing)
        )


def main() -> int:
    settings = {
        "host": os.getenv("GTP_SAVED_TOURS_POSTGRES_HOST", ""),
        "port": int(os.getenv("GTP_SAVED_TOURS_POSTGRES_PORT", "5432")),
        "dbname": os.getenv("GTP_SAVED_TOURS_POSTGRES_DATABASE", ""),
        "user": os.getenv("GTP_SAVED_TOURS_POSTGRES_USER", ""),
        "password": os.getenv("GTP_SAVED_TOURS_POSTGRES_PASSWORD", ""),
        "connect_timeout": 5,
    }
    if not all(settings.values()):
        print(
            "Database schema check failed: PostgreSQL settings are incomplete.",
            file=sys.stderr,
        )
        return 1
    try:
        with psycopg.connect(**settings) as connection:
            check_required_columns(connection)
    except RuntimeError as error:
        print(f"Database schema check failed: {error}", file=sys.stderr)
        return 1
    except psycopg.Error:
        print(
            "Database schema check failed: PostgreSQL connection or query failed.",
            file=sys.stderr,
        )
        return 1
    print("Database schema check passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
