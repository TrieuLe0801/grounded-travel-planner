"""PostgreSQL archive for explicitly saved, owner-scoped tour snapshots."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from uuid import uuid4

import psycopg
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool, PoolClosed, PoolTimeout

from grounded_travel_planner.contracts import SightseeingPlan
from grounded_travel_planner.saved_tours import (
    LIST_LIMIT,
    SNAPSHOT_SCHEMA_VERSION,
    SavedTour,
    SavedTourError,
    SavedTourPage,
    SavedTourRepository,
)


class PostgresSavedTourRepository:
    """Bounded PostgreSQL connections with the SQLite archive's public contract."""

    def __init__(
        self,
        *,
        host: str,
        database: str,
        user: str,
        password: str,
        port: int = 5432,
    ) -> None:
        if not all((host, database, user, password)):
            raise SavedTourError("PostgreSQL saved-tour settings are incomplete.")
        self._pool = ConnectionPool(
            conninfo="",
            kwargs={
                "host": host,
                "port": port,
                "dbname": database,
                "user": user,
                "password": password,
                "connect_timeout": 5,
                "row_factory": dict_row,
            },
            min_size=0,
            max_size=4,
            timeout=5,
            open=True,
        )
        try:
            with self._pool.connection() as connection:
                with connection.cursor() as cursor:
                    cursor.execute("SELECT to_regclass('saved_tours')")
                    table_exists = cursor.fetchone()["to_regclass"] is not None
                    if table_exists:
                        cursor.execute(
                            "SELECT 1 FROM pg_indexes WHERE schemaname = "
                            "current_schema() AND tablename = 'saved_tours' "
                            "AND indexname = 'saved_tours_by_owner_saved_at_id'"
                        )
                        if cursor.fetchone() is None:
                            cursor.execute("SELECT 1 FROM saved_tours LIMIT 1")
                            if cursor.fetchone() is not None:
                                raise SavedTourError(
                                    "Populated PostgreSQL saved-tour storage is missing "
                                    "its list index. Build the index during maintenance "
                                    "before starting the app."
                                )
                create_postgres_schema(connection)
        except SavedTourError:
            self._pool.close()
            raise
        except Exception as error:
            self._pool.close()
            raise SavedTourError(
                "Could not initialize PostgreSQL saved-tour storage."
            ) from error

    def close(self) -> None:
        self._pool.close()

    def save(self, owner_token: str, plan: SightseeingPlan) -> SavedTour:
        owner_hash = SavedTourRepository.owner_hash(owner_token)
        snapshot = json.dumps(
            {
                "schema_version": SNAPSHOT_SCHEMA_VERSION,
                "plan": plan.model_dump(mode="json"),
            },
            ensure_ascii=False,
            separators=(",", ":"),
        )
        saved_at = datetime.now(timezone.utc).isoformat()
        title = f"{plan.destination} · {plan.start_date.isoformat()}"
        tour_id = uuid4().hex
        try:
            with self._pool.connection() as connection, connection.cursor() as cursor:
                cursor.execute(
                    """
                        INSERT INTO saved_tours (
                            id, owner_hash, plan_id, revision, title, destination,
                            start_date, day_count, saved_at, plan_snapshot
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        ON CONFLICT (owner_hash, plan_id, revision) DO NOTHING
                        RETURNING id, title, destination, start_date, day_count,
                                  revision, saved_at, plan_snapshot
                        """,
                    (
                        tour_id,
                        owner_hash,
                        plan.plan_id,
                        plan.revision,
                        title,
                        plan.destination,
                        plan.start_date.isoformat(),
                        plan.day_count,
                        saved_at,
                        snapshot,
                    ),
                )
                row = cursor.fetchone()
                if row is None:
                    cursor.execute(
                        """
                            SELECT id, title, destination, start_date, day_count,
                                   revision, saved_at, plan_snapshot
                            FROM saved_tours
                            WHERE owner_hash = %s AND plan_id = %s AND revision = %s
                            """,
                        (owner_hash, plan.plan_id, plan.revision),
                    )
                    row = cursor.fetchone()
                if row is None:
                    raise SavedTourError(
                        "Could not find the saved tour after a conflict."
                    )
        except (psycopg.Error, PoolClosed, PoolTimeout) as error:
            raise SavedTourError("Could not save the tour snapshot.") from error
        return SavedTourRepository._tour_from_row(row)

    def list(
        self, owner_token: str, *, cursor: str | None = None, limit: int = LIST_LIMIT
    ) -> SavedTourPage:
        if not 1 <= limit <= LIST_LIMIT:
            raise ValueError(f"limit must be between 1 and {LIST_LIMIT}")
        position = (
            SavedTourRepository.decode_cursor(cursor) if cursor is not None else None
        )
        query = """
            SELECT id, title, destination, start_date, day_count, revision, saved_at
            FROM saved_tours WHERE owner_hash = %s
        """
        parameters: list[object] = [SavedTourRepository.owner_hash(owner_token)]
        if position is not None:
            query += " AND (saved_at, id) < (%s, %s)"
            parameters.extend(position)
        query += " ORDER BY saved_at DESC, id DESC LIMIT %s"
        parameters.append(limit + 1)
        try:
            with (
                self._pool.connection() as connection,
                connection.cursor() as database_cursor,
            ):
                database_cursor.execute(query, parameters)
                rows = database_cursor.fetchall()
        except (psycopg.Error, PoolClosed, PoolTimeout) as error:
            raise SavedTourError("Could not list saved tours.") from error
        items = [SavedTourRepository._summary_from_row(row) for row in rows[:limit]]
        has_more = len(rows) > limit
        return SavedTourPage(
            items=items,
            has_more=has_more,
            next_cursor=(
                SavedTourRepository.encode_cursor(items[-1])
                if has_more and items
                else None
            ),
        )

    def get(self, owner_token: str, tour_id: str) -> SavedTour | None:
        try:
            with self._pool.connection() as connection, connection.cursor() as cursor:
                cursor.execute(
                    """
                        SELECT id, title, destination, start_date, day_count, revision,
                               saved_at, plan_snapshot
                        FROM saved_tours WHERE owner_hash = %s AND id = %s
                        """,
                    (SavedTourRepository.owner_hash(owner_token), tour_id),
                )
                row = cursor.fetchone()
        except (psycopg.Error, PoolClosed, PoolTimeout) as error:
            raise SavedTourError("Could not read the saved tour.") from error
        return SavedTourRepository._tour_from_row(row) if row is not None else None

    def delete(self, owner_token: str, tour_id: str) -> bool:
        try:
            with self._pool.connection() as connection, connection.cursor() as cursor:
                cursor.execute(
                    "DELETE FROM saved_tours WHERE owner_hash = %s AND id = %s",
                    (SavedTourRepository.owner_hash(owner_token), tour_id),
                )
                return cursor.rowcount == 1
        except (psycopg.Error, PoolClosed, PoolTimeout) as error:
            raise SavedTourError("Could not delete the saved tour.") from error


def create_postgres_schema(
    connection: psycopg.Connection[dict], *, create_index: bool = True
) -> None:
    """Create fresh archive schema; existing tables retain exact TEXT snapshots."""

    with connection.cursor() as cursor:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS saved_tours (
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
        """)
        if create_index:
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS saved_tours_by_owner_saved_at_id
                ON saved_tours (owner_hash, saved_at DESC, id DESC)
            """)
