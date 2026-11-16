"""Merge duplicate application accounts in PostgreSQL after manual review.

The default command performs preflight checks and rolls back. Before ``--apply``,
back up PostgreSQL, pause app writes, and verify ownership of both login methods
outside this script. A canonical admin may self-audit only with the explicit
confirmation flag and only when the database has no other active admin. This
never links Auth0 profiles or chooses accounts by email.
"""

from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime, timezone
from uuid import UUID, uuid4

import psycopg
from psycopg.rows import dict_row


class ReconcileError(RuntimeError):
    """The requested account reconciliation is not safe to apply."""


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ReconcileError(message)


def require_uuid(value: str, label: str) -> None:
    try:
        canonical = str(UUID(value))
    except (TypeError, ValueError) as error:
        raise ReconcileError(f"{label} must be a UUID.") from error
    require(canonical == value, f"{label} must use canonical UUID format.")


def postgres_settings() -> dict[str, str | int]:
    settings: dict[str, str | int] = {
        "host": os.getenv("GTP_SAVED_TOURS_POSTGRES_HOST", ""),
        "port": int(os.getenv("GTP_SAVED_TOURS_POSTGRES_PORT", "5432")),
        "dbname": os.getenv("GTP_SAVED_TOURS_POSTGRES_DATABASE", ""),
        "user": os.getenv("GTP_SAVED_TOURS_POSTGRES_USER", ""),
        "password": os.getenv("GTP_SAVED_TOURS_POSTGRES_PASSWORD", ""),
        "connect_timeout": 5,
        "row_factory": dict_row,
    }
    if not all(settings.values()):
        raise ReconcileError("PostgreSQL account settings are incomplete.")
    return settings


