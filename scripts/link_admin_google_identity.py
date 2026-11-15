"""Link one existing Google login to its existing email-OTP administrator.

Run inside the configured app container after a PostgreSQL backup. The default
mode executes every check and write in a transaction, then rolls it back. Pass
``--apply`` only after reviewing the dry-run result. This is a one-time repair,
not a general email-based account linking policy.
"""

from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime, timezone
from uuid import uuid4

import psycopg


class LinkError(RuntimeError):
    """The two records cannot be linked safely."""


def require(condition: bool, message: str) -> None:
    if not condition:
        raise LinkError(message)


def link(email: str, *, apply: bool) -> tuple[int, int]:
    settings = {
        "host": os.environ["GTP_SAVED_TOURS_POSTGRES_HOST"],
        "port": int(os.environ.get("GTP_SAVED_TOURS_POSTGRES_PORT", "5432")),
        "dbname": os.environ["GTP_SAVED_TOURS_POSTGRES_DATABASE"],
        "user": os.environ["GTP_SAVED_TOURS_POSTGRES_USER"],
        "password": os.environ["GTP_SAVED_TOURS_POSTGRES_PASSWORD"],
        "connect_timeout": 5,
    }
    with psycopg.connect(**settings) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """SELECT id, access_status, is_admin FROM app_users
                WHERE lower(email) = lower(%s) ORDER BY id FOR UPDATE""",
                (email,),
            )
            users = cursor.fetchall()
            require(bool(users), "No accounts found for this email.")
            cursor.execute(
                """SELECT user_id, issuer, subject FROM auth_identities
                WHERE user_id = ANY(%s) ORDER BY user_id FOR UPDATE""",
                ([row[0] for row in users],),
            )
            identities = cursor.fetchall()
            admin_candidates = [
                row
                for row in users
                if row[1] == "active"
                and row[2] is True
                and any(
                    identity[0] == row[0] and identity[2].startswith("email|")
                    for identity in identities
                )
            ]
            google_candidates = [
                row
                for row in users
                if row[1] == "pending"
                and row[2] is False
                and any(
                    identity[0] == row[0] and identity[2].startswith("google-oauth2|")
                    for identity in identities
                )
            ]
            require(
                len(admin_candidates) == 1 and len(google_candidates) == 1,
                "Expected one email admin and one pending Google account.",
            )
            admin_id, pending_id = admin_candidates[0][0], google_candidates[0][0]
            admin_identities = [row for row in identities if row[0] == admin_id]
            pending_identities = [row for row in identities if row[0] == pending_id]
            require(
                len(admin_identities) == 1
                and admin_identities[0][2].startswith("email|")
                and len(pending_identities) == 1
                and pending_identities[0][2].startswith("google-oauth2|")
                and admin_identities[0][1] == pending_identities[0][1],
                "Expected one email identity and one Google identity from the same issuer.",
            )
            _, issuer, subject = pending_identities[0]
            # Match the lock used by find_or_create_user during Auth0 callbacks.
            identity_key = f"{len(issuer)}:{issuer}{subject}"
            cursor.execute(
                "SELECT pg_advisory_xact_lock(hashtextextended(%s, 0))",
                (identity_key,),
            )
            cursor.execute(
                "SELECT count(*) FROM saved_tours WHERE owner_user_id = %s",
                (pending_id,),
            )
            require(cursor.fetchone()[0] == 0, "Google account owns saved tours.")
            cursor.execute(
                "SELECT count(*) FROM account_access_events WHERE user_id = %s",
                (pending_id,),
            )
            require(cursor.fetchone()[0] == 0, "Google account has access history.")
            cursor.execute(
                "SELECT count(*) FROM saved_tours WHERE owner_user_id = %s",
                (admin_id,),
            )
            tour_count = cursor.fetchone()[0]
            cursor.execute(
                "SELECT count(*) FROM auth_sessions WHERE user_id = %s",
                (pending_id,),
            )
            session_count = cursor.fetchone()[0]
            cursor.execute(
                """UPDATE auth_sessions SET revoked_at = %s
                WHERE user_id = %s AND revoked_at IS NULL""",
                (int(datetime.now(timezone.utc).timestamp()), pending_id),
            )
            cursor.execute(
                """UPDATE auth_identities SET user_id = %s
                WHERE issuer = %s AND subject = %s AND user_id = %s""",
                (admin_id, issuer, subject, pending_id),
            )
            require(cursor.rowcount == 1, "Google identity changed during link.")
            cursor.execute(
                "DELETE FROM auth_sessions WHERE user_id = %s", (pending_id,)
            )
            cursor.execute("DELETE FROM app_users WHERE id = %s", (pending_id,))
            require(cursor.rowcount == 1, "Google account changed during link.")
            cursor.execute(
                """INSERT INTO account_access_events
                (id, user_id, actor_user_id, action, created_at)
                VALUES (%s, %s, NULL, 'link_google_identity', %s)""",
                (str(uuid4()), admin_id, datetime.now(timezone.utc).isoformat()),
            )
            cursor.execute(
                "SELECT count(*) FROM saved_tours WHERE owner_user_id = %s",
                (admin_id,),
            )
            require(cursor.fetchone()[0] == tour_count, "Admin tour count changed.")
            if apply:
                connection.commit()
            else:
                connection.rollback()
            return tour_count, session_count


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--email", required=True, help="exact existing account email")
    parser.add_argument("--apply", action="store_true", help="commit the link")
    args = parser.parse_args()
    try:
        email = args.email.strip()
        require(bool(email), "Email is required.")
        tours, sessions = link(email, apply=args.apply)
    except (KeyError, ValueError, LinkError, psycopg.Error) as error:
        print(f"Identity link failed: {error}", file=sys.stderr)
        return 1
    mode = "applied" if args.apply else "dry-run rolled back"
    print(f"Identity link {mode}; admin tours: {tours}; old sessions: {sessions}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
