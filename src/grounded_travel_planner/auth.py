"""OIDC BFF primitives and durable application authentication sessions."""

from __future__ import annotations

import base64
import binascii
import hashlib
import hmac
import json
import os
import secrets
import sqlite3
import time
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal, Protocol
from urllib.parse import urlencode, urlsplit
from urllib.request import urlopen
from uuid import uuid4

import jwt
import psycopg
from jwt import PyJWKClient
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool, PoolClosed, PoolTimeout

from utils.sqlite import prepare_private_sqlite_database

AUTH_COOKIE_NAME = "gtp_auth"
AUTH_PENDING_COOKIE_NAME = "gtp_auth_pending"
AUTH_IDLE_SECONDS = 30 * 60
AUTH_ABSOLUTE_SECONDS = 30 * 24 * 60 * 60
AUTH_PENDING_SECONDS = 10 * 60


class AuthError(RuntimeError):
    """Authentication could not be completed safely."""


class AccountNotFound(AuthError):
    """Requested application account does not exist."""


class AccessChangeConflict(AuthError):
    """Requested access change would violate administrator safeguards."""


class OidcProvider(Protocol):
    """Small boundary for the external identity provider."""

    def authorization_url(
        self,
        *,
        state: str,
        nonce: str,
        code_verifier: str,
        redirect_uri: str,
        screen_hint: Literal["signup"] | None = None,
    ) -> str: ...

    def verify_callback(
        self, *, code: str, nonce: str, code_verifier: str, redirect_uri: str
    ) -> VerifiedIdentity: ...

    def logout_url(self, *, return_to: str) -> str: ...


@dataclass(frozen=True)
class VerifiedIdentity:
    issuer: str
    subject: str
    email: str | None = None


def _identity_lock_key(identity: VerifiedIdentity) -> str:
    """Build an unambiguous PostgreSQL text key without forbidden NUL bytes."""

    return f"{len(identity.issuer)}:{identity.issuer}{identity.subject}"


@dataclass(frozen=True)
class AuthenticatedUser:
    user_id: str
    email: str | None
    csrf_token: str
    access_status: str = "active"
    is_admin: bool = False


@dataclass(frozen=True)
class AccountRecord:
    id: str
    email: str | None
    created_at: str
    access_status: str
    is_admin: bool


def _account_record(row: Any) -> AccountRecord:
    return AccountRecord(
        id=str(row["id"]),
        email=row["email"],
        created_at=str(row["created_at"]),
        access_status=str(row["access_status"]),
        is_admin=bool(row["is_admin"]),
    )


@dataclass(frozen=True)
class _SessionRecord:
    user_id: str
    email: str | None
    csrf_token: str
    idle_expires_at: int
    absolute_expires_at: int


def _now() -> int:
    return int(time.time())


def _hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _csrf_for(token: str) -> str:
    secret = os.getenv("GTP_AUTH_SESSION_SECRET", "")
    if not secret:
        raise AuthError("The auth session secret is not configured.")
    return _b64(
        hmac.new(secret.encode("utf-8"), token.encode("utf-8"), hashlib.sha256).digest()
    )


