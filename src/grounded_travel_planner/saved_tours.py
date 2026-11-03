"""Durable, owner-scoped snapshots of explicitly saved sightseeing plans."""

from __future__ import annotations

import hashlib
import json
import secrets
import sqlite3
from base64 import b64decode, urlsafe_b64encode
from binascii import Error as BinasciiError
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from grounded_travel_planner.contracts import SightseeingPlan

SNAPSHOT_SCHEMA_VERSION = 1
LIST_LIMIT = 50
SAVED_TOURS_SCHEMA_VERSION = 2
ACCOUNT_SAVED_TOURS_SCHEMA_VERSION = 3
LEGACY_OWNER_INDEX_NAME = "saved_tours_by_owner"
OWNER_SAVED_AT_ID_INDEX_NAME = "saved_tours_by_owner_saved_at_id"
USER_SAVED_AT_ID_INDEX_NAME = "saved_tours_by_user_saved_at_id"
CURSOR_VERSION = 1
MAX_CURSOR_LENGTH = 512


class SavedTourError(RuntimeError):
    """A durable saved-tour store could not complete an operation safely."""


class InvalidSavedTourCursor(ValueError):
    """A list cursor does not identify a valid saved-tour position."""


@dataclass(frozen=True)
class SavedTourSummary:
    """Small list representation, intentionally excluding the plan snapshot."""

    id: str
    title: str
    destination: str
    start_date: str
    day_count: int
    revision: int
    saved_at: str

    def payload(self) -> dict[str, object]:
        return {
            "id": self.id,
            "title": self.title,
            "destination": self.destination,
            "start_date": self.start_date,
            "day_count": self.day_count,
            "revision": self.revision,
            "saved_at": self.saved_at,
        }


@dataclass(frozen=True)
class SavedTour(SavedTourSummary):
    """A durable snapshot of one accepted plan revision."""

    plan: SightseeingPlan

    def payload(self) -> dict[str, object]:
        return {**super().payload(), "plan": self.plan.model_dump(mode="json")}


@dataclass(frozen=True)
class SavedTourPage:
    """A bounded page of owner-scoped saved-tour list items."""

    items: list[SavedTourSummary]
    has_more: bool
    next_cursor: str | None


@dataclass(frozen=True)
class SavedTourClaimConflict:
    """A legacy snapshot that cannot be claimed without losing a revision."""

    legacy_tour_id: str
    account_tour_id: str
    plan_id: str
    revision: int


@dataclass(frozen=True)
class SavedTourClaimResult:
    """Outcome of claiming legacy browser-owned snapshots for one account."""

    claimed_count: int
    already_claimed_count: int
    conflicts: list[SavedTourClaimConflict]


