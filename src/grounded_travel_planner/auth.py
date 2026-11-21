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
from collections.abc import Callable, Iterator, Sequence
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal, Protocol
from urllib.parse import quote, urlencode, urlsplit
from urllib.request import Request, urlopen
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


class Auth0ManagementError(AuthError):
    """Auth0 Management API could not delete the requested users."""


class AccountLinkRequired(AuthError):
    """An existing email account must authorize a new identity explicitly."""


class AccountLinkConflict(AuthError):
    """An identity cannot be linked without changing another account's data."""


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
        connection: str | None = None,
        prompt: str | None = None,
    ) -> str: ...

    def verify_callback(
        self, *, code: str, nonce: str, code_verifier: str, redirect_uri: str
    ) -> VerifiedIdentity: ...

    def logout_url(self, *, return_to: str) -> str: ...

    def request_password_reset(self, *, email: str, connection: str) -> None: ...


class Auth0UserDeleter(Protocol):
    """Server-side boundary for deleting Auth0 user profiles."""

    def delete_users(self, identities: Sequence[tuple[str, str]]) -> None: ...


@dataclass(frozen=True)
class VerifiedIdentity:
    issuer: str
    subject: str
    email: str | None = None
    email_verified: bool = False


def _identity_lock_key(identity: VerifiedIdentity) -> str:
    """Build an unambiguous PostgreSQL text key without forbidden NUL bytes."""

    return f"{len(identity.issuer)}:{identity.issuer}{identity.subject}"


