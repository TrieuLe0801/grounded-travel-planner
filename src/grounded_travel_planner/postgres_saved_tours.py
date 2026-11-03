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
    SavedTourClaimConflict,
    SavedTourClaimResult,
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
                        legacy_index_missing = cursor.fetchone() is None
                        cursor.execute(
                            "SELECT 1 FROM information_schema.columns "
                            "WHERE table_schema = current_schema() "
                            "AND table_name = 'saved_tours' "
                            "AND column_name = 'owner_user_id'"
                        )
                        account_column_missing = cursor.fetchone() is None
                        cursor.execute(
                            "SELECT 1 FROM pg_indexes WHERE schemaname = "
                            "current_schema() AND tablename = 'saved_tours' "
                            "AND indexname = 'saved_tours_by_user_saved_at_id'"
                        )
                        account_index_missing = cursor.fetchone() is None
                        if (
                            legacy_index_missing
                            or account_column_missing
                            or account_index_missing
                        ):
                            cursor.execute("SELECT 1 FROM saved_tours LIMIT 1")
                            if cursor.fetchone() is not None:
                                raise SavedTourError(
                                    "Populated PostgreSQL saved-tour storage requires "
                                    "explicit migration. Run "
                                    "scripts/migrate_saved_tours_account_ownership.py "
                                    "during maintenance before starting the app."
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
                            WHERE owner_hash = %s AND owner_user_id IS NULL
                              AND plan_id = %s AND revision = %s
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

    def save_for_user(self, user_id: str, plan: SightseeingPlan) -> SavedTour:
        SavedTourRepository._validate_user_id(user_id)
        snapshot = SavedTourRepository._snapshot(plan)
        saved_at = datetime.now(timezone.utc).isoformat()
        title = SavedTourRepository._title(plan)
        tour_id = uuid4().hex
        try:
            with self._pool.connection() as connection, connection.cursor() as cursor:
                cursor.execute(
                    "SELECT pg_advisory_xact_lock(hashtextextended(%s, 0))",
                    (f"{user_id}:{plan.plan_id}:{plan.revision}",),
                )
                cursor.execute(
                    """
                    SELECT id, title, destination, start_date, day_count, revision,
                           saved_at, plan_snapshot
                    FROM saved_tours
                    WHERE owner_user_id = %s AND plan_id = %s AND revision = %s
                    """,
                    (user_id, plan.plan_id, plan.revision),
                )
                row = cursor.fetchone()
                if row is None:
                    cursor.execute(
                        """
                        INSERT INTO saved_tours (
                            id, owner_hash, owner_user_id, plan_id, revision, title,
                            destination, start_date, day_count, saved_at, plan_snapshot
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        RETURNING id, title, destination, start_date, day_count,
                                  revision, saved_at, plan_snapshot
                        """,
                        (
                            tour_id,
                            SavedTourRepository._account_owner_hash(),
                            user_id,
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
        except (psycopg.Error, PoolClosed, PoolTimeout) as error:
            raise SavedTourError("Could not save the tour snapshot.") from error
        if row is None:
            raise SavedTourError("Could not save the tour snapshot.")
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
            FROM saved_tours WHERE owner_hash = %s AND owner_user_id IS NULL
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

    def list_for_user(
        self, user_id: str, *, cursor: str | None = None, limit: int = LIST_LIMIT
    ) -> SavedTourPage:
        SavedTourRepository._validate_user_id(user_id)
        return self._list_for_column(
            "owner_user_id", user_id, cursor=cursor, limit=limit
        )

    def _list_for_column(
        self, column: str, owner: str, *, cursor: str | None, limit: int
    ) -> SavedTourPage:
        if not 1 <= limit <= LIST_LIMIT:
            raise ValueError(f"limit must be between 1 and {LIST_LIMIT}")
        position = (
            SavedTourRepository.decode_cursor(cursor) if cursor is not None else None
        )
        query = f"""
            SELECT id, title, destination, start_date, day_count, revision, saved_at
            FROM saved_tours WHERE {column} = %s
        """
        parameters: list[object] = [owner]
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
                        FROM saved_tours
                        WHERE owner_hash = %s AND owner_user_id IS NULL AND id = %s
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
                    """DELETE FROM saved_tours
                       WHERE owner_hash = %s AND owner_user_id IS NULL AND id = %s""",
                    (SavedTourRepository.owner_hash(owner_token), tour_id),
                )
                return cursor.rowcount == 1
        except (psycopg.Error, PoolClosed, PoolTimeout) as error:
            raise SavedTourError("Could not delete the saved tour.") from error

    def get_for_user(self, user_id: str, tour_id: str) -> SavedTour | None:
        SavedTourRepository._validate_user_id(user_id)
        try:
            with self._pool.connection() as connection, connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT id, title, destination, start_date, day_count, revision,
                           saved_at, plan_snapshot
                    FROM saved_tours WHERE owner_user_id = %s AND id = %s
                    """,
                    (user_id, tour_id),
                )
                row = cursor.fetchone()
        except (psycopg.Error, PoolClosed, PoolTimeout) as error:
            raise SavedTourError("Could not read the saved tour.") from error
        return SavedTourRepository._tour_from_row(row) if row is not None else None

    def delete_for_user(self, user_id: str, tour_id: str) -> bool:
        SavedTourRepository._validate_user_id(user_id)
        try:
            with self._pool.connection() as connection, connection.cursor() as cursor:
                cursor.execute(
                    "DELETE FROM saved_tours WHERE owner_user_id = %s AND id = %s",
                    (user_id, tour_id),
                )
                return cursor.rowcount == 1
        except (psycopg.Error, PoolClosed, PoolTimeout) as error:
            raise SavedTourError("Could not delete the saved tour.") from error

    def claim_for_user(
        self, user_id: str, legacy_owner_token: str
    ) -> SavedTourClaimResult:
        SavedTourRepository._validate_user_id(user_id)
        legacy_hash = SavedTourRepository.owner_hash(legacy_owner_token)
        try:
            with self._pool.connection() as connection, connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT id, plan_id, revision FROM saved_tours
                    WHERE owner_hash = %s AND owner_user_id IS NULL
                    ORDER BY id FOR UPDATE
                    """,
                    (legacy_hash,),
                )
                legacy_rows = cursor.fetchall()
                claim_keys = sorted(
                    {f"{row['plan_id']}:{row['revision']}" for row in legacy_rows}
                )
                for claim_key in claim_keys:
                    cursor.execute(
                        "SELECT pg_advisory_xact_lock(hashtextextended(%s, 0))",
                        (f"{user_id}:{claim_key}",),
                    )
                cursor.execute(
                    """
                    SELECT id, plan_id, revision FROM saved_tours
                    WHERE owner_user_id = %s FOR UPDATE
                    """,
                    (user_id,),
                )
                existing = cursor.fetchall()
                cursor.execute(
                    """
                    SELECT COUNT(*) AS count FROM saved_tours
                    WHERE owner_hash = %s AND owner_user_id = %s
                    """,
                    (legacy_hash, user_id),
                )
                already_claimed = int(cursor.fetchone()["count"])
                existing_by_revision = {
                    (str(row["plan_id"]), int(row["revision"])): str(row["id"])
                    for row in existing
                }
                conflicts: list[SavedTourClaimConflict] = []
                claim_ids: list[str] = []
                for row in legacy_rows:
                    key = (str(row["plan_id"]), int(row["revision"]))
                    account_tour_id = existing_by_revision.get(key)
                    if account_tour_id is not None:
                        conflicts.append(
                            SavedTourClaimConflict(
                                legacy_tour_id=str(row["id"]),
                                account_tour_id=account_tour_id,
                                plan_id=key[0],
                                revision=key[1],
                            )
                        )
                    else:
                        claim_ids.append(str(row["id"]))
                        existing_by_revision[key] = str(row["id"])
                if claim_ids:
                    cursor.execute(
                        "UPDATE saved_tours SET owner_user_id = %s WHERE id = ANY(%s)",
                        (user_id, claim_ids),
                    )
        except (psycopg.Error, PoolClosed, PoolTimeout) as error:
            raise SavedTourError("Could not claim legacy saved tours.") from error
        return SavedTourClaimResult(
            claimed_count=len(claim_ids),
            already_claimed_count=already_claimed,
            conflicts=conflicts,
        )


def create_postgres_schema(
    connection: psycopg.Connection[dict], *, create_index: bool = True
) -> None:
    """Create fresh archive schema; existing tables retain exact TEXT snapshots."""

    with connection.cursor() as cursor:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS saved_tours (
                id TEXT COLLATE "C" PRIMARY KEY,
                owner_hash TEXT NOT NULL,
                owner_user_id TEXT,
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
            cursor.execute(
                "ALTER TABLE saved_tours ADD COLUMN IF NOT EXISTS owner_user_id TEXT"
            )
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS saved_tours_by_owner_saved_at_id
                ON saved_tours (owner_hash, saved_at DESC, id DESC)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS saved_tours_by_user_saved_at_id
                ON saved_tours (owner_user_id, saved_at DESC, id DESC)
            """)