class SavedTourRepository:
    """SQLite storage that only persists an explicitly supplied plan snapshot."""

    def __init__(self, database_path: Path) -> None:
        self._database_path = Path(database_path)
        self._database_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    @staticmethod
    def owner_hash(owner_token: str) -> str:
        """Return the only owner identifier allowed to reach SQLite."""

        return hashlib.sha256(owner_token.encode("utf-8")).hexdigest()

    def save(self, owner_token: str, plan: SightseeingPlan) -> SavedTour:
        """Save a snapshot once per owner/plan/revision and return that snapshot."""

        owner_hash = self.owner_hash(owner_token)
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
        existing_row: sqlite3.Row | None = None
        try:
            with self._connection() as connection:
                try:
                    connection.execute(
                        """
                        INSERT INTO saved_tours (
                            id, owner_hash, plan_id, revision, title, destination,
                            start_date, day_count, saved_at, plan_snapshot
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                except sqlite3.IntegrityError:
                    existing_row = connection.execute(
                        """
                        SELECT id, title, destination, start_date, day_count, revision,
                               saved_at, plan_snapshot
                        FROM saved_tours
                        WHERE owner_hash = ? AND owner_user_id IS NULL
                          AND plan_id = ? AND revision = ?
                        """,
                        (owner_hash, plan.plan_id, plan.revision),
                    ).fetchone()
                    if existing_row is None:
                        raise
        except sqlite3.Error as error:
            raise SavedTourError("Could not save the tour snapshot.") from error
        return (
            self._tour_from_row(existing_row)
            if existing_row is not None
            else SavedTour(
                id=tour_id,
                title=title,
                destination=plan.destination,
                start_date=plan.start_date.isoformat(),
                day_count=plan.day_count,
                revision=plan.revision,
                saved_at=saved_at,
                plan=plan.model_copy(deep=True),
            )
        )

    def save_for_user(self, user_id: str, plan: SightseeingPlan) -> SavedTour:
        """Save a snapshot once for an authenticated account and plan revision."""

        self._validate_user_id(user_id)
        snapshot = self._snapshot(plan)
        saved_at = datetime.now(timezone.utc).isoformat()
        title = self._title(plan)
        tour_id = uuid4().hex
        try:
            with self._connection() as connection:
                connection.execute("BEGIN IMMEDIATE")
                existing_row = connection.execute(
                    """
                    SELECT id, title, destination, start_date, day_count, revision,
                           saved_at, plan_snapshot
                    FROM saved_tours
                    WHERE owner_user_id = ? AND plan_id = ? AND revision = ?
                    """,
                    (user_id, plan.plan_id, plan.revision),
                ).fetchone()
                if existing_row is None:
                    connection.execute(
                        """
                        INSERT INTO saved_tours (
                            id, owner_hash, owner_user_id, plan_id, revision, title,
                            destination, start_date, day_count, saved_at, plan_snapshot
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            tour_id,
                            self._account_owner_hash(),
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
        except sqlite3.Error as error:
            raise SavedTourError("Could not save the tour snapshot.") from error
        return (
            self._tour_from_row(existing_row)
            if existing_row is not None
            else SavedTour(
                id=tour_id,
                title=title,
                destination=plan.destination,
                start_date=plan.start_date.isoformat(),
                day_count=plan.day_count,
                revision=plan.revision,
                saved_at=saved_at,
                plan=plan.model_copy(deep=True),
            )
        )

    def list(
        self, owner_token: str, *, cursor: str | None = None, limit: int = LIST_LIMIT
    ) -> SavedTourPage:
        if not 1 <= limit <= LIST_LIMIT:
            raise ValueError(f"limit must be between 1 and {LIST_LIMIT}")
        position = self.decode_cursor(cursor) if cursor is not None else None
        query = """
            SELECT id, title, destination, start_date, day_count, revision, saved_at
            FROM saved_tours
            WHERE owner_hash = ? AND owner_user_id IS NULL
        """
        parameters: list[object] = [self.owner_hash(owner_token)]
        if position is not None:
            saved_at, tour_id = position
            query += """
                AND (saved_at, id) < (?, ?)
            """
            parameters.extend((saved_at, tour_id))
        query += " ORDER BY saved_at DESC, id DESC LIMIT ?"
        parameters.append(limit + 1)
        try:
            with self._connection() as connection:
                rows = connection.execute(query, parameters).fetchall()
        except sqlite3.Error as error:
            raise SavedTourError("Could not list saved tours.") from error
        items = [self._summary_from_row(row) for row in rows[:limit]]
        has_more = len(rows) > limit
        return SavedTourPage(
            items=items,
            has_more=has_more,
            next_cursor=self.encode_cursor(items[-1]) if has_more and items else None,
        )

    def list_for_user(
        self, user_id: str, *, cursor: str | None = None, limit: int = LIST_LIMIT
    ) -> SavedTourPage:
        self._validate_user_id(user_id)
        return self._list_for_column(
            "owner_user_id", user_id, cursor=cursor, limit=limit
        )

    @classmethod
    def encode_cursor(cls, item: SavedTourSummary) -> str:
        """Encode the final visible key without exposing an offset."""

        payload = json.dumps(
            {"v": CURSOR_VERSION, "s": item.saved_at, "i": item.id},
            separators=(",", ":"),
        ).encode("utf-8")
        return urlsafe_b64encode(payload).decode("ascii").rstrip("=")

    @classmethod
    def decode_cursor(cls, cursor: str) -> tuple[str, str]:
        """Decode a bounded, versioned cursor into the SQLite ordering key."""

        if not cursor or len(cursor) > MAX_CURSOR_LENGTH:
            raise InvalidSavedTourCursor("Saved-tour cursor is malformed.")
        try:
            padding = "=" * (-len(cursor) % 4)
            payload = b64decode(
                (cursor + padding).encode("ascii"), altchars=b"-_", validate=True
            )
            decoded = json.loads(payload.decode("utf-8"))
            if (
                not isinstance(decoded, dict)
                or set(decoded) != {"v", "s", "i"}
                or decoded["v"] != CURSOR_VERSION
                or not isinstance(decoded["s"], str)
                or not isinstance(decoded["i"], str)
                or len(decoded["s"]) > 40
                or len(decoded["i"]) != 32
                or any(
                    character not in "0123456789abcdef" for character in decoded["i"]
                )
            ):
                raise ValueError("invalid cursor payload")
            datetime.fromisoformat(decoded["s"])
        except (
            BinasciiError,
            UnicodeDecodeError,
            ValueError,
            json.JSONDecodeError,
        ) as error:
            raise InvalidSavedTourCursor("Saved-tour cursor is malformed.") from error
        return decoded["s"], decoded["i"]

    def _list_for_column(
        self,
        column: str,
        owner: str,
        *,
        cursor: str | None,
        limit: int,
    ) -> SavedTourPage:
        if not 1 <= limit <= LIST_LIMIT:
            raise ValueError(f"limit must be between 1 and {LIST_LIMIT}")
        position = self.decode_cursor(cursor) if cursor is not None else None
        query = f"""
            SELECT id, title, destination, start_date, day_count, revision, saved_at
            FROM saved_tours WHERE {column} = ?
        """
        parameters: list[object] = [owner]
        if position is not None:
            query += " AND (saved_at, id) < (?, ?)"
            parameters.extend(position)
        query += " ORDER BY saved_at DESC, id DESC LIMIT ?"
        parameters.append(limit + 1)
        try:
            with self._connection() as connection:
                rows = connection.execute(query, parameters).fetchall()
        except sqlite3.Error as error:
            raise SavedTourError("Could not list saved tours.") from error
        items = [self._summary_from_row(row) for row in rows[:limit]]
        has_more = len(rows) > limit
        return SavedTourPage(
            items=items,
            has_more=has_more,
            next_cursor=self.encode_cursor(items[-1]) if has_more and items else None,
        )

    def get(self, owner_token: str, tour_id: str) -> SavedTour | None:
        try:
            with self._connection() as connection:
                row = connection.execute(
                    """
                    SELECT id, title, destination, start_date, day_count, revision,
                           saved_at, plan_snapshot
                    FROM saved_tours
                    WHERE owner_hash = ? AND owner_user_id IS NULL AND id = ?
                    """,
                    (self.owner_hash(owner_token), tour_id),
                ).fetchone()
        except sqlite3.Error as error:
            raise SavedTourError("Could not read the saved tour.") from error
        return self._tour_from_row(row) if row is not None else None

    def delete(self, owner_token: str, tour_id: str) -> bool:
        try:
            with self._connection() as connection:
                result = connection.execute(
                    """DELETE FROM saved_tours
                       WHERE owner_hash = ? AND owner_user_id IS NULL AND id = ?""",
                    (self.owner_hash(owner_token), tour_id),
                )
        except sqlite3.Error as error:
            raise SavedTourError("Could not delete the saved tour.") from error
        return result.rowcount == 1

    def get_for_user(self, user_id: str, tour_id: str) -> SavedTour | None:
        self._validate_user_id(user_id)
        try:
            with self._connection() as connection:
                row = connection.execute(
                    """
                    SELECT id, title, destination, start_date, day_count, revision,
                           saved_at, plan_snapshot
                    FROM saved_tours WHERE owner_user_id = ? AND id = ?
                    """,
                    (user_id, tour_id),
                ).fetchone()
        except sqlite3.Error as error:
            raise SavedTourError("Could not read the saved tour.") from error
        return self._tour_from_row(row) if row is not None else None

    def delete_for_user(self, user_id: str, tour_id: str) -> bool:
        self._validate_user_id(user_id)
        try:
            with self._connection() as connection:
                result = connection.execute(
                    "DELETE FROM saved_tours WHERE owner_user_id = ? AND id = ?",
                    (user_id, tour_id),
                )
        except sqlite3.Error as error:
            raise SavedTourError("Could not delete the saved tour.") from error
        return result.rowcount == 1

    def claim_for_user(
        self, user_id: str, legacy_owner_token: str
    ) -> SavedTourClaimResult:
        """Claim only unclaimed legacy rows, preserving every duplicate revision."""

        self._validate_user_id(user_id)
        legacy_hash = self.owner_hash(legacy_owner_token)
        try:
            with self._connection() as connection:
                connection.execute("BEGIN IMMEDIATE")
                legacy_rows = connection.execute(
                    """
                    SELECT id, plan_id, revision FROM saved_tours
                    WHERE owner_hash = ? AND owner_user_id IS NULL
                    ORDER BY id
                    """,
                    (legacy_hash,),
                ).fetchall()
                existing = connection.execute(
                    """
                    SELECT id, plan_id, revision FROM saved_tours
                    WHERE owner_user_id = ?
                    """,
                    (user_id,),
                ).fetchall()
                claimed = connection.execute(
                    """
                    SELECT COUNT(*) AS count FROM saved_tours
                    WHERE owner_hash = ? AND owner_user_id = ?
                    """,
                    (legacy_hash, user_id),
                ).fetchone()
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
                    connection.executemany(
                        "UPDATE saved_tours SET owner_user_id = ? WHERE id = ?",
                        [(user_id, tour_id) for tour_id in claim_ids],
                    )
        except sqlite3.Error as error:
            raise SavedTourError("Could not claim legacy saved tours.") from error
        return SavedTourClaimResult(
            claimed_count=len(claim_ids),
            already_claimed_count=int(claimed["count"]),
            conflicts=conflicts,
        )

    def _initialize(self) -> None:
        try:
            with self._connection() as connection:
                connection.execute("PRAGMA journal_mode=WAL")
                table_exists = connection.execute(
                    "SELECT 1 FROM sqlite_master WHERE type = 'table' "
                    "AND name = 'saved_tours'"
                ).fetchone()
                if table_exists is None:
                    self._create_schema_v3(connection)
                    return
                version = int(connection.execute("PRAGMA user_version").fetchone()[0])
                if version < SAVED_TOURS_SCHEMA_VERSION:
                    has_rows = connection.execute(
                        "SELECT 1 FROM saved_tours LIMIT 1"
                    ).fetchone()
                    if has_rows is not None:
                        raise SavedTourError(
                            "Saved-tour storage requires migration. Run "
                            "python scripts/migrate_saved_tours_index.py "
                            f"{self._database_path} before starting the app."
                        )
                    self._create_index_v2(connection)
                    connection.execute(
                        f"DROP INDEX IF EXISTS {LEGACY_OWNER_INDEX_NAME}"
                    )
                    connection.execute(
                        f"PRAGMA user_version = {SAVED_TOURS_SCHEMA_VERSION}"
                    )
                else:
                    index_exists = connection.execute(
                        "SELECT 1 FROM sqlite_master WHERE type = 'index' "
                        "AND name = ?",
                        (OWNER_SAVED_AT_ID_INDEX_NAME,),
                    ).fetchone()
                    if index_exists is None:
                        raise SavedTourError(
                            "Saved-tour storage is missing its v2 index."
                        )
                account_column = connection.execute(
                    "PRAGMA table_info(saved_tours)"
                ).fetchall()
                has_account_column = any(
                    row["name"] == "owner_user_id" for row in account_column
                )
                account_index = connection.execute(
                    "SELECT 1 FROM sqlite_master WHERE type = 'index' AND name = ?",
                    (USER_SAVED_AT_ID_INDEX_NAME,),
                ).fetchone()
                if not has_account_column or account_index is None:
                    has_rows = connection.execute(
                        "SELECT 1 FROM saved_tours LIMIT 1"
                    ).fetchone()
                    if has_rows is not None:
                        raise SavedTourError(
                            "Saved-tour storage requires account migration. Run "
                            "python scripts/migrate_saved_tours_account_ownership.py "
                            f"--sqlite {self._database_path} before starting the app."
                        )
                    self._create_account_schema(connection)
        except sqlite3.Error as error:
            raise SavedTourError("Could not initialize saved-tour storage.") from error

    @staticmethod
    def _create_schema_v3(connection: sqlite3.Connection) -> None:
        connection.execute("""
            CREATE TABLE saved_tours (
                id TEXT PRIMARY KEY,
                owner_hash TEXT NOT NULL,
                owner_user_id TEXT,
                plan_id TEXT NOT NULL,
                revision INTEGER NOT NULL,
                title TEXT NOT NULL,
                destination TEXT NOT NULL,
                start_date TEXT NOT NULL,
                day_count INTEGER NOT NULL,
                saved_at TEXT NOT NULL,
                plan_snapshot TEXT NOT NULL,
                UNIQUE(owner_hash, plan_id, revision)
            )
            """)
        SavedTourRepository._create_index_v2(connection)
        SavedTourRepository._create_account_schema(connection)
        connection.execute(
            f"PRAGMA user_version = {ACCOUNT_SAVED_TOURS_SCHEMA_VERSION}"
        )

    @staticmethod
    def _create_index_v2(connection: sqlite3.Connection) -> None:
        connection.execute(
            f"CREATE INDEX IF NOT EXISTS {OWNER_SAVED_AT_ID_INDEX_NAME} "
            "ON saved_tours(owner_hash, saved_at DESC, id DESC)"
        )

    @staticmethod
    def _create_account_schema(connection: sqlite3.Connection) -> None:
        columns = connection.execute("PRAGMA table_info(saved_tours)").fetchall()
        if not any(row["name"] == "owner_user_id" for row in columns):
            connection.execute("ALTER TABLE saved_tours ADD COLUMN owner_user_id TEXT")
        connection.execute(
            f"CREATE INDEX IF NOT EXISTS {USER_SAVED_AT_ID_INDEX_NAME} "
            "ON saved_tours(owner_user_id, saved_at DESC, id DESC)"
        )
        connection.execute(
            f"PRAGMA user_version = {ACCOUNT_SAVED_TOURS_SCHEMA_VERSION}"
        )

    @staticmethod
    def _validate_user_id(user_id: str) -> None:
        if not user_id:
            raise ValueError("user_id is required")

    @staticmethod
    def _account_owner_hash() -> str:
        """Store a non-recoverable random placeholder for account-owned rows."""

        return hashlib.sha256(secrets.token_urlsafe(32).encode("utf-8")).hexdigest()

    @staticmethod
    def _snapshot(plan: SightseeingPlan) -> str:
        return json.dumps(
            {
                "schema_version": SNAPSHOT_SCHEMA_VERSION,
                "plan": plan.model_dump(mode="json"),
            },
            ensure_ascii=False,
            separators=(",", ":"),
        )

    @staticmethod
    def _title(plan: SightseeingPlan) -> str:
        return f"{plan.destination} · {plan.start_date.isoformat()}"

    @contextmanager
    def _connection(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self._database_path, timeout=5)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA busy_timeout=5000")
        try:
            with connection:
                yield connection
        finally:
            connection.close()

    @staticmethod
    def _summary_from_row(row: sqlite3.Row) -> SavedTourSummary:
        return SavedTourSummary(
            id=str(row["id"]),
            title=str(row["title"]),
            destination=str(row["destination"]),
            start_date=str(row["start_date"]),
            day_count=int(row["day_count"]),
            revision=int(row["revision"]),
            saved_at=str(row["saved_at"]),
        )

    @classmethod
    def _tour_from_row(cls, row: sqlite3.Row) -> SavedTour:
        try:
            snapshot = json.loads(str(row["plan_snapshot"]))
            if snapshot.get("schema_version") != SNAPSHOT_SCHEMA_VERSION:
                raise ValueError("Unsupported saved-tour snapshot schema.")
            plan = SightseeingPlan.model_validate(snapshot["plan"])
        except (AttributeError, KeyError, TypeError, ValueError) as error:
            raise SavedTourError("The saved tour snapshot is invalid.") from error
        return SavedTour(plan=plan, **cls._summary_from_row(row).__dict__)
