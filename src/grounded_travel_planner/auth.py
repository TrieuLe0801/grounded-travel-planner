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
from typing import Any, Protocol
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


class OidcProvider(Protocol):
    """Small boundary for the external identity provider."""

    def authorization_url(
        self, *, state: str, nonce: str, code_verifier: str, redirect_uri: str
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
        self, *, state: str, nonce: str, code_verifier: str, redirect_uri: str
    ) -> str:
        query = urlencode(
            {
                "response_type": "code",
                "client_id": self._client_id,
                "redirect_uri": redirect_uri,
                "scope": "openid profile email",
                "state": state,
                "nonce": nonce,
                "code_challenge": code_challenge(code_verifier),
                "code_challenge_method": "S256",
                "connection": "email",
            }
        )
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
                    id TEXT PRIMARY KEY, email TEXT, created_at TEXT NOT NULL
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
                """)

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
                    "INSERT INTO app_users (id, email, created_at) VALUES (?, ?, ?)",
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
                    """SELECT auth_sessions.user_id, app_users.email, auth_sessions.csrf_hash,
                    auth_sessions.idle_expires_at, auth_sessions.absolute_expires_at,
                    auth_sessions.revoked_at FROM auth_sessions JOIN app_users
                    ON app_users.id = auth_sessions.user_id WHERE verifier_hash = ?""",
                    (_hash(token),),
                ).fetchone()
                if (
                    row is None
                    or row["revoked_at"] is not None
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
                    str(row["user_id"]), row["email"], _csrf_for(token)
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
                    """SELECT auth_sessions.user_id, app_users.email, csrf_hash, idle_expires_at,
                    absolute_expires_at, revoked_at FROM auth_sessions JOIN app_users
                    ON app_users.id = auth_sessions.user_id WHERE verifier_hash = ?""",
                    (_hash(token),),
                ).fetchone()
                if (
                    row is None
                    or row["revoked_at"] is not None
                    or now > min(row["idle_expires_at"], row["absolute_expires_at"])
                ):
                    return None
                if not hmac.compare_digest(str(row["csrf_hash"]), _hash(csrf)):
                    return None
                return AuthenticatedUser(str(row["user_id"]), row["email"], csrf)
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
                    "INSERT INTO app_users (id, email, created_at) VALUES (%s, %s, %s)",
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
                    """SELECT auth_sessions.user_id, app_users.email, auth_sessions.csrf_hash,
                    auth_sessions.idle_expires_at, auth_sessions.absolute_expires_at, auth_sessions.revoked_at
                    FROM auth_sessions JOIN app_users ON app_users.id = auth_sessions.user_id
                    WHERE verifier_hash = %s""",
                    (_hash(token),),
                )
                row = cursor.fetchone()
                if (
                    row is None
                    or row["revoked_at"] is not None
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
                    str(row["user_id"]), row["email"], _csrf_for(token)
                )
        except (psycopg.Error, PoolClosed, PoolTimeout) as error:
            raise AuthError("Authentication storage is unavailable.") from error

    def authenticated(self, token: str | None) -> AuthenticatedUser | None:
        return self._record(token, rotate=True)

    def verify_csrf(
        self, token: str | None, csrf: str | None
    ) -> AuthenticatedUser | None:
        return self._record(token, csrf)

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
            id TEXT PRIMARY KEY, email TEXT, created_at TEXT NOT NULL)""")
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