def reconcile(
    *,
    canonical_user_id: str,
    secondary_user_id: str,
    actor_user_id: str,
    reason: str,
    apply: bool,
    canonical_actor_confirmed: bool = False,
) -> tuple[int, int, int, list[str]]:
    require_uuid(canonical_user_id, "Canonical user ID")
    require_uuid(secondary_user_id, "Secondary user ID")
    require_uuid(actor_user_id, "Admin actor ID")
    require(canonical_user_id != secondary_user_id, "Account IDs must differ.")
    settings = postgres_settings()
    with psycopg.connect(**settings) as connection, connection.cursor() as cursor:
        # Serialize operator repairs and align with the identity-link maintenance gate.
        cursor.execute(
            "SELECT pg_advisory_xact_lock(hashtextextended('auth_account_reconcile', 0))"
        )
        cursor.execute("""SELECT to_regclass('account_merges') AS merge_table,
            to_regclass('saved_tours') AS tours_table""")
        tables = cursor.fetchone()
        merge_table, tours_table = tables["merge_table"], tables["tours_table"]
        require(merge_table is not None, "Run the auth account-merge migration first.")
        require(tours_table is not None, "Saved-tour storage is missing.")

        ids = sorted((canonical_user_id, secondary_user_id))
        cursor.execute(
            """SELECT id, email, access_status, is_admin FROM app_users
            WHERE id = ANY(%s) ORDER BY id FOR UPDATE""",
            (ids,),
        )
        users = {row["id"]: row for row in cursor.fetchall()}
        require(len(users) == 2, "Both application accounts must exist.")
        canonical = users[canonical_user_id]
        secondary = users[secondary_user_id]
        require(
            canonical["access_status"] != "merged"
            and secondary["access_status"] != "merged",
            "A merged account cannot be reconciled again.",
        )
        require(
            canonical["access_status"] in {"active", "pending", "blocked"}
            and secondary["access_status"] in {"active", "pending", "blocked"},
            "Account access state is unsupported; resolve it before reconciliation.",
        )
        canonical_email = str(canonical["email"] or "").strip().casefold()
        secondary_email = str(secondary["email"] or "").strip().casefold()
        require(
            canonical_email and canonical_email == secondary_email,
            "Accounts must have the same nonempty verified email.",
        )
        cursor.execute(
            """SELECT id FROM app_users
            WHERE lower(trim(email)) = %s AND access_status <> 'merged'
            ORDER BY id FOR UPDATE""",
            (canonical_email,),
        )
        matching_users = {row["id"] for row in cursor.fetchall()}
        require(
            {canonical_user_id, secondary_user_id}.issubset(matching_users),
            "The explicitly selected accounts do not share the same normalized email.",
        )
        remaining_email_user_ids = sorted(
            matching_users - {canonical_user_id, secondary_user_id}
        )
        require(
            canonical["is_admin"] == secondary["is_admin"]
            or (canonical["is_admin"] and not secondary["is_admin"]),
            "A secondary administrator cannot be merged into a non-admin canonical account.",
        )
        require(
            canonical["access_status"] == secondary["access_status"]
            or (
                canonical["access_status"] == "active"
                and secondary["access_status"] == "pending"
            ),
            "Account access states conflict.",
        )
        cursor.execute(
            """SELECT 1 FROM account_merges
            WHERE secondary_user_id = ANY(%s) OR canonical_user_id = %s
            LIMIT 1""",
            ([canonical_user_id, secondary_user_id], secondary_user_id),
        )
        require(
            cursor.fetchone() is None,
            "A merged alias cannot be used as a source or canonical account.",
        )
        require(
            actor_user_id != secondary_user_id,
            "The secondary account cannot be the audit actor.",
        )
        require(
            actor_user_id != canonical_user_id
            or not apply
            or canonical_actor_confirmed,
            "Applying with the canonical account as actor requires explicit self-audit confirmation.",
        )
        if apply and actor_user_id == canonical_user_id:
            cursor.execute(
                """SELECT id FROM app_users
                WHERE id NOT IN (%s, %s) AND access_status = 'active'
                AND is_admin = TRUE AND NOT EXISTS (
                    SELECT 1 FROM account_merges
                    WHERE secondary_user_id = app_users.id
                ) ORDER BY id FOR UPDATE""",
                (canonical_user_id, secondary_user_id),
            )
            require(
                not cursor.fetchall(),
                "Use a separate active admin actor when one exists.",
            )
        cursor.execute(
            """SELECT id FROM app_users
            WHERE id = %s AND access_status = 'active' AND is_admin = TRUE
            AND NOT EXISTS (
                SELECT 1 FROM account_merges
                WHERE secondary_user_id = app_users.id
            ) FOR UPDATE""",
            (actor_user_id,),
        )
        require(cursor.fetchone() is not None, "An active administrator is required.")

        cursor.execute(
            """SELECT user_id, issuer, subject FROM auth_identities
            WHERE user_id = ANY(%s) ORDER BY issuer, subject FOR UPDATE""",
            (ids,),
        )
        identities = cursor.fetchall()
        primary_identities = [
            row for row in identities if row["user_id"] == canonical_user_id
        ]
        secondary_identities = [
            row for row in identities if row["user_id"] == secondary_user_id
        ]
        require(
            primary_identities and secondary_identities,
            "Each account must own at least one identity.",
        )
        require(
            len({row["issuer"] for row in identities}) == 1,
            "Identity issuers differ; resolve them separately.",
        )

        cursor.execute(
            "SELECT id FROM saved_tours WHERE owner_user_id = %s FOR UPDATE",
            (canonical_user_id,),
        )
        canonical_tour_count = len(cursor.fetchall())
        cursor.execute(
            "SELECT id FROM saved_tours WHERE owner_user_id = %s FOR UPDATE",
            (secondary_user_id,),
        )
        secondary_tour_count = len(cursor.fetchall())
        cursor.execute(
            "SELECT verifier_hash FROM auth_sessions WHERE user_id = %s FOR UPDATE",
            (secondary_user_id,),
        )
        secondary_session_count = len(cursor.fetchall())
        created_at = datetime.now(timezone.utc).isoformat()

        cursor.execute(
            "UPDATE auth_identities SET user_id = %s WHERE user_id = %s",
            (canonical_user_id, secondary_user_id),
        )
        require(
            cursor.rowcount == len(secondary_identities),
            "Identity ownership changed during reconciliation.",
        )
        cursor.execute(
            "UPDATE saved_tours SET owner_user_id = %s WHERE owner_user_id = %s",
            (canonical_user_id, secondary_user_id),
        )
        require(
            cursor.rowcount == secondary_tour_count,
            "Saved-tour ownership changed during reconciliation.",
        )
        cursor.execute(
            "UPDATE auth_sessions SET revoked_at = %s WHERE user_id = %s AND revoked_at IS NULL",
            (int(datetime.now(timezone.utc).timestamp()), secondary_user_id),
        )
        cursor.execute(
            "DELETE FROM auth_sessions WHERE user_id = %s", (secondary_user_id,)
        )
        cursor.execute(
            "UPDATE app_users SET access_status = 'merged' WHERE id = %s",
            (secondary_user_id,),
        )
        require(
            cursor.rowcount == 1, "Secondary account changed during reconciliation."
        )
        cursor.execute(
            """INSERT INTO account_merges
            (secondary_user_id, canonical_user_id, actor_user_id, reason, created_at)
            VALUES (%s, %s, %s, %s, %s)""",
            (
                secondary_user_id,
                canonical_user_id,
                actor_user_id,
                reason,
                created_at,
            ),
        )
        cursor.executemany(
            """INSERT INTO account_access_events
            (id, user_id, actor_user_id, action, created_at)
            VALUES (%s, %s, %s, %s, %s)""",
            [
                (
                    str(uuid4()),
                    secondary_user_id,
                    actor_user_id,
                    "account_merge_source",
                    created_at,
                ),
                (
                    str(uuid4()),
                    canonical_user_id,
                    actor_user_id,
                    "account_merge_received",
                    created_at,
                ),
            ],
        )

        cursor.execute(
            "SELECT count(*) AS count FROM saved_tours WHERE owner_user_id = %s",
            (canonical_user_id,),
        )
        require(
            cursor.fetchone()["count"] == canonical_tour_count + secondary_tour_count,
            "Saved-tour count changed during reconciliation.",
        )
        cursor.execute(
            "SELECT count(*) AS count FROM auth_identities WHERE user_id = %s",
            (secondary_user_id,),
        )
        require(
            cursor.fetchone()["count"] == 0, "Secondary identities remain attached."
        )
        cursor.execute(
            "SELECT count(*) AS count FROM auth_sessions WHERE user_id = %s",
            (secondary_user_id,),
        )
        require(cursor.fetchone()["count"] == 0, "Secondary sessions remain active.")

        if apply:
            connection.commit()
        else:
            connection.rollback()
        return (
            secondary_tour_count,
            secondary_session_count,
            len(secondary_identities),
            remaining_email_user_ids,
        )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--canonical-user-id", required=True)
    parser.add_argument("--secondary-user-id", required=True)
    parser.add_argument("--actor-user-id", required=True)
    parser.add_argument("--reason", required=True, help="ticket or verification record")
    parser.add_argument("--ownership-confirmed", action="store_true")
    parser.add_argument("--backup-complete", action="store_true")
    parser.add_argument("--writes-paused", action="store_true")
    parser.add_argument(
        "--canonical-actor-confirmed",
        action="store_true",
        help="confirm the canonical admin is the audit actor because no independent admin exists",
    )
    parser.add_argument("--apply", action="store_true", help="commit reconciliation")
    args = parser.parse_args()
    try:
        reason = args.reason.strip()
        require(
            bool(reason) and len(reason) <= 400,
            "Reason must contain 1 to 400 characters.",
        )
        if args.apply:
            require(
                args.ownership_confirmed, "Confirm ownership of both identities first."
            )
            require(args.backup_complete, "Confirm a verified backup first.")
            require(args.writes_paused, "Confirm application writes are paused first.")
            if args.actor_user_id == args.canonical_user_id:
                require(
                    args.canonical_actor_confirmed,
                    "Confirm the canonical admin will be recorded as the audit actor.",
                )
            else:
                require(
                    not args.canonical_actor_confirmed,
                    "Canonical-actor confirmation only applies when the actor is canonical.",
                )
        else:
            require(
                not args.canonical_actor_confirmed,
                "Canonical-actor confirmation is only valid with --apply.",
            )
        tours, sessions, identities, remaining_email_user_ids = reconcile(
            canonical_user_id=args.canonical_user_id,
            secondary_user_id=args.secondary_user_id,
            actor_user_id=args.actor_user_id,
            reason=reason,
            apply=args.apply,
            canonical_actor_confirmed=args.canonical_actor_confirmed,
        )
    except (ReconcileError, psycopg.Error, ValueError) as error:
        print(f"Account reconciliation failed: {error}", file=sys.stderr)
        return 1
    mode = "applied" if args.apply else "dry-run rolled back"
    print(
        f"Account reconciliation {mode}; identities: {identities}; "
        f"saved tours moved: {tours}; secondary sessions revoked: {sessions}."
    )
    if remaining_email_user_ids:
        print(
            "Other unmerged account IDs with this email need operator review: "
            + ", ".join(remaining_email_user_ids)
            + "."
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