def _b64(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")


def code_challenge(verifier: str) -> str:
    return _b64(hashlib.sha256(verifier.encode("ascii")).digest())


def safe_return_to(value: str | None) -> str:
    """Only local absolute paths are safe redirect targets."""

    if value is None or value == "":
        return "/"
    if (
        not value.startswith("/")
        or value.startswith("//")
        or "\\" in value
        or any(character.isspace() or ord(character) < 32 for character in value)
    ):
        raise AuthError("Invalid return target.")
    return value


class PendingLoginCodec:
    """Signed, short-lived OIDC state stored only in an HttpOnly cookie."""

    def __init__(self, secret: str) -> None:
        if len(secret) < 32:
            raise AuthError(
                "The auth session secret must contain at least 32 characters."
            )
        self._secret = secret.encode("utf-8")

    def issue(self, *, return_to: str) -> tuple[str, dict[str, str]]:
        payload = {
            "state": secrets.token_urlsafe(32),
            "nonce": secrets.token_urlsafe(32),
            "verifier": secrets.token_urlsafe(64),
            "return_to": safe_return_to(return_to),
            "expires_at": _now() + AUTH_PENDING_SECONDS,
        }
        encoded = _b64(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
        signature = _b64(
            hmac.new(self._secret, encoded.encode("ascii"), hashlib.sha256).digest()
        )
        return f"{encoded}.{signature}", payload

    def read(self, token: str) -> dict[str, str]:
        try:
            encoded, provided = token.split(".", 1)
            expected = _b64(
                hmac.new(self._secret, encoded.encode("ascii"), hashlib.sha256).digest()
            )
            if not hmac.compare_digest(expected, provided):
                raise AuthError("Invalid login state.")
            raw: dict[str, Any] = json.loads(
                base64.urlsafe_b64decode(encoded + "=" * (-len(encoded) % 4))
            )
            required = {"state", "nonce", "verifier", "return_to", "expires_at"}
            if set(raw) != required or int(raw["expires_at"]) < _now():
                raise AuthError("Expired login state.")
            return {key: str(value) for key, value in raw.items()}
        except (ValueError, TypeError, json.JSONDecodeError, binascii.Error) as error:
            raise AuthError("Invalid login state.") from error


class Auth0OidcProvider:
    """Auth0 Authorization Code + PKCE adapter; tokens never leave this class."""

    def __init__(self, *, issuer: str, client_id: str, client_secret: str) -> None:
        if not all((issuer, client_id, client_secret)):
            raise AuthError("Auth0 settings are incomplete.")
        endpoint = self._https_origin(issuer)
        self._issuer = f"{endpoint}/"
        self._endpoint = endpoint
        self._client_id = client_id
        self._client_secret = client_secret

    @staticmethod
    def _https_origin(issuer: str) -> str:
        """Accept only an HTTPS origin before sending a client secret to Auth0."""

        try:
            parsed = urlsplit(issuer)
            port = parsed.port
        except ValueError as error:
            raise AuthError("Auth0 issuer must be a valid HTTPS origin.") from error
        if (
            parsed.scheme != "https"
            or not parsed.hostname
            or parsed.username is not None
            or parsed.password is not None
            or parsed.path not in {"", "/"}
            or parsed.query
            or parsed.fragment
        ):
            raise AuthError("Auth0 issuer must be a valid HTTPS origin.")
        authority = parsed.hostname
        if ":" in authority and not authority.startswith("["):
            authority = f"[{authority}]"
        if port is not None:
            authority = f"{authority}:{port}"
        return f"https://{authority}"

    @classmethod
    def from_environment(cls) -> Auth0OidcProvider:
        return cls(
            issuer=os.getenv("GTP_AUTH0_ISSUER", ""),
            client_id=os.getenv("GTP_AUTH0_CLIENT_ID", ""),
            client_secret=os.getenv("GTP_AUTH0_CLIENT_SECRET", ""),
        )

    def authorization_url(
        self,
        *,
        state: str,
        nonce: str,
        code_verifier: str,
        redirect_uri: str,
        screen_hint: Literal["signup"] | None = None,
    ) -> str:
        # Let Auth0 reuse an existing tenant session for SSO.
        parameters = {
            "response_type": "code",
            "client_id": self._client_id,
            "redirect_uri": redirect_uri,
            "scope": "openid profile email",
            "state": state,
            "nonce": nonce,
            "code_challenge": code_challenge(code_verifier),
            "code_challenge_method": "S256",
        }
        if screen_hint is not None:
            parameters["screen_hint"] = screen_hint
        query = urlencode(parameters)
        return f"{self._endpoint}/authorize?{query}"

    def verify_callback(
        self, *, code: str, nonce: str, code_verifier: str, redirect_uri: str
    ) -> VerifiedIdentity:
        import urllib.parse
        import urllib.request

        body = urllib.parse.urlencode(
            {
                "grant_type": "authorization_code",
                "client_id": self._client_id,
                "client_secret": self._client_secret,
                "code": code,
                "redirect_uri": redirect_uri,
                "code_verifier": code_verifier,
            }
        ).encode("ascii")
        request = urllib.request.Request(
            f"{self._endpoint}/oauth/token",
            data=body,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            method="POST",
        )
        try:
            with urlopen(request, timeout=10) as response:
                result = json.loads(response.read())
            token = result["id_token"]
            key = PyJWKClient(
                f"{self._endpoint}/.well-known/jwks.json"
            ).get_signing_key_from_jwt(token)
            claims = jwt.decode(
                token,
                key.key,
                algorithms=["RS256"],
                audience=self._client_id,
                issuer=self._issuer,
                options={"require": ["exp", "iat", "iss", "sub", "aud", "nonce"]},
            )
        except (
            Exception
        ) as error:  # provider errors intentionally become generic client error
            raise AuthError("Auth0 could not verify this login.") from error
        if not hmac.compare_digest(str(claims.get("nonce", "")), nonce):
            raise AuthError("Auth0 login nonce did not match.")
        return VerifiedIdentity(
            issuer=str(claims["iss"]),
            subject=str(claims["sub"]),
            email=claims.get("email"),
        )

    def logout_url(self, *, return_to: str) -> str:
        """Build Auth0's browser logout URL without exposing any provider token."""

        query = urlencode({"client_id": self._client_id, "returnTo": return_to})
        return f"{self._endpoint}/v2/logout?{query}"


class AuthRepository:
    """SQLite account/session store. Schema creation is an explicit migration."""

    def __init__(self, database_path: Path) -> None:
        self._database_path = Path(database_path)

    def migrate(self) -> None:
        """Create the fresh auth schema; invoke from an explicit maintenance step."""

        with self._connection() as connection:
            connection.executescript("""
                CREATE TABLE IF NOT EXISTS app_users (
                    id TEXT PRIMARY KEY, email TEXT, created_at TEXT NOT NULL,
                    access_status TEXT NOT NULL DEFAULT 'pending',
                    is_admin INTEGER NOT NULL DEFAULT 0
                );
                CREATE TABLE IF NOT EXISTS auth_identities (
                    issuer TEXT NOT NULL, subject TEXT NOT NULL, user_id TEXT NOT NULL,
                    PRIMARY KEY (issuer, subject), FOREIGN KEY(user_id) REFERENCES app_users(id)
                );
                CREATE TABLE IF NOT EXISTS auth_sessions (
                    verifier_hash TEXT PRIMARY KEY, user_id TEXT NOT NULL, csrf_hash TEXT NOT NULL,
                    idle_expires_at INTEGER NOT NULL, absolute_expires_at INTEGER NOT NULL,
                    revoked_at INTEGER, created_at TEXT NOT NULL,
                    FOREIGN KEY(user_id) REFERENCES app_users(id)
                );
                CREATE INDEX IF NOT EXISTS auth_sessions_expiry ON auth_sessions (idle_expires_at);
                CREATE TABLE IF NOT EXISTS account_access_events (
                    id TEXT PRIMARY KEY, user_id TEXT NOT NULL,
                    actor_user_id TEXT, action TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(user_id) REFERENCES app_users(id)
                );
                """)

    def migrate_admin(self) -> None:
        """Upgrade an existing auth database during an explicit write pause."""

        with self._connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            columns = {
                str(row["name"])
                for row in connection.execute("PRAGMA table_info(app_users)")
            }
            if not columns:
                raise AuthError("Authentication schema is missing.")
            if "access_status" not in columns:
                connection.execute(
                    "ALTER TABLE app_users ADD COLUMN access_status TEXT NOT NULL DEFAULT 'active'"
                )
            if "is_admin" not in columns:
                connection.execute(
                    "ALTER TABLE app_users ADD COLUMN is_admin INTEGER NOT NULL DEFAULT 0"
                )
            connection.execute("""CREATE TABLE IF NOT EXISTS account_access_events (
                id TEXT PRIMARY KEY, user_id TEXT NOT NULL, actor_user_id TEXT,
                action TEXT NOT NULL, created_at TEXT NOT NULL,
                FOREIGN KEY(user_id) REFERENCES app_users(id))""")

    def find_or_create_user(self, identity: VerifiedIdentity) -> tuple[str, str | None]:
        try:
            with self._connection() as connection:
                connection.execute("BEGIN IMMEDIATE")
                row = connection.execute(
                    """SELECT app_users.id, app_users.email FROM auth_identities
                    JOIN app_users ON app_users.id = auth_identities.user_id
                    WHERE issuer = ? AND subject = ?""",
                    (identity.issuer, identity.subject),
                ).fetchone()
                if row is not None:
                    return str(row["id"]), row["email"]
                user_id = str(uuid4())
                connection.execute(
                    """INSERT INTO app_users
                    (id, email, created_at, access_status, is_admin)
                    VALUES (?, ?, ?, 'pending', 0)""",
                    (user_id, identity.email, datetime.now(timezone.utc).isoformat()),
                )
                connection.execute(
                    "INSERT INTO auth_identities (issuer, subject, user_id) VALUES (?, ?, ?)",
                    (identity.issuer, identity.subject, user_id),
                )
                return user_id, identity.email
        except sqlite3.Error as error:
            raise AuthError("Authentication storage is unavailable.") from error

    def issue_session(self, user_id: str, email: str | None) -> tuple[str, str]:
        token = secrets.token_urlsafe(48)
        csrf = _csrf_for(token)
        now = _now()
        try:
            with self._connection() as connection:
                row = connection.execute(
                    "SELECT access_status FROM app_users WHERE id = ?",
                    (user_id,),
                ).fetchone()
                if row is None or row["access_status"] == "blocked":
                    raise AuthError("Account access is blocked.")
                connection.execute(
                    """INSERT INTO auth_sessions
                    (verifier_hash, user_id, csrf_hash, idle_expires_at, absolute_expires_at, created_at)
                    VALUES (?, ?, ?, ?, ?, ?)""",
                    (
                        _hash(token),
                        user_id,
                        _hash(csrf),
                        now + AUTH_IDLE_SECONDS,
                        now + AUTH_ABSOLUTE_SECONDS,
                        datetime.now(timezone.utc).isoformat(),
                    ),
                )
        except sqlite3.Error as error:
            raise AuthError("Authentication storage is unavailable.") from error
        return token, csrf

    def authenticated(self, token: str | None) -> AuthenticatedUser | None:
        if not token:
            return None
        now = _now()
        try:
            with self._connection() as connection:
                row = connection.execute(
                    """SELECT auth_sessions.user_id, app_users.email, app_users.access_status,
                    app_users.is_admin, auth_sessions.csrf_hash,
                    auth_sessions.idle_expires_at, auth_sessions.absolute_expires_at,
                    auth_sessions.revoked_at FROM auth_sessions JOIN app_users
                    ON app_users.id = auth_sessions.user_id WHERE verifier_hash = ?""",
                    (_hash(token),),
                ).fetchone()
                if (
                    row is None
                    or row["revoked_at"] is not None
                    or row["access_status"] == "blocked"
                    or now > min(row["idle_expires_at"], row["absolute_expires_at"])
                ):
                    return None
                connection.execute(
                    "UPDATE auth_sessions SET idle_expires_at = ? WHERE verifier_hash = ?",
                    (
                        min(now + AUTH_IDLE_SECONDS, row["absolute_expires_at"]),
                        _hash(token),
                    ),
                )
                return AuthenticatedUser(
                    str(row["user_id"]),
                    row["email"],
                    _csrf_for(token),
                    str(row["access_status"]),
                    bool(row["is_admin"]),
                )
        except sqlite3.Error as error:
            raise AuthError("Authentication storage is unavailable.") from error

    def verify_csrf(
        self, token: str | None, csrf: str | None
    ) -> AuthenticatedUser | None:
        if not token or not csrf:
            return None
        # Do not rotate here: callers need the supplied CSRF secret checked atomically.
        now = _now()
        try:
            with self._connection() as connection:
                row = connection.execute(
                    """SELECT auth_sessions.user_id, app_users.email,
                    app_users.access_status, app_users.is_admin, csrf_hash, idle_expires_at,
                    absolute_expires_at, revoked_at FROM auth_sessions JOIN app_users
                    ON app_users.id = auth_sessions.user_id WHERE verifier_hash = ?""",
                    (_hash(token),),
                ).fetchone()
                if (
                    row is None
                    or row["revoked_at"] is not None
                    or row["access_status"] == "blocked"
                    or now > min(row["idle_expires_at"], row["absolute_expires_at"])
                ):
                    return None
                if not hmac.compare_digest(str(row["csrf_hash"]), _hash(csrf)):
                    return None
                return AuthenticatedUser(
                    str(row["user_id"]),
                    row["email"],
                    csrf,
                    str(row["access_status"]),
                    bool(row["is_admin"]),
                )
        except sqlite3.Error as error:
            raise AuthError("Authentication storage is unavailable.") from error

    def list_users(self, limit: int = 50, offset: int = 0) -> list[AccountRecord]:
        if not 1 <= limit <= 100 or offset < 0:
            raise ValueError("Invalid account page.")
        try:
            with self._connection() as connection:
                rows = connection.execute(
                    """SELECT id, email, created_at, access_status, is_admin
                    FROM app_users ORDER BY created_at DESC, id DESC LIMIT ? OFFSET ?""",
                    (limit, offset),
                ).fetchall()
                return [_account_record(row) for row in rows]
        except sqlite3.Error as error:
            raise AuthError("Authentication storage is unavailable.") from error

    def get_user(self, user_id: str) -> AccountRecord | None:
        try:
            with self._connection() as connection:
                row = connection.execute(
                    """SELECT id, email, created_at, access_status, is_admin
                    FROM app_users WHERE id = ?""",
                    (user_id,),
                ).fetchone()
                return _account_record(row) if row else None
        except sqlite3.Error as error:
            raise AuthError("Authentication storage is unavailable.") from error

    def set_access(
        self, user_id: str, active: bool, actor_user_id: str
    ) -> AccountRecord:
        """Change access and revoke sessions atomically with an audit entry."""

        try:
            with self._connection() as connection:
                connection.execute("BEGIN IMMEDIATE")
                actor = connection.execute(
                    "SELECT is_admin, access_status FROM app_users WHERE id = ?",
                    (actor_user_id,),
                ).fetchone()
                if (
                    not actor
                    or not actor["is_admin"]
                    or actor["access_status"] != "active"
                ):
                    raise AccessChangeConflict("An active administrator is required.")
                target = connection.execute(
                    """SELECT id, email, created_at, access_status, is_admin
                    FROM app_users WHERE id = ?""",
                    (user_id,),
                ).fetchone()
                if target is None:
                    raise AccountNotFound("Account does not exist.")
                if not active and user_id == actor_user_id:
                    raise AccessChangeConflict(
                        "Administrators cannot block themselves."
                    )
                if not active and target["is_admin"]:
                    count = connection.execute("""SELECT COUNT(*) FROM app_users
                        WHERE is_admin = 1 AND access_status = 'active'""").fetchone()[
                        0
                    ]
                    if count <= 1:
                        raise AccessChangeConflict(
                            "The last active administrator cannot be blocked."
                        )
                status = "active" if active else "blocked"
                if target["access_status"] != status:
                    connection.execute(
                        "UPDATE app_users SET access_status = ? WHERE id = ?",
                        (status, user_id),
                    )
                    if not active:
                        connection.execute(
                            "UPDATE auth_sessions SET revoked_at = ? WHERE user_id = ? AND revoked_at IS NULL",
                            (_now(), user_id),
                        )
                    connection.execute(
                        """INSERT INTO account_access_events
                        (id, user_id, actor_user_id, action, created_at)
                        VALUES (?, ?, ?, ?, ?)""",
                        (
                            str(uuid4()),
                            user_id,
                            actor_user_id,
                            status,
                            datetime.now(timezone.utc).isoformat(),
                        ),
                    )
                return AccountRecord(
                    user_id,
                    target["email"],
                    str(target["created_at"]),
                    status,
                    bool(target["is_admin"]),
                )
        except sqlite3.Error as error:
            raise AuthError("Authentication storage is unavailable.") from error

    def bootstrap_admin(self, user_id: str) -> AccountRecord:
        """Activate the first admin only from an explicit maintenance command."""

        try:
            with self._connection() as connection:
                connection.execute("BEGIN IMMEDIATE")
                if connection.execute(
                    "SELECT 1 FROM app_users WHERE is_admin = 1 LIMIT 1"
                ).fetchone():
                    raise AccessChangeConflict("An administrator already exists.")
                target = connection.execute(
                    """SELECT id, email, created_at, access_status, is_admin
                    FROM app_users WHERE id = ?""",
                    (user_id,),
                ).fetchone()
                if target is None:
                    raise AccountNotFound("Account does not exist.")
                connection.execute(
                    "UPDATE app_users SET is_admin = 1, access_status = 'active' WHERE id = ?",
                    (user_id,),
                )
                connection.execute(
                    """INSERT INTO account_access_events
                    (id, user_id, actor_user_id, action, created_at)
                    VALUES (?, ?, NULL, 'bootstrap_admin', ?)""",
                    (str(uuid4()), user_id, datetime.now(timezone.utc).isoformat()),
                )
                return AccountRecord(
                    user_id, target["email"], str(target["created_at"]), "active", True
                )
        except sqlite3.Error as error:
            raise AuthError("Authentication storage is unavailable.") from error

    def revoke_user_sessions(self, user_id: str) -> None:
        try:
            with self._connection() as connection:
                connection.execute(
                    "UPDATE auth_sessions SET revoked_at = ? WHERE user_id = ? AND revoked_at IS NULL",
                    (_now(), user_id),
                )
        except sqlite3.Error as error:
            raise AuthError("Authentication storage is unavailable.") from error

    def revoke(self, token: str | None) -> None:
        if not token:
            return
        try:
            with self._connection() as connection:
                connection.execute(
                    "UPDATE auth_sessions SET revoked_at = ? WHERE verifier_hash = ?",
                    (_now(), _hash(token)),
                )
        except sqlite3.Error as error:
            raise AuthError("Authentication storage is unavailable.") from error

    @contextmanager
    def _connection(self) -> Iterator[sqlite3.Connection]:
        prepare_private_sqlite_database(self._database_path)
        connection = sqlite3.connect(self._database_path)
        connection.row_factory = sqlite3.Row
        try:
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()


class PostgresAuthRepository:
    """PostgreSQL implementation; its migration is deliberately never automatic."""

    def __init__(
        self, *, host: str, database: str, user: str, password: str, port: int = 5432
    ) -> None:
        if not all((host, database, user, password)):
            raise AuthError("PostgreSQL auth settings are incomplete.")
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

    def close(self) -> None:
        self._pool.close()

    def find_or_create_user(self, identity: VerifiedIdentity) -> tuple[str, str | None]:
        try:
            with self._pool.connection() as connection, connection.cursor() as cursor:
                cursor.execute(
                    "SELECT pg_advisory_xact_lock(hashtextextended(%s, 0))",
                    (_identity_lock_key(identity),),
                )
                cursor.execute(
                    """SELECT app_users.id, app_users.email FROM auth_identities JOIN app_users
                    ON app_users.id = auth_identities.user_id WHERE issuer = %s AND subject = %s""",
                    (identity.issuer, identity.subject),
                )
                row = cursor.fetchone()
                if row is not None:
                    return str(row["id"]), row["email"]
                user_id = str(uuid4())
                cursor.execute(
                    """INSERT INTO app_users
                    (id, email, created_at, access_status, is_admin)
                    VALUES (%s, %s, %s, 'pending', FALSE)""",
                    (user_id, identity.email, datetime.now(timezone.utc).isoformat()),
                )
                cursor.execute(
                    "INSERT INTO auth_identities (issuer, subject, user_id) VALUES (%s, %s, %s)",
                    (identity.issuer, identity.subject, user_id),
                )
                return user_id, identity.email
        except (psycopg.Error, PoolClosed, PoolTimeout) as error:
            raise AuthError("Authentication storage is unavailable.") from error

    def issue_session(self, user_id: str, email: str | None) -> tuple[str, str]:
        del email
        token, now = secrets.token_urlsafe(48), _now()
        csrf = _csrf_for(token)
        try:
            with self._pool.connection() as connection, connection.cursor() as cursor:
                cursor.execute(
                    "SELECT access_status FROM app_users WHERE id = %s FOR UPDATE",
                    (user_id,),
                )
                row = cursor.fetchone()
                if row is None or row["access_status"] == "blocked":
                    raise AuthError("Account access is blocked.")
                cursor.execute(
                    """INSERT INTO auth_sessions (verifier_hash, user_id, csrf_hash,
                    idle_expires_at, absolute_expires_at, created_at) VALUES (%s, %s, %s, %s, %s, %s)""",
                    (
                        _hash(token),
                        user_id,
                        _hash(csrf),
                        now + AUTH_IDLE_SECONDS,
                        now + AUTH_ABSOLUTE_SECONDS,
                        datetime.now(timezone.utc).isoformat(),
                    ),
                )
        except (psycopg.Error, PoolClosed, PoolTimeout) as error:
            raise AuthError("Authentication storage is unavailable.") from error
        return token, csrf

    def _record(
        self, token: str | None, csrf: str | None = None, *, rotate: bool = False
    ) -> AuthenticatedUser | None:
        if not token:
            return None
        now = _now()
        try:
            with self._pool.connection() as connection, connection.cursor() as cursor:
                cursor.execute(
                    """SELECT auth_sessions.user_id, app_users.email,
                    app_users.access_status, app_users.is_admin, auth_sessions.csrf_hash,
                    auth_sessions.idle_expires_at, auth_sessions.absolute_expires_at, auth_sessions.revoked_at
                    FROM auth_sessions JOIN app_users ON app_users.id = auth_sessions.user_id
                    WHERE verifier_hash = %s""",
                    (_hash(token),),
                )
                row = cursor.fetchone()
                if (
                    row is None
                    or row["revoked_at"] is not None
                    or row["access_status"] == "blocked"
                    or now > min(row["idle_expires_at"], row["absolute_expires_at"])
                ):
                    return None
                if csrf is not None and not hmac.compare_digest(
                    str(row["csrf_hash"]), _hash(csrf)
                ):
                    return None
                if rotate:
                    cursor.execute(
                        "UPDATE auth_sessions SET idle_expires_at = %s WHERE verifier_hash = %s",
                        (
                            min(now + AUTH_IDLE_SECONDS, row["absolute_expires_at"]),
                            _hash(token),
                        ),
                    )
                return AuthenticatedUser(
                    str(row["user_id"]),
                    row["email"],
                    _csrf_for(token),
                    str(row["access_status"]),
                    bool(row["is_admin"]),
                )
        except (psycopg.Error, PoolClosed, PoolTimeout) as error:
            raise AuthError("Authentication storage is unavailable.") from error

    def authenticated(self, token: str | None) -> AuthenticatedUser | None:
        return self._record(token, rotate=True)

    def verify_csrf(
        self, token: str | None, csrf: str | None
    ) -> AuthenticatedUser | None:
        return self._record(token, csrf)

    def list_users(self, limit: int = 50, offset: int = 0) -> list[AccountRecord]:
        if not 1 <= limit <= 100 or offset < 0:
            raise ValueError("Invalid account page.")
        try:
            with self._pool.connection() as connection, connection.cursor() as cursor:
                cursor.execute(
                    """SELECT id, email, created_at, access_status, is_admin
                    FROM app_users ORDER BY created_at DESC, id DESC LIMIT %s OFFSET %s""",
                    (limit, offset),
                )
                return [_account_record(row) for row in cursor.fetchall()]
        except (psycopg.Error, PoolClosed, PoolTimeout) as error:
            raise AuthError("Authentication storage is unavailable.") from error

    def get_user(self, user_id: str) -> AccountRecord | None:
        try:
            with self._pool.connection() as connection, connection.cursor() as cursor:
                cursor.execute(
                    """SELECT id, email, created_at, access_status, is_admin
                    FROM app_users WHERE id = %s""",
                    (user_id,),
                )
                row = cursor.fetchone()
                return _account_record(row) if row else None
        except (psycopg.Error, PoolClosed, PoolTimeout) as error:
            raise AuthError("Authentication storage is unavailable.") from error

    def set_access(
        self, user_id: str, active: bool, actor_user_id: str
    ) -> AccountRecord:
        try:
            with self._pool.connection() as connection, connection.cursor() as cursor:
                cursor.execute(
                    "SELECT pg_advisory_xact_lock(hashtextextended('app_user_admin_access', 0))"
                )
                cursor.execute(
                    "SELECT is_admin, access_status FROM app_users WHERE id = %s",
                    (actor_user_id,),
                )
                actor = cursor.fetchone()
                if (
                    not actor
                    or not actor["is_admin"]
                    or actor["access_status"] != "active"
                ):
                    raise AccessChangeConflict("An active administrator is required.")
                cursor.execute(
                    """SELECT id, email, created_at, access_status, is_admin
                    FROM app_users WHERE id = %s FOR UPDATE""",
                    (user_id,),
                )
                target = cursor.fetchone()
                if target is None:
                    raise AccountNotFound("Account does not exist.")
                if not active and user_id == actor_user_id:
                    raise AccessChangeConflict(
                        "Administrators cannot block themselves."
                    )
                if not active and target["is_admin"]:
                    cursor.execute("""SELECT COUNT(*) FROM app_users
                        WHERE is_admin = TRUE AND access_status = 'active'""")
                    if cursor.fetchone()["count"] <= 1:
                        raise AccessChangeConflict(
                            "The last active administrator cannot be blocked."
                        )
                status = "active" if active else "blocked"
                if target["access_status"] != status:
                    cursor.execute(
                        "UPDATE app_users SET access_status = %s WHERE id = %s",
                        (status, user_id),
                    )
                    if not active:
                        cursor.execute(
                            """UPDATE auth_sessions SET revoked_at = %s
                            WHERE user_id = %s AND revoked_at IS NULL""",
                            (_now(), user_id),
                        )
                    cursor.execute(
                        """INSERT INTO account_access_events
                        (id, user_id, actor_user_id, action, created_at)
                        VALUES (%s, %s, %s, %s, %s)""",
                        (
                            str(uuid4()),
                            user_id,
                            actor_user_id,
                            status,
                            datetime.now(timezone.utc).isoformat(),
                        ),
                    )
                return AccountRecord(
                    user_id,
                    target["email"],
                    str(target["created_at"]),
                    status,
                    bool(target["is_admin"]),
                )
        except (psycopg.Error, PoolClosed, PoolTimeout) as error:
            raise AuthError("Authentication storage is unavailable.") from error

    def bootstrap_admin(self, user_id: str) -> AccountRecord:
        """Activate the first admin only from an explicit maintenance command."""

        try:
            with self._pool.connection() as connection, connection.cursor() as cursor:
                cursor.execute(
                    "SELECT pg_advisory_xact_lock(hashtextextended('app_user_admin_access', 0))"
                )
                cursor.execute("SELECT 1 FROM app_users WHERE is_admin = TRUE LIMIT 1")
                if cursor.fetchone():
                    raise AccessChangeConflict("An administrator already exists.")
                cursor.execute(
                    """SELECT id, email, created_at FROM app_users
                    WHERE id = %s FOR UPDATE""",
                    (user_id,),
                )
                target = cursor.fetchone()
                if target is None:
                    raise AccountNotFound("Account does not exist.")
                cursor.execute(
                    """UPDATE app_users SET is_admin = TRUE,
                    access_status = 'active' WHERE id = %s""",
                    (user_id,),
                )
                cursor.execute(
                    """INSERT INTO account_access_events
                    (id, user_id, actor_user_id, action, created_at)
                    VALUES (%s, %s, NULL, 'bootstrap_admin', %s)""",
                    (str(uuid4()), user_id, datetime.now(timezone.utc).isoformat()),
                )
                return AccountRecord(
                    user_id, target["email"], str(target["created_at"]), "active", True
                )
        except (psycopg.Error, PoolClosed, PoolTimeout) as error:
            raise AuthError("Authentication storage is unavailable.") from error

    def revoke_user_sessions(self, user_id: str) -> None:
        try:
            with self._pool.connection() as connection, connection.cursor() as cursor:
                cursor.execute(
                    """UPDATE auth_sessions SET revoked_at = %s
                    WHERE user_id = %s AND revoked_at IS NULL""",
                    (_now(), user_id),
                )
        except (psycopg.Error, PoolClosed, PoolTimeout) as error:
            raise AuthError("Authentication storage is unavailable.") from error

    def revoke(self, token: str | None) -> None:
        if not token:
            return
        try:
            with self._pool.connection() as connection, connection.cursor() as cursor:
                cursor.execute(
                    "UPDATE auth_sessions SET revoked_at = %s WHERE verifier_hash = %s",
                    (_now(), _hash(token)),
                )
        except (psycopg.Error, PoolClosed, PoolTimeout) as error:
            raise AuthError("Authentication storage is unavailable.") from error


def create_postgres_auth_schema(
    connection: psycopg.Connection[dict[str, Any]],
) -> None:
    """Explicit maintenance migration for the three auth tables."""

    with connection.cursor() as cursor:
        cursor.execute("""CREATE TABLE IF NOT EXISTS app_users (
            id TEXT PRIMARY KEY, email TEXT, created_at TEXT NOT NULL,
            access_status TEXT NOT NULL DEFAULT 'pending',
            is_admin BOOLEAN NOT NULL DEFAULT FALSE)""")
        cursor.execute("""CREATE TABLE IF NOT EXISTS auth_identities (
            issuer TEXT NOT NULL, subject TEXT NOT NULL, user_id TEXT NOT NULL REFERENCES app_users(id),
            PRIMARY KEY (issuer, subject))""")
        cursor.execute("""CREATE TABLE IF NOT EXISTS auth_sessions (
            verifier_hash TEXT PRIMARY KEY, user_id TEXT NOT NULL REFERENCES app_users(id),
            csrf_hash TEXT NOT NULL, idle_expires_at BIGINT NOT NULL, absolute_expires_at BIGINT NOT NULL,
            revoked_at BIGINT, created_at TEXT NOT NULL)""")
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS auth_sessions_expiry ON auth_sessions (idle_expires_at)"
        )
        cursor.execute("""CREATE TABLE IF NOT EXISTS account_access_events (
            id TEXT PRIMARY KEY, user_id TEXT NOT NULL REFERENCES app_users(id),
            actor_user_id TEXT, action TEXT NOT NULL, created_at TEXT NOT NULL)""")


def migrate_postgres_admin_schema(
    connection: psycopg.Connection[dict[str, Any]],
) -> None:
    """Upgrade existing users as active, then default new users to pending."""

    with connection.cursor() as cursor:
        cursor.execute("SELECT to_regclass('app_users')")
        if cursor.fetchone()[0] is None:
            raise AuthError("Authentication schema is missing.")
        cursor.execute("""ALTER TABLE app_users ADD COLUMN IF NOT EXISTS
            access_status TEXT NOT NULL DEFAULT 'active'""")
        cursor.execute("""ALTER TABLE app_users ADD COLUMN IF NOT EXISTS
            is_admin BOOLEAN NOT NULL DEFAULT FALSE""")
        cursor.execute(
            "ALTER TABLE app_users ALTER COLUMN access_status SET DEFAULT 'pending'"
        )
        cursor.execute("""CREATE TABLE IF NOT EXISTS account_access_events (
            id TEXT PRIMARY KEY, user_id TEXT NOT NULL REFERENCES app_users(id),
            actor_user_id TEXT, action TEXT NOT NULL, created_at TEXT NOT NULL)""")
