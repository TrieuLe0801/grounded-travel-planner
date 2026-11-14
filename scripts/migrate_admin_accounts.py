"""Explicit admin-access migration for a stopped authentication database.

Back up the database and pause application writes before running. Existing
accounts remain active; new Auth0 identities start pending approval. Optionally
activate the first administrator by internal account UUID or by a unique email
already associated with a verified Auth0 login after migration.
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
    PostgresAuthRepository,
    migrate_postgres_admin_schema,
)


def postgres_settings() -> dict[str, str | int]:
    settings: dict[str, str | int] = {
        "host": os.getenv("GTP_SAVED_TOURS_POSTGRES_HOST", ""),
        "port": int(os.getenv("GTP_SAVED_TOURS_POSTGRES_PORT", "5432")),
        "dbname": os.getenv("GTP_SAVED_TOURS_POSTGRES_DATABASE", ""),
        "user": os.getenv("GTP_SAVED_TOURS_POSTGRES_USER", ""),
        "password": os.getenv("GTP_SAVED_TOURS_POSTGRES_PASSWORD", ""),
        "connect_timeout": 5,
    }
    if not all(settings.values()):
        raise AuthError("PostgreSQL auth settings are incomplete.")
    return settings


def find_bootstrap_user_id(
    repository: AuthRepository | PostgresAuthRepository, email: str
) -> str:
    """Resolve an existing account by unique email without persisting it."""

    wanted = email.strip().casefold()
    if not wanted:
        raise AuthError("Bootstrap email is required.")
    matches: list[str] = []
    offset = 0
    while True:
        page = repository.list_users(limit=100, offset=offset)
        matches.extend(
            account.id
            for account in page
            if account.email and account.email.casefold() == wanted
        )
        if len(page) < 100:
            break
        offset += len(page)
    if len(matches) != 1:
        raise AuthError("Bootstrap email must match exactly one existing account.")
    return matches[0]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    target = parser.add_mutually_exclusive_group(required=True)
    target.add_argument("--sqlite", type=Path, help="existing SQLite auth database")
    target.add_argument(
        "--postgres", action="store_true", help="use PostgreSQL runtime settings"
    )
    bootstrap = parser.add_mutually_exclusive_group()
    bootstrap.add_argument(
        "--bootstrap-user-id",
        help="existing internal account UUID to make first administrator",
    )
    bootstrap.add_argument(
        "--bootstrap-email",
        help="unique email on an existing Auth0-backed account",
    )
    args = parser.parse_args()
    try:
        if args.sqlite is not None:
            if not args.sqlite.is_file():
                raise AuthError("SQLite auth database does not exist.")
            repository: AuthRepository | PostgresAuthRepository = AuthRepository(
                args.sqlite
            )
            repository.migrate_admin()
        else:
            settings = postgres_settings()
            with psycopg.connect(**settings) as connection:
                migrate_postgres_admin_schema(connection)
            repository = PostgresAuthRepository(
                host=str(settings["host"]),
                port=int(settings["port"]),
                database=str(settings["dbname"]),
                user=str(settings["user"]),
                password=str(settings["password"]),
            )
        try:
            if args.bootstrap_user_id:
                repository.bootstrap_admin(args.bootstrap_user_id)
            elif args.bootstrap_email:
                repository.bootstrap_admin(
                    find_bootstrap_user_id(repository, args.bootstrap_email)
                )
        finally:
            if isinstance(repository, PostgresAuthRepository):
                repository.close()
    except (AuthError, sqlite3.Error, psycopg.Error, ValueError) as error:
        print(f"Admin account migration failed: {error}", file=sys.stderr)
        return 1
    print("Admin account migration completed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