def _identity_method(subject: str) -> str | None:
    if subject.startswith("google-oauth2|"):
        return "google"
    if subject.startswith("auth0|"):
        return "password"
    if subject.startswith("email|"):
        return "email_otp"
    return None


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

    def issue(
        self,
        *,
        return_to: str,
        link_user_id: str | None = None,
        link_auth_hash: str | None = None,
        link_method: Literal["google", "password", "email_otp"] | None = None,
    ) -> tuple[str, dict[str, str]]:
        if any(
            value is not None for value in (link_user_id, link_auth_hash, link_method)
        ) and not all(
            value is not None for value in (link_user_id, link_auth_hash, link_method)
        ):
            raise AuthError("Incomplete account linking state.")
        payload = {
            "state": secrets.token_urlsafe(32),
            "nonce": secrets.token_urlsafe(32),
            "verifier": secrets.token_urlsafe(64),
            "return_to": safe_return_to(return_to),
            "expires_at": _now() + AUTH_PENDING_SECONDS,
        }
        if link_user_id is not None and link_auth_hash is not None and link_method:
            payload["link_user_id"] = link_user_id
            payload["link_auth_hash"] = link_auth_hash
            payload["link_method"] = link_method
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
            link_fields = {"link_user_id", "link_auth_hash", "link_method"}
            if (
                set(raw) not in (required, required | link_fields)
                or int(raw["expires_at"]) < _now()
                or (
                    "link_method" in raw
                    and raw["link_method"] not in {"google", "password", "email_otp"}
                )
            ):
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
        connection: str | None = None,
        prompt: str | None = None,
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
        if connection is not None:
            parameters["connection"] = connection
        if prompt is not None:
            parameters["prompt"] = prompt
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
            email_verified=claims.get("email_verified") is True,
        )

    def logout_url(self, *, return_to: str) -> str:
        """Build Auth0's browser logout URL without exposing any provider token."""

        query = urlencode({"client_id": self._client_id, "returnTo": return_to})
        return f"{self._endpoint}/v2/logout?{query}"

    def request_password_reset(self, *, email: str, connection: str) -> None:
        """Ask Auth0 to email its database-connection password reset form."""

        from urllib.request import Request

        body = json.dumps(
            {"client_id": self._client_id, "email": email, "connection": connection}
        ).encode("utf-8")
        request = Request(
            f"{self._endpoint}/dbconnections/change_password",
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urlopen(request, timeout=10):
                pass
        except Exception as error:
            raise AuthError("Auth0 could not send a password reset email.") from error


class Auth0ManagementApi:
    """Delete Auth0 users with a server-only Management API client credential."""

    def __init__(
        self,
        *,
        issuer: str,
        client_id: str,
        client_secret: str,
        audience: str | None = None,
    ) -> None:
        self._endpoint = Auth0OidcProvider._https_origin(issuer)
        self._issuer = f"{self._endpoint}/"
        management_audience = (audience or f"{self._endpoint}/api/v2/").strip()
        if not management_audience.endswith("/api/v2/"):
            raise AuthError("Auth0 Management API audience must end with /api/v2/.")
        management_origin = management_audience[: -len("/api/v2/")]
        Auth0OidcProvider._https_origin(management_origin)
        self._audience = management_audience
        self._client_id = client_id
        self._client_secret = client_secret

    @classmethod
    def from_environment(cls) -> Auth0ManagementApi:
        return cls(
            issuer=os.getenv("GTP_AUTH0_ISSUER", ""),
            client_id=os.getenv("GTP_AUTH0_M2M_CLIENT_ID", ""),
            client_secret=os.getenv("GTP_AUTH0_M2M_CLIENT_SECRET", ""),
            audience=os.getenv("GTP_AUTH0_MGMT_API_AUDIENCE") or None,
        )

    def delete_users(self, identities: Sequence[tuple[str, str]]) -> None:
        if not self._client_id or not self._client_secret:
            raise Auth0ManagementError(
                "Auth0 Management API credentials are not configured."
            )
        if not identities:
            raise Auth0ManagementError("No Auth0 identities are available to delete.")
        for issuer, subject in identities:
            if issuer.rstrip("/") != self._issuer.rstrip("/") or not subject:
                raise Auth0ManagementError(
                    "The account has an unsupported Auth0 identity."
                )

        token = self._access_token()
        # The stored identity set includes the original account subject plus
        # linked identities. Delete every subject so a secondary lookup cannot
        # prevent the primary Auth0 profile from being reached. Sorting only
        # makes request order stable; it does not identify the primary subject.
        ordered = sorted(
            identities,
            key=lambda identity: (identity[1], identity[0]),
        )
        for _, subject in ordered:
            request = Request(
                f"{self._endpoint}/api/v2/users/{quote(subject, safe='')}",
                headers={"Authorization": f"Bearer {token}"},
                method="DELETE",
            )
            self._request(request, "delete")

    def _access_token(self) -> str:
        if not self._client_id or not self._client_secret:
            raise Auth0ManagementError(
                "Auth0 Management API credentials are not configured."
            )
        body = urlencode(
            {
                "grant_type": "client_credentials",
                "client_id": self._client_id,
                "client_secret": self._client_secret,
                "audience": self._audience,
                "scope": "delete:users",
            }
        ).encode("ascii")
        request = Request(
            f"{self._endpoint}/oauth/token",
            data=body,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            method="POST",
        )
        try:
            with urlopen(request, timeout=10) as response:
                result = json.loads(response.read())
            access_token = result.get("access_token")
            if not isinstance(access_token, str) or not access_token:
                raise Auth0ManagementError(
                    "Auth0 Management API returned an invalid token."
                )
            return access_token
        except Auth0ManagementError:
            raise
        except Exception as error:
            raise self._provider_error(error, "token") from error

    @staticmethod
    def _request(request: Any, operation: str) -> None:
        try:
            with urlopen(request, timeout=10) as response:
                if not 200 <= response.status < 300:
                    raise Auth0ManagementError(
                        f"Auth0 Management API {operation} failed."
                    )
        except Auth0ManagementError:
            raise
        except Exception as error:
            raise Auth0ManagementApi._provider_error(error, operation) from error

    @staticmethod
    def _provider_error(error: Exception, operation: str) -> Auth0ManagementError:
        status = getattr(error, "code", None)
        if isinstance(status, int):
            return Auth0ManagementError(
                f"Auth0 Management API {operation} failed (HTTP {status})."
            )
        return Auth0ManagementError(f"Auth0 Management API {operation} request failed.")


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
                    access_status TEXT NOT NULL DEFAULT 'active',
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
                CREATE TABLE IF NOT EXISTS account_usage_aliases (
                    former_user_id TEXT PRIMARY KEY,
                    canonical_user_id TEXT NOT NULL,
                    CHECK (former_user_id <> canonical_user_id),
                    FOREIGN KEY(canonical_user_id) REFERENCES app_users(id)
                );
                CREATE INDEX IF NOT EXISTS account_usage_aliases_canonical
                    ON account_usage_aliases(canonical_user_id);
                CREATE TABLE IF NOT EXISTS account_merges (
                    secondary_user_id TEXT PRIMARY KEY,
                    canonical_user_id TEXT NOT NULL,
                    actor_user_id TEXT NOT NULL,
                    reason TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(secondary_user_id) REFERENCES app_users(id),
                    FOREIGN KEY(canonical_user_id) REFERENCES app_users(id),
                    CHECK (secondary_user_id <> canonical_user_id)
                );
                CREATE INDEX IF NOT EXISTS account_merges_canonical
                    ON account_merges (canonical_user_id);
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
            connection.execute("""CREATE TABLE IF NOT EXISTS account_usage_aliases (
                former_user_id TEXT PRIMARY KEY, canonical_user_id TEXT NOT NULL,
                CHECK (former_user_id <> canonical_user_id),
                FOREIGN KEY(canonical_user_id) REFERENCES app_users(id))""")
            connection.execute(
                """CREATE INDEX IF NOT EXISTS account_usage_aliases_canonical
                ON account_usage_aliases(canonical_user_id)"""
            )
            connection.execute("""CREATE TABLE IF NOT EXISTS account_merges (
                secondary_user_id TEXT PRIMARY KEY,
                canonical_user_id TEXT NOT NULL,
                actor_user_id TEXT NOT NULL,
                reason TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY(secondary_user_id) REFERENCES app_users(id),
                FOREIGN KEY(canonical_user_id) REFERENCES app_users(id),
                CHECK (secondary_user_id <> canonical_user_id))""")
            connection.execute(
                "CREATE INDEX IF NOT EXISTS account_merges_canonical ON account_merges (canonical_user_id)"
            )

    def migrate_runtime_model_settings(self) -> None:
        """Create durable runtime-model settings and audit tables explicitly."""

        with self._connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            if not connection.execute("PRAGMA table_info(app_users)").fetchall():
                raise AuthError("Authentication schema is missing.")
            connection.execute("""CREATE TABLE IF NOT EXISTS runtime_model_settings (
                settings_key TEXT PRIMARY KEY CHECK (settings_key = 'global'),
                config_json TEXT NOT NULL,
                revision INTEGER NOT NULL DEFAULT 1,
                updated_by TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY(updated_by) REFERENCES app_users(id))""")
            connection.execute(
                """CREATE TABLE IF NOT EXISTS runtime_model_settings_events (
                id TEXT PRIMARY KEY,
                actor_user_id TEXT NOT NULL,
                action TEXT NOT NULL,
                changed_fields_json TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY(actor_user_id) REFERENCES app_users(id))"""
            )

    def get_runtime_model_settings(self) -> tuple[str, int] | None:
        """Read the committed app-wide config; migration errors fail closed."""

        try:
            with self._connection() as connection:
                row = connection.execute(
                    "SELECT config_json, revision FROM runtime_model_settings WHERE settings_key = 'global'"
                ).fetchone()
                return (str(row["config_json"]), int(row["revision"])) if row else None
        except sqlite3.OperationalError as error:
            if "no such table" in str(error).casefold():
                raise AuthError(
                    "Runtime model settings migration is required."
                ) from error
            raise AuthError("Runtime model settings are unavailable.") from error
        except sqlite3.Error as error:
            raise AuthError("Runtime model settings are unavailable.") from error

    def update_runtime_model_settings(
        self, config_json: str, changed_fields_json: str, actor_user_id: str
    ) -> int:
        """Atomically replace settings and record field names, never values."""

        try:
            with self._connection() as connection:
                connection.execute("BEGIN IMMEDIATE")
                row = connection.execute(
                    "SELECT revision FROM runtime_model_settings WHERE settings_key = 'global'"
                ).fetchone()
                revision = int(row["revision"]) + 1 if row else 1
                now = datetime.now(timezone.utc).isoformat()
                connection.execute(
                    """INSERT INTO runtime_model_settings
                    (settings_key, config_json, revision, updated_by, updated_at)
                    VALUES ('global', ?, ?, ?, ?)
                    ON CONFLICT(settings_key) DO UPDATE SET
                    config_json=excluded.config_json, revision=excluded.revision,
                    updated_by=excluded.updated_by, updated_at=excluded.updated_at""",
                    (config_json, revision, actor_user_id, now),
                )
                connection.execute(
                    """INSERT INTO runtime_model_settings_events
                    (id, actor_user_id, action, changed_fields_json, created_at)
                    VALUES (?, ?, 'update', ?, ?)""",
                    (str(uuid4()), actor_user_id, changed_fields_json, now),
                )
                return revision
        except sqlite3.OperationalError as error:
            if "no such table" in str(error).casefold():
                raise AuthError(
                    "Runtime model settings migration is required."
                ) from error
            raise AuthError("Runtime model settings are unavailable.") from error
        except sqlite3.Error as error:
            raise AuthError("Runtime model settings are unavailable.") from error

    def find_or_create_user(self, identity: VerifiedIdentity) -> tuple[str, str | None]:
        if not identity.email_verified:
            raise AuthError("Email is not verified.")
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
                    updated = connection.execute(
                        "UPDATE app_users SET access_status = 'active' WHERE id = ? AND access_status = 'pending'",
                        (row["id"],),
                    )
                    if updated.rowcount:
                        connection.execute(
                            """INSERT INTO account_access_events
                            (id, user_id, actor_user_id, action, created_at)
                            VALUES (?, ?, NULL, 'verified_login', ?)""",
                            (
                                str(uuid4()),
                                row["id"],
                                datetime.now(timezone.utc).isoformat(),
                            ),
                        )
                    return str(row["id"]), row["email"]
                if identity.subject.startswith("google-oauth2|") and not identity.email:
                    raise AccountLinkConflict("Google identity has no email address.")
                if identity.email:
                    match = connection.execute(
                        "SELECT id FROM app_users WHERE lower(email) = lower(?) LIMIT 1",
                        (identity.email,),
                    ).fetchone()
                    if match is not None:
                        raise AccountLinkRequired(
                            "Sign in to your existing account to link this identity."
                        )
                user_id = str(uuid4())
                connection.execute(
                    """INSERT INTO app_users
                    (id, email, created_at, access_status, is_admin)
                    VALUES (?, ?, ?, 'active', 0)""",
                    (user_id, identity.email, datetime.now(timezone.utc).isoformat()),
                )
                connection.execute(
                    "INSERT INTO auth_identities (issuer, subject, user_id) VALUES (?, ?, ?)",
                    (identity.issuer, identity.subject, user_id),
                )
                return user_id, identity.email
        except sqlite3.Error as error:
            raise AuthError("Authentication storage is unavailable.") from error

    def login_methods(self, user_id: str) -> list[str]:
        try:
            with self._connection() as connection:
                subjects = connection.execute(
                    "SELECT subject FROM auth_identities WHERE user_id = ?",
                    (user_id,),
                ).fetchall()
        except sqlite3.Error as error:
            raise AuthError("Authentication storage is unavailable.") from error
        return sorted(
            {method for row in subjects if (method := _identity_method(row["subject"]))}
        )

    def recent_session(self, token: str | None, max_age_seconds: int = 300) -> bool:
        if not token or self.authenticated(token) is None:
            return False
        try:
            with self._connection() as connection:
                row = connection.execute(
                    "SELECT created_at FROM auth_sessions WHERE verifier_hash = ?",
                    (_hash(token),),
                ).fetchone()
            if row is None:
                return False
            created = datetime.fromisoformat(str(row["created_at"]))
            return (
                0
                <= (datetime.now(timezone.utc) - created).total_seconds()
                <= max_age_seconds
            )
        except (sqlite3.Error, ValueError, TypeError) as error:
            if isinstance(error, sqlite3.Error):
                raise AuthError("Authentication storage is unavailable.") from error
            return False

    def link_google_identity(
        self,
        identity: VerifiedIdentity,
        primary_user_id: str,
    ) -> None:
        self._link_identity(identity, primary_user_id, method="google")

    def link_password_identity(
        self,
        identity: VerifiedIdentity,
        primary_user_id: str,
    ) -> None:
        self._link_identity(identity, primary_user_id, method="password")

    def link_email_otp_identity(
        self,
        identity: VerifiedIdentity,
        primary_user_id: str,
    ) -> None:
        self._link_identity(identity, primary_user_id, method="email_otp")

    def _link_identity(
        self,
        identity: VerifiedIdentity,
        primary_user_id: str,
        *,
        method: Literal["google", "password", "email_otp"],
    ) -> None:
        if not identity.email_verified or _identity_method(identity.subject) != method:
            raise AccountLinkConflict(
                "A verified identity of the requested type is required."
            )
        try:
            with self._connection() as connection:
                connection.execute("BEGIN IMMEDIATE")
                primary = connection.execute(
                    "SELECT email, access_status FROM app_users WHERE id = ?",
                    (primary_user_id,),
                ).fetchone()
                if (
                    primary is None
                    or primary["access_status"] != "active"
                    or not primary["email"]
                    or not identity.email
                    or str(primary["email"]).casefold() != identity.email.casefold()
                ):
                    raise AccountLinkConflict(
                        "Primary account and identity email do not match."
                    )
                issuer = connection.execute(
                    "SELECT 1 FROM auth_identities WHERE user_id = ? AND issuer = ? LIMIT 1",
                    (primary_user_id, identity.issuer),
                ).fetchone()
                if issuer is None:
                    raise AccountLinkConflict(
                        "The new identity and primary account use different issuers."
                    )
                current = connection.execute(
                    "SELECT user_id FROM auth_identities WHERE issuer = ? AND subject = ?",
                    (identity.issuer, identity.subject),
                ).fetchone()
                if current is not None and current["user_id"] == primary_user_id:
                    return
                if current is not None:
                    raise AccountLinkConflict(
                        "The identity belongs to another account."
                    )
                connection.execute(
                    "INSERT INTO auth_identities (issuer, subject, user_id) VALUES (?, ?, ?)",
                    (identity.issuer, identity.subject, primary_user_id),
                )
                connection.execute(
                    """INSERT INTO account_access_events
                    (id, user_id, actor_user_id, action, created_at)
                    VALUES (?, ?, ?, ?, ?)""",
                    (
                        str(uuid4()),
                        primary_user_id,
                        primary_user_id,
                        f"link_{method}_identity",
                        datetime.now(timezone.utc).isoformat(),
                    ),
                )
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
                if row is None or row["access_status"] != "active":
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
                    or row["access_status"] != "active"
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
                    or row["access_status"] != "active"
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
                    FROM app_users WHERE access_status NOT IN ('merged', 'deleted')
                    ORDER BY created_at DESC, id DESC LIMIT ? OFFSET ?""",
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

    def begin_account_deletion(
        self,
        user_id: str,
        actor_user_id: str,
        delete_auth0_users: Callable[[Sequence[tuple[str, str]]], None],
    ) -> AccountRecord:
        """Delete Auth0 identities, then hide and revoke a retryable account."""

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
                if target["access_status"] == "merged":
                    raise AccessChangeConflict("Merged accounts cannot be deleted.")
                if user_id == actor_user_id:
                    raise AccessChangeConflict(
                        "Administrators cannot delete themselves."
                    )
                if target["access_status"] == "deleted":
                    return _account_record(target)
                if target["is_admin"] and target["access_status"] == "active":
                    count = connection.execute("""SELECT COUNT(*) FROM app_users
                        WHERE is_admin = 1 AND access_status = 'active'""").fetchone()[
                        0
                    ]
                    if count <= 1:
                        raise AccessChangeConflict(
                            "The last active administrator cannot be deleted."
                        )
                identity_rows = connection.execute(
                    """SELECT issuer, subject FROM auth_identities
                    WHERE user_id = ?
                    ORDER BY CASE WHEN subject LIKE 'google-oauth2|%' THEN 1 ELSE 0 END,
                        subject""",
                    (user_id,),
                ).fetchall()
                identities = tuple(
                    (str(row["issuer"]), str(row["subject"])) for row in identity_rows
                )
                if not identities:
                    raise AuthError("The account has no stored Auth0 identities.")

                # Keep the original identity and all linked subjects until Auth0
                # confirms every DELETE. The callback is idempotent for retries.
                delete_auth0_users(identities)
                next_status = "deleting"
                if target["access_status"] != next_status:
                    connection.execute(
                        "UPDATE app_users SET access_status = ? WHERE id = ?",
                        (next_status, user_id),
                    )
                    action = "deletion_started"
                else:
                    action = "deletion_retried"
                connection.execute(
                    "DELETE FROM auth_sessions WHERE user_id = ?", (user_id,)
                )
                connection.execute(
                    """INSERT INTO account_access_events
                    (id, user_id, actor_user_id, action, created_at)
                    VALUES (?, ?, ?, ?, ?)""",
                    (
                        str(uuid4()),
                        user_id,
                        actor_user_id,
                        action,
                        datetime.now(timezone.utc).isoformat(),
                    ),
                )
                return AccountRecord(
                    user_id,
                    target["email"],
                    str(target["created_at"]),
                    next_status,
                    bool(target["is_admin"]),
                )
        except sqlite3.Error as error:
            raise AuthError("Authentication storage is unavailable.") from error

    def complete_account_deletion(
        self, user_id: str, actor_user_id: str
    ) -> AccountRecord:
        """Scrub account data after its Auth0 users and saved tours are gone."""

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
                if target["access_status"] == "merged":
                    raise AccessChangeConflict("Merged accounts cannot be deleted.")
                if target["access_status"] == "deleted":
                    return _account_record(target)
                if target["access_status"] != "deleting":
                    raise AccessChangeConflict(
                        "Auth0 deletion has not completed for this account."
                    )
                connection.execute(
                    "DELETE FROM auth_sessions WHERE user_id = ?", (user_id,)
                )
                connection.execute(
                    "DELETE FROM auth_identities WHERE user_id = ?", (user_id,)
                )
                connection.execute(
                    """DELETE FROM account_usage_aliases
                    WHERE canonical_user_id = ? OR former_user_id = ?""",
                    (user_id, user_id),
                )
                connection.execute(
                    """UPDATE app_users SET email = NULL, access_status = 'deleted',
                    is_admin = 0 WHERE id = ?""",
                    (user_id,),
                )
                connection.execute(
                    """INSERT INTO account_access_events
                    (id, user_id, actor_user_id, action, created_at)
                    VALUES (?, ?, ?, 'deleted', ?)""",
                    (
                        str(uuid4()),
                        user_id,
                        actor_user_id,
                        datetime.now(timezone.utc).isoformat(),
                    ),
                )
                return AccountRecord(
                    user_id,
                    None,
                    str(target["created_at"]),
                    "deleted",
                    False,
                )
        except sqlite3.Error as error:
            raise AuthError("Authentication storage is unavailable.") from error

    def usage_aliases_for_users(self, user_ids: list[str]) -> dict[str, list[str]]:
        canonical_ids = list(dict.fromkeys(user_ids))
        if not canonical_ids:
            return {}
        placeholders = ",".join("?" for _ in canonical_ids)
        try:
            with self._connection() as connection:
                usage_rows = connection.execute(
                    f"""SELECT canonical_user_id, secondary_user_id
                    FROM account_merges
                    WHERE canonical_user_id IN ({placeholders})
                    ORDER BY canonical_user_id, secondary_user_id""",
                    canonical_ids,
                ).fetchall()
                alias_rows = connection.execute(
                    f"""SELECT canonical_user_id, former_user_id
                    FROM account_usage_aliases
                    WHERE canonical_user_id IN ({placeholders})
                    ORDER BY canonical_user_id, former_user_id""",
                    canonical_ids,
                ).fetchall()
        except sqlite3.Error as error:
            raise AuthError("Authentication storage is unavailable.") from error
        aliases: dict[str, set[str]] = {}
        for row in usage_rows:
            aliases.setdefault(str(row["canonical_user_id"]), set()).add(
                str(row["secondary_user_id"])
            )
        for row in alias_rows:
            aliases.setdefault(str(row["canonical_user_id"]), set()).add(
                str(row["former_user_id"])
            )
        return {canonical_id: sorted(ids) for canonical_id, ids in aliases.items()}

    def usage_aliases(self, user_ids: list[str]) -> dict[str, list[str]]:
        """Compatibility name for merged account usage aliases."""

        return self.usage_aliases_for_users(user_ids)

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
                if target["access_status"] in {"merged", "deleting", "deleted"}:
                    raise AccessChangeConflict(
                        "Merged or deleting accounts cannot change access."
                    )
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
                if target["access_status"] in {"merged", "deleting", "deleted"}:
                    raise AccessChangeConflict(
                        "Merged or deleting accounts cannot be activated."
                    )
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
        if not identity.email_verified:
            raise AuthError("Email is not verified.")
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
                    cursor.execute(
                        "UPDATE app_users SET access_status = 'active' WHERE id = %s AND access_status = 'pending'",
                        (row["id"],),
                    )
                    if cursor.rowcount:
                        cursor.execute(
                            """INSERT INTO account_access_events
                            (id, user_id, actor_user_id, action, created_at)
                            VALUES (%s, %s, NULL, 'verified_login', %s)""",
                            (
                                str(uuid4()),
                                row["id"],
                                datetime.now(timezone.utc).isoformat(),
                            ),
                        )
                    return str(row["id"]), row["email"]
                if identity.subject.startswith("google-oauth2|") and not identity.email:
                    raise AccountLinkConflict("Google identity has no email address.")
                if identity.email:
                    cursor.execute(
                        "SELECT pg_advisory_xact_lock(hashtextextended(%s, 0))",
                        (f"app_user_email:{identity.email.casefold()}",),
                    )
                if identity.email:
                    cursor.execute(
                        "SELECT id FROM app_users WHERE lower(email) = lower(%s) LIMIT 1",
                        (identity.email,),
                    )
                    if cursor.fetchone() is not None:
                        raise AccountLinkRequired(
                            "Sign in to your existing account to link this identity."
                        )
                user_id = str(uuid4())
                cursor.execute(
                    """INSERT INTO app_users
                    (id, email, created_at, access_status, is_admin)
                    VALUES (%s, %s, %s, 'active', FALSE)""",
                    (user_id, identity.email, datetime.now(timezone.utc).isoformat()),
                )
                cursor.execute(
                    "INSERT INTO auth_identities (issuer, subject, user_id) VALUES (%s, %s, %s)",
                    (identity.issuer, identity.subject, user_id),
                )
                return user_id, identity.email
        except (psycopg.Error, PoolClosed, PoolTimeout) as error:
            raise AuthError("Authentication storage is unavailable.") from error

    def login_methods(self, user_id: str) -> list[str]:
        try:
            with self._pool.connection() as connection, connection.cursor() as cursor:
                cursor.execute(
                    "SELECT subject FROM auth_identities WHERE user_id = %s",
                    (user_id,),
                )
                subjects = cursor.fetchall()
        except (psycopg.Error, PoolClosed, PoolTimeout) as error:
            raise AuthError("Authentication storage is unavailable.") from error
        return sorted(
            {method for row in subjects if (method := _identity_method(row["subject"]))}
        )

    def usage_aliases(self, user_ids: list[str]) -> dict[str, list[str]]:
        """Compatibility name for merged account usage aliases."""

        return self.usage_aliases_for_users(user_ids)

    def recent_session(self, token: str | None, max_age_seconds: int = 300) -> bool:
        if not token or self.authenticated(token) is None:
            return False
        try:
            with self._pool.connection() as connection, connection.cursor() as cursor:
                cursor.execute(
                    "SELECT created_at FROM auth_sessions WHERE verifier_hash = %s",
                    (_hash(token),),
                )
                row = cursor.fetchone()
            if row is None:
                return False
            created = datetime.fromisoformat(str(row["created_at"]))
            return (
                0
                <= (datetime.now(timezone.utc) - created).total_seconds()
                <= max_age_seconds
            )
        except (psycopg.Error, PoolClosed, PoolTimeout) as error:
            raise AuthError("Authentication storage is unavailable.") from error
        except (ValueError, TypeError):
            return False

    def link_google_identity(
        self,
        identity: VerifiedIdentity,
        primary_user_id: str,
    ) -> None:
        self._link_identity(identity, primary_user_id, method="google")

    def link_password_identity(
        self,
        identity: VerifiedIdentity,
        primary_user_id: str,
    ) -> None:
        self._link_identity(identity, primary_user_id, method="password")

    def link_email_otp_identity(
        self,
        identity: VerifiedIdentity,
        primary_user_id: str,
    ) -> None:
        self._link_identity(identity, primary_user_id, method="email_otp")

    def _link_identity(
        self,
        identity: VerifiedIdentity,
        primary_user_id: str,
        *,
        method: Literal["google", "password", "email_otp"],
    ) -> None:
        if not identity.email_verified or _identity_method(identity.subject) != method:
            raise AccountLinkConflict(
                "A verified identity of the requested type is required."
            )
        try:
            with self._pool.connection() as connection, connection.cursor() as cursor:
                cursor.execute(
                    "SELECT pg_advisory_xact_lock(hashtextextended(%s, 0))",
                    (_identity_lock_key(identity),),
                )
                cursor.execute(
                    "SELECT email, access_status FROM app_users WHERE id = %s FOR UPDATE",
                    (primary_user_id,),
                )
                primary = cursor.fetchone()
                if (
                    primary is None
                    or primary["access_status"] != "active"
                    or not primary["email"]
                    or not identity.email
                    or str(primary["email"]).casefold() != identity.email.casefold()
                ):
                    raise AccountLinkConflict(
                        "Primary account and identity email do not match."
                    )
                cursor.execute(
                    "SELECT 1 FROM auth_identities WHERE user_id = %s AND issuer = %s LIMIT 1",
                    (primary_user_id, identity.issuer),
                )
                if cursor.fetchone() is None:
                    raise AccountLinkConflict(
                        "The new identity and primary account use different issuers."
                    )
                cursor.execute(
                    "SELECT user_id FROM auth_identities WHERE issuer = %s AND subject = %s FOR UPDATE",
                    (identity.issuer, identity.subject),
                )
                current = cursor.fetchone()
                if current is not None and current["user_id"] == primary_user_id:
                    return
                if current is not None:
                    raise AccountLinkConflict(
                        "The identity belongs to another account."
                    )
                cursor.execute(
                    "INSERT INTO auth_identities (issuer, subject, user_id) VALUES (%s, %s, %s)",
                    (identity.issuer, identity.subject, primary_user_id),
                )
                cursor.execute(
                    """INSERT INTO account_access_events
                    (id, user_id, actor_user_id, action, created_at)
                    VALUES (%s, %s, %s, %s, %s)""",
                    (
                        str(uuid4()),
                        primary_user_id,
                        primary_user_id,
                        f"link_{method}_identity",
                        datetime.now(timezone.utc).isoformat(),
                    ),
                )
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
                if row is None or row["access_status"] != "active":
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
                    or row["access_status"] != "active"
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
                    FROM app_users WHERE access_status NOT IN ('merged', 'deleted')
                    ORDER BY created_at DESC, id DESC LIMIT %s OFFSET %s""",
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

    def begin_account_deletion(
        self,
        user_id: str,
        actor_user_id: str,
        delete_auth0_users: Callable[[Sequence[tuple[str, str]]], None],
    ) -> AccountRecord:
        """Delete Auth0 identities, then hide and revoke a retryable account."""

        try:
            with self._pool.connection() as connection, connection.cursor() as cursor:
                cursor.execute(
                    "SELECT pg_advisory_xact_lock(hashtextextended('app_user_admin_access', 0))"
                )
                cursor.execute(
                    "SELECT is_admin, access_status FROM app_users WHERE id = %s FOR UPDATE",
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
                if target["access_status"] == "merged":
                    raise AccessChangeConflict("Merged accounts cannot be deleted.")
                if user_id == actor_user_id:
                    raise AccessChangeConflict(
                        "Administrators cannot delete themselves."
                    )
                if target["access_status"] == "deleted":
                    return _account_record(target)
                if target["is_admin"] and target["access_status"] == "active":
                    cursor.execute("""SELECT COUNT(*) FROM app_users
                        WHERE is_admin = TRUE AND access_status = 'active'""")
                    if cursor.fetchone()["count"] <= 1:
                        raise AccessChangeConflict(
                            "The last active administrator cannot be deleted."
                        )
                cursor.execute(
                    """SELECT issuer, subject FROM auth_identities
                    WHERE user_id = %s ORDER BY subject, issuer FOR UPDATE""",
                    (user_id,),
                )
                identities = tuple(
                    (str(row["issuer"]), str(row["subject"]))
                    for row in cursor.fetchall()
                )
                if not identities:
                    raise AuthError("The account has no stored Auth0 identities.")

                # Keep the original subject and all linked identities until
                # Auth0 confirms every DELETE. Repeating the callback is safe.
                delete_auth0_users(identities)
                next_status = "deleting"
                if target["access_status"] != next_status:
                    cursor.execute(
                        "UPDATE app_users SET access_status = %s WHERE id = %s",
                        (next_status, user_id),
                    )
                    action = "deletion_started"
                else:
                    action = "deletion_retried"
                cursor.execute(
                    "DELETE FROM auth_sessions WHERE user_id = %s", (user_id,)
                )
                cursor.execute(
                    """INSERT INTO account_access_events
                    (id, user_id, actor_user_id, action, created_at)
                    VALUES (%s, %s, %s, %s, %s)""",
                    (
                        str(uuid4()),
                        user_id,
                        actor_user_id,
                        action,
                        datetime.now(timezone.utc).isoformat(),
                    ),
                )
                return AccountRecord(
                    user_id,
                    target["email"],
                    str(target["created_at"]),
                    next_status,
                    bool(target["is_admin"]),
                )
        except (psycopg.Error, PoolClosed, PoolTimeout) as error:
            raise AuthError("Authentication storage is unavailable.") from error

    def complete_account_deletion(
        self, user_id: str, actor_user_id: str
    ) -> AccountRecord:
        """Scrub account data after its Auth0 users and saved tours are gone."""

        try:
            with self._pool.connection() as connection, connection.cursor() as cursor:
                cursor.execute(
                    "SELECT pg_advisory_xact_lock(hashtextextended('app_user_admin_access', 0))"
                )
                cursor.execute(
                    "SELECT is_admin, access_status FROM app_users WHERE id = %s FOR UPDATE",
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
                if target["access_status"] == "merged":
                    raise AccessChangeConflict("Merged accounts cannot be deleted.")
                if target["access_status"] == "deleted":
                    return _account_record(target)
                if target["access_status"] != "deleting":
                    raise AccessChangeConflict(
                        "Auth0 deletion has not completed for this account."
                    )
                cursor.execute(
                    "DELETE FROM auth_sessions WHERE user_id = %s", (user_id,)
                )
                cursor.execute(
                    "DELETE FROM auth_identities WHERE user_id = %s", (user_id,)
                )
                cursor.execute(
                    """DELETE FROM account_usage_aliases
                    WHERE canonical_user_id = %s OR former_user_id = %s""",
                    (user_id, user_id),
                )
                cursor.execute(
                    """UPDATE app_users SET email = NULL, access_status = 'deleted',
                    is_admin = FALSE WHERE id = %s""",
                    (user_id,),
                )
                cursor.execute(
                    """INSERT INTO account_access_events
                    (id, user_id, actor_user_id, action, created_at)
                    VALUES (%s, %s, %s, 'deleted', %s)""",
                    (
                        str(uuid4()),
                        user_id,
                        actor_user_id,
                        datetime.now(timezone.utc).isoformat(),
                    ),
                )
                return AccountRecord(
                    user_id,
                    None,
                    str(target["created_at"]),
                    "deleted",
                    False,
                )
        except (psycopg.Error, PoolClosed, PoolTimeout) as error:
            raise AuthError("Authentication storage is unavailable.") from error

    def usage_aliases_for_users(self, user_ids: list[str]) -> dict[str, list[str]]:
        canonical_ids = list(dict.fromkeys(user_ids))
        if not canonical_ids:
            return {}
        try:
            with self._pool.connection() as connection, connection.cursor() as cursor:
                cursor.execute(
                    """SELECT canonical_user_id, alias_user_id FROM (
                        SELECT canonical_user_id, former_user_id AS alias_user_id
                        FROM account_usage_aliases
                        WHERE canonical_user_id = ANY(%s)
                        UNION
                        SELECT canonical_user_id, secondary_user_id AS alias_user_id
                        FROM account_merges
                        WHERE canonical_user_id = ANY(%s)
                    ) AS aliases
                    ORDER BY canonical_user_id, alias_user_id""",
                    (canonical_ids, canonical_ids),
                )
                rows = cursor.fetchall()
        except (psycopg.Error, PoolClosed, PoolTimeout) as error:
            raise AuthError("Authentication storage is unavailable.") from error
        aliases: dict[str, list[str]] = {}
        for row in rows:
            aliases.setdefault(str(row["canonical_user_id"]), []).append(
                str(row["alias_user_id"])
            )
        return aliases

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
                if target["access_status"] in {"merged", "deleting", "deleted"}:
                    raise AccessChangeConflict(
                        "Merged or deleting accounts cannot change access."
                    )
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
                    """SELECT id, email, created_at, access_status FROM app_users
                    WHERE id = %s FOR UPDATE""",
                    (user_id,),
                )
                target = cursor.fetchone()
                if target is None:
                    raise AccountNotFound("Account does not exist.")
                if target["access_status"] in {"merged", "deleting", "deleted"}:
                    raise AccessChangeConflict(
                        "Merged or deleting accounts cannot be activated."
                    )
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

    def get_runtime_model_settings(self) -> tuple[str, int] | None:
        """Read app-wide model settings from PostgreSQL."""

        try:
            with self._pool.connection() as connection, connection.cursor() as cursor:
                cursor.execute(
                    "SELECT config_json::text AS config_json, revision FROM runtime_model_settings WHERE settings_key = 'global'"
                )
                row = cursor.fetchone()
                return (str(row["config_json"]), int(row["revision"])) if row else None
        except psycopg.errors.UndefinedTable as error:
            raise AuthError("Runtime model settings migration is required.") from error
        except (psycopg.Error, PoolClosed, PoolTimeout) as error:
            raise AuthError("Runtime model settings are unavailable.") from error

    def update_runtime_model_settings(
        self, config_json: str, changed_fields_json: str, actor_user_id: str
    ) -> int:
        """Atomically replace settings and store field names, never values."""

        try:
            with self._pool.connection() as connection, connection.cursor() as cursor:
                now = datetime.now(timezone.utc).isoformat()
                cursor.execute(
                    """INSERT INTO runtime_model_settings
                    (settings_key, config_json, revision, updated_by, updated_at)
                    VALUES ('global', %s::jsonb, 1, %s, %s)
                    ON CONFLICT(settings_key) DO UPDATE SET
                    config_json=EXCLUDED.config_json,
                    revision=runtime_model_settings.revision + 1,
                    updated_by=EXCLUDED.updated_by, updated_at=EXCLUDED.updated_at
                    RETURNING revision""",
                    (config_json, actor_user_id, now),
                )
                revision = int(cursor.fetchone()["revision"])
                cursor.execute(
                    """INSERT INTO runtime_model_settings_events
                    (id, actor_user_id, action, changed_fields_json, created_at)
                    VALUES (%s, %s, 'update', %s::jsonb, %s)""",
                    (str(uuid4()), actor_user_id, changed_fields_json, now),
                )
                return revision
        except psycopg.errors.UndefinedTable as error:
            raise AuthError("Runtime model settings migration is required.") from error
        except (psycopg.Error, PoolClosed, PoolTimeout) as error:
            raise AuthError("Runtime model settings are unavailable.") from error


def create_postgres_auth_schema(
    connection: psycopg.Connection[dict[str, Any]],
) -> None:
    """Explicit maintenance migration for auth, session, and merge tables."""

    with connection.cursor() as cursor:
        cursor.execute("""CREATE TABLE IF NOT EXISTS app_users (
            id TEXT PRIMARY KEY, email TEXT, created_at TEXT NOT NULL,
            access_status TEXT NOT NULL DEFAULT 'active',
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
        cursor.execute("""CREATE TABLE IF NOT EXISTS account_usage_aliases (
            former_user_id TEXT PRIMARY KEY,
            canonical_user_id TEXT NOT NULL REFERENCES app_users(id),
            CHECK (former_user_id <> canonical_user_id))""")
        cursor.execute("""CREATE INDEX IF NOT EXISTS account_usage_aliases_canonical
            ON account_usage_aliases(canonical_user_id)""")
        cursor.execute("""CREATE TABLE IF NOT EXISTS account_merges (
            secondary_user_id TEXT PRIMARY KEY REFERENCES app_users(id),
            canonical_user_id TEXT NOT NULL REFERENCES app_users(id),
            actor_user_id TEXT NOT NULL,
            reason TEXT NOT NULL,
            created_at TEXT NOT NULL,
            CHECK (secondary_user_id <> canonical_user_id))""")
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS account_merges_canonical ON account_merges (canonical_user_id)"
        )


def migrate_postgres_admin_schema(
    connection: psycopg.Connection[dict[str, Any]],
) -> None:
    """Upgrade existing users and default new users to active."""

    with connection.cursor() as cursor:
        cursor.execute("SELECT to_regclass('app_users')")
        if cursor.fetchone()[0] is None:
            raise AuthError("Authentication schema is missing.")
        cursor.execute("""ALTER TABLE app_users ADD COLUMN IF NOT EXISTS
            access_status TEXT NOT NULL DEFAULT 'active'""")
        cursor.execute("""ALTER TABLE app_users ADD COLUMN IF NOT EXISTS
            is_admin BOOLEAN NOT NULL DEFAULT FALSE""")
        cursor.execute(
            "ALTER TABLE app_users ALTER COLUMN access_status SET DEFAULT 'active'"
        )
        cursor.execute("""CREATE TABLE IF NOT EXISTS account_access_events (
            id TEXT PRIMARY KEY, user_id TEXT NOT NULL REFERENCES app_users(id),
            actor_user_id TEXT, action TEXT NOT NULL, created_at TEXT NOT NULL)""")
        cursor.execute("""CREATE TABLE IF NOT EXISTS account_usage_aliases (
            former_user_id TEXT PRIMARY KEY,
            canonical_user_id TEXT NOT NULL REFERENCES app_users(id),
            CHECK (former_user_id <> canonical_user_id))""")
        cursor.execute("""CREATE INDEX IF NOT EXISTS account_usage_aliases_canonical
            ON account_usage_aliases(canonical_user_id)""")
        cursor.execute("""CREATE TABLE IF NOT EXISTS account_merges (
            secondary_user_id TEXT PRIMARY KEY REFERENCES app_users(id),
            canonical_user_id TEXT NOT NULL REFERENCES app_users(id),
            actor_user_id TEXT NOT NULL,
            reason TEXT NOT NULL,
            created_at TEXT NOT NULL,
            CHECK (secondary_user_id <> canonical_user_id))""")
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS account_merges_canonical ON account_merges (canonical_user_id)"
        )


def migrate_postgres_runtime_model_settings_schema(
    connection: psycopg.Connection[dict[str, Any]],
) -> None:
    """Create app-wide runtime settings and audit tables in maintenance mode."""

    with connection.cursor() as cursor:
        cursor.execute("SELECT to_regclass('app_users')")
        if cursor.fetchone()[0] is None:
            raise AuthError("Authentication schema is missing.")
        cursor.execute("""CREATE TABLE IF NOT EXISTS runtime_model_settings (
            settings_key TEXT PRIMARY KEY CHECK (settings_key = 'global'),
            config_json JSONB NOT NULL,
            revision BIGINT NOT NULL DEFAULT 1,
            updated_by TEXT NOT NULL REFERENCES app_users(id),
            updated_at TEXT NOT NULL)""")
        cursor.execute("""CREATE TABLE IF NOT EXISTS runtime_model_settings_events (
            id TEXT PRIMARY KEY,
            actor_user_id TEXT NOT NULL REFERENCES app_users(id),
            action TEXT NOT NULL,
            changed_fields_json JSONB NOT NULL,
            created_at TEXT NOT NULL)""")
