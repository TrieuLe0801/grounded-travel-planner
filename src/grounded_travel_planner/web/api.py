"""Thin HTTP adapter that keeps itinerary state in one browser session only."""

from __future__ import annotations

import hmac
import json
import os
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from threading import Lock
from time import monotonic
from typing import Literal, Protocol
from urllib.parse import urlsplit
from uuid import uuid4

from fastapi import Cookie, FastAPI, Header, HTTPException, Query, Request, Response
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from grounded_travel_planner.auth import (
    AUTH_ABSOLUTE_SECONDS,
    AUTH_COOKIE_NAME,
    AUTH_PENDING_COOKIE_NAME,
    Auth0OidcProvider,
    AuthenticatedUser,
    AuthError,
    AuthRepository,
    OidcProvider,
    PendingLoginCodec,
    PostgresAuthRepository,
    safe_return_to,
)
from grounded_travel_planner.contracts import (
    AgentResponse,
    ConversationTurn,
    SightseeingPlan,
    TripRequest,
)
from grounded_travel_planner.conversation import (
    MAX_CONVERSATION_TURNS,
    MAX_SESSION_SUMMARY,
)
from grounded_travel_planner.i18n import Language, localized, localized_issue_message
from grounded_travel_planner.saved_tours import (
    LIST_LIMIT,
    InvalidSavedTourCursor,
    SavedTour,
    SavedTourError,
    SavedTourPage,
    SavedTourRepository,
)
from grounded_travel_planner.service import TravelPlannerService
from grounded_travel_planner.ui.graph_diagram import compiled_graph_svg
from grounded_travel_planner.ui.turn_runner import (
    PendingTurn,
    TurnCapacityExceeded,
    TurnRunner,
)
from grounded_travel_planner.visuals import VisualEnrichmentService
from grounded_travel_planner.web.turn_rate_limit import (
    TurnQuotaReservation,
    TurnRateLimiter,
    TurnRateLimitExceeded,
)

COOKIE_NAME = "gtp_session"
SAVED_TOURS_OWNER_COOKIE_NAME = "gtp_saved_tours_owner"
SAVED_TOURS_OWNER_MAX_AGE = 365 * 24 * 60 * 60
AUTH_DATABASE_PATH = Path(
    os.getenv("GTP_AUTH_DB_PATH", Path.cwd() / ".local" / "auth.sqlite")
)
DEFAULT_SAVED_TOURS_DATABASE_PATH = Path(
    os.getenv("GTP_SAVED_TOURS_DB_PATH", Path.cwd() / ".local" / "saved_tours.sqlite")
)
DEFAULT_MAX_SESSIONS = 1024
DEFAULT_SESSION_IDLE_SECONDS = 60 * 60
FRONTEND_DIST = Path(
    os.getenv("GTP_FRONTEND_DIST", Path.cwd() / "frontend" / "dist")
).resolve()


class TurnInput(BaseModel):
    """HTTP payload for either a new itinerary or a chat turn."""

    message: str = Field(min_length=1, max_length=4000)
    request: TripRequest | None = None


class LanguageInput(BaseModel):
    language: Literal["vi", "en"]


@dataclass
class WebSession:
    """Volatile state keyed only by an opaque HttpOnly browser cookie."""

    thread_id: str
    owner_user_id: str | None = None
    language: Language = "vi"
    current_plan: SightseeingPlan | None = None
    pending: PendingTurn | None = None
    response: AgentResponse | None = None
    conversation: list[ConversationTurn] = field(default_factory=list)
    session_summary: str = ""
    last_accessed: float = 0.0
    lock: Lock = field(default_factory=Lock)


class SessionCapacityExceeded(RuntimeError):
    """Raised when volatile session capacity is exhausted."""


class SessionStore:
    """Small in-memory store; replacing the process intentionally clears it."""

    def __init__(
        self,
        *,
        max_sessions: int = DEFAULT_MAX_SESSIONS,
        idle_seconds: float = DEFAULT_SESSION_IDLE_SECONDS,
        clock: Callable[[], float] = monotonic,
    ) -> None:
        if max_sessions < 1:
            raise ValueError("max_sessions must be positive")
        if idle_seconds <= 0:
            raise ValueError("idle_seconds must be positive")
        self._max_sessions = max_sessions
        self._idle_seconds = idle_seconds
        self._clock = clock
        self._sessions: dict[str, WebSession] = {}
        self._lock = Lock()

    def create(
        self, service: TravelPlannerService, owner_user_id: str | None = None
    ) -> tuple[str, WebSession]:
        with self._lock:
            now = self._clock()
            self._evict_idle(now)
            if len(self._sessions) >= self._max_sessions:
                raise SessionCapacityExceeded("The session capacity is exhausted.")
            session_id = uuid4().hex
            session = WebSession(
                thread_id=service.create_session(),
                owner_user_id=owner_user_id,
                last_accessed=now,
            )
            self._sessions[session_id] = session
        return session_id, session

    def replace(
        self,
        session_id: str | None,
        service: TravelPlannerService,
        owner_user_id: str | None = None,
    ) -> tuple[str, WebSession]:
        """Create a reset session while removing its predecessor atomically."""

        with self._lock:
            now = self._clock()
            self._evict_idle(now)
            previous = self._sessions.get(session_id) if session_id else None
            if previous is None and len(self._sessions) >= self._max_sessions:
                raise SessionCapacityExceeded("The session capacity is exhausted.")
            language: Language = "vi"
            if previous is not None:
                with previous.lock:
                    language = previous.language
            replacement = WebSession(
                thread_id=service.create_session(),
                owner_user_id=owner_user_id,
                language=language,
                last_accessed=now,
            )
            replacement_id = uuid4().hex
            if session_id:
                self._sessions.pop(session_id, None)
            self._sessions[replacement_id] = replacement
        return replacement_id, replacement

    def bind_or_replace(
        self, session_id: str | None, service: TravelPlannerService, owner_user_id: str
    ) -> tuple[str, WebSession]:
        """Bind a legacy session to its verified owner or replace another owner's."""

        with self._lock:
            now = self._clock()
            self._evict_idle(now)
            existing = self._sessions.get(session_id) if session_id else None
            if existing is None:
                if len(self._sessions) >= self._max_sessions:
                    raise SessionCapacityExceeded("The session capacity is exhausted.")
                replacement_id = uuid4().hex
                replacement = WebSession(
                    thread_id=service.create_session(),
                    owner_user_id=owner_user_id,
                    last_accessed=now,
                )
                self._sessions[replacement_id] = replacement
                return replacement_id, replacement
            with existing.lock:
                if existing.owner_user_id in {None, owner_user_id}:
                    existing.owner_user_id = owner_user_id
                    existing.last_accessed = now
                    return session_id or "", existing
            replacement_id = uuid4().hex
            replacement = WebSession(
                thread_id=service.create_session(),
                owner_user_id=owner_user_id,
                last_accessed=now,
            )
            if session_id:
                self._sessions.pop(session_id, None)
            self._sessions[replacement_id] = replacement
            return replacement_id, replacement

    def discard(self, session_id: str | None, owner_user_id: str) -> None:
        """Remove only a session owned by the account that is logging out."""

        if not session_id:
            return
        with self._lock:
            session = self._sessions.get(session_id)
            if session is None:
                return
            with session.lock:
                if session.owner_user_id == owner_user_id:
                    self._sessions.pop(session_id, None)

    def get(self, session_id: str | None) -> WebSession:
        if not session_id:
            raise HTTPException(status_code=401, detail="Hãy bắt đầu một phiên mới.")
        with self._lock:
            now = self._clock()
            self._evict_idle(now)
            session = self._sessions.get(session_id)
            if session is not None:
                session.last_accessed = now
        if session is None:
            raise HTTPException(
                status_code=401, detail="Phiên đã hết hạn. Hãy tạo lại lịch."
            )
        return session

    @property
    def session_count(self) -> int:
        """Return retained session count after lazy expiry for diagnostics and tests."""

        with self._lock:
            self._evict_idle(self._clock())
            return len(self._sessions)

    def _evict_idle(self, now: float) -> None:
        expired_ids: list[str] = []
        for session_id, session in self._sessions.items():
            if now - session.last_accessed <= self._idle_seconds:
                continue
            with session.lock:
                if session.pending is None or session.pending.future.done():
                    expired_ids.append(session_id)
        for session_id in expired_ids:
            self._sessions.pop(session_id, None)


def _response_payload(
    response: AgentResponse | None, language: Language
) -> dict[str, object] | None:
    if response is None:
        return None
    payload = response.model_dump(mode="json")
    payload["validation_issues"] = [
        {
            **issue.model_dump(mode="json"),
            "message": localized_issue_message(issue.code, issue.message, language),
        }
        for issue in response.validation_issues
    ]
    return payload


def _append_conversation(session: WebSession, turn: ConversationTurn) -> None:
    """Store one bounded transcript turn while its caller owns the session lock."""

    session.conversation.append(turn)
    session.conversation = session.conversation[-MAX_CONVERSATION_TURNS:]


def _session_payload(
    session: WebSession, response: AgentResponse | None
) -> dict[str, object]:
    return {
        "plan": (
            session.current_plan.model_dump(mode="json")
            if session.current_plan
            else None
        ),
        "response": _response_payload(response or session.response, session.language),
        "pending": session.pending is not None,
        "language": session.language,
        "conversation": [turn.model_dump(mode="json") for turn in session.conversation],
    }


def _secure_cookie(request: Request) -> bool:
    """Use Secure by default; allow explicit plain-HTTP local development."""

    configured = os.getenv("GTP_SAVED_TOURS_COOKIE_SECURE", "true").casefold()
    return (
        request.url.scheme == "https"
        or request.headers.get("x-forwarded-proto", "").casefold() == "https"
        or configured not in {"0", "false", "no", "off"}
    )


class SavedTourStore(Protocol):
    """Storage contract used by the HTTP adapter, regardless of database engine."""

    def save_for_user(
        self,
        user_id: str,
        plan: SightseeingPlan,
        visuals_by_entry: dict[str, dict[str, str]] | None = None,
    ) -> SavedTour: ...

    def list_for_user(
        self, user_id: str, *, cursor: str | None = None, limit: int = LIST_LIMIT
    ) -> SavedTourPage: ...

    def get_for_user(self, user_id: str, tour_id: str) -> SavedTour | None: ...

    def delete_for_user(self, user_id: str, tour_id: str) -> bool: ...

    def claim_for_user(self, user_id: str, legacy_owner_token: str) -> object: ...


def _saved_tour_store_from_environment() -> SavedTourStore:
    backend = os.getenv("GTP_SAVED_TOURS_BACKEND", "sqlite").casefold()
    if backend == "sqlite":
        return SavedTourRepository(DEFAULT_SAVED_TOURS_DATABASE_PATH)
    if backend == "postgres":
        from grounded_travel_planner.postgres_saved_tours import (
            PostgresSavedTourRepository,
        )

        try:
            port = int(os.getenv("GTP_SAVED_TOURS_POSTGRES_PORT", "5432"))
        except ValueError as error:
            raise SavedTourError("Invalid PostgreSQL saved-tour port.") from error
        return PostgresSavedTourRepository(
            host=os.getenv("GTP_SAVED_TOURS_POSTGRES_HOST", ""),
            database=os.getenv("GTP_SAVED_TOURS_POSTGRES_DATABASE", ""),
            user=os.getenv("GTP_SAVED_TOURS_POSTGRES_USER", ""),
            password=os.getenv("GTP_SAVED_TOURS_POSTGRES_PASSWORD", ""),
            port=port,
        )
    raise SavedTourError("Unsupported saved-tour backend.")


def _auth_repository_from_environment() -> AuthRepository | PostgresAuthRepository:
    backend = os.getenv("GTP_SAVED_TOURS_BACKEND", "sqlite").casefold()
    if backend == "sqlite":
        return AuthRepository(AUTH_DATABASE_PATH)
    if backend == "postgres":
        try:
            port = int(os.getenv("GTP_SAVED_TOURS_POSTGRES_PORT", "5432"))
        except ValueError as error:
            raise AuthError("Invalid PostgreSQL auth port.") from error
        return PostgresAuthRepository(
            host=os.getenv("GTP_SAVED_TOURS_POSTGRES_HOST", ""),
            database=os.getenv("GTP_SAVED_TOURS_POSTGRES_DATABASE", ""),
            user=os.getenv("GTP_SAVED_TOURS_POSTGRES_USER", ""),
            password=os.getenv("GTP_SAVED_TOURS_POSTGRES_PASSWORD", ""),
            port=port,
        )
    raise AuthError("Unsupported auth storage backend.")


def create_app(
    service: TravelPlannerService | None = None,
    visual_service: VisualEnrichmentService | None = None,
    turn_runner: TurnRunner | None = None,
    session_store: SessionStore | None = None,
    saved_tour_repository: SavedTourStore | None = None,
    auth_provider: OidcProvider | None = None,
    auth_repository: AuthRepository | PostgresAuthRepository | None = None,
    turn_rate_limiter: TurnRateLimiter | None = None,
    require_auth: bool = True,
) -> FastAPI:
    """Create an injectable app so endpoint tests need no live provider calls."""

    planner_service = service or TravelPlannerService.from_environment()
    visuals = visual_service or VisualEnrichmentService.from_environment()
    runner = turn_runner or TurnRunner()
    sessions = session_store or SessionStore()
    saved_tours = saved_tour_repository or _saved_tour_store_from_environment()
    auth = auth_repository or _auth_repository_from_environment()
    rate_limiter = turn_rate_limiter or TurnRateLimiter.from_environment()
    provider = auth_provider
    app = FastAPI(title="Grounded Travel Planner", docs_url=None, redoc_url=None)

    def current_user(auth_token: str | None) -> AuthenticatedUser:
        try:
            user = auth.authenticated(auth_token)
        except AuthError as error:
            raise HTTPException(
                status_code=503, detail="Không thể xác thực lúc này."
            ) from error
        if user is None:
            raise HTTPException(status_code=401, detail="Bạn cần đăng nhập.")
        return user

    def current_session(session_id: str | None, auth_token: str | None) -> WebSession:
        """Return live state only when its owner matches the verified account."""

        if not require_auth:
            return sessions.get(session_id)
        user = current_user(auth_token)
        session = sessions.get(session_id)
        if session.owner_user_id != user.user_id:
            raise HTTPException(
                status_code=401, detail="Phiên không thuộc tài khoản này."
            )
        return session

    def mutation_user(
        auth_token: str | None, csrf_token: str | None
    ) -> AuthenticatedUser | None:
        """Require CSRF before any authenticated planner state mutation."""

        if not require_auth:
            return None
        return csrf_user(auth_token, csrf_token)

    def mutation_session(
        session_id: str | None, auth_token: str | None, csrf_token: str | None
    ) -> WebSession:
        """Return an owned live session only after the CSRF check succeeds."""

        user = mutation_user(auth_token, csrf_token)
        if user is None:
            return sessions.get(session_id)
        session = sessions.get(session_id)
        if session.owner_user_id != user.user_id:
            raise HTTPException(
                status_code=401, detail="Phiên không thuộc tài khoản này."
            )
        return session

    def turn_principal(session: WebSession, auth_token: str | None) -> str:
        """Use only server-verified account identity or an opaque session ID."""

        try:
            user = auth.authenticated(auth_token)
        except AuthError as error:
            raise HTTPException(
                status_code=503, detail="Không thể xác thực lúc này."
            ) from error
        if user is not None:
            return f"account:{user.user_id}"
        return f"session:{session.thread_id}"

    def csrf_user(auth_token: str | None, csrf_token: str | None) -> AuthenticatedUser:
        try:
            user = auth.verify_csrf(auth_token, csrf_token)
        except AuthError as error:
            raise HTTPException(
                status_code=503, detail="Không thể xác thực lúc này."
            ) from error
        if user is None:
            if not auth_token:
                raise HTTPException(status_code=401, detail="Bạn cần đăng nhập.")
            raise HTTPException(status_code=403, detail="Yêu cầu bảo mật không hợp lệ.")
        return user

    def auth_public_origin(request: Request) -> str:
        origin = os.getenv("GTP_AUTH_PUBLIC_ORIGIN", "").strip().rstrip("/")
        if not origin:
            if isinstance(provider, Auth0OidcProvider):
                raise AuthError("The public auth origin is not configured.")
            return str(request.base_url).rstrip("/")

        parsed = urlsplit(origin)
        if (
            parsed.scheme not in {"http", "https"}
            or not parsed.netloc
            or parsed.hostname is None
            or parsed.username is not None
            or parsed.password is not None
            or parsed.path
            or parsed.query
            or parsed.fragment
        ):
            raise AuthError("The public auth origin is invalid.")
        if parsed.netloc.casefold() != request.headers.get("host", "").casefold():
            raise AuthError("The request host is not the configured auth origin.")
        return origin

    def callback_uri(request: Request) -> str:
        return f"{auth_public_origin(request)}/api/auth/callback"

    def logout_return_to(request: Request) -> str:
        return f"{auth_public_origin(request)}/"

    def pending_codec() -> PendingLoginCodec:
        secret = os.getenv("GTP_AUTH_SESSION_SECRET", "")
        return PendingLoginCodec(secret)

    def collect(session: WebSession) -> AgentResponse | None:
        if session.pending is None:
            return session.response
        completed = TurnRunner.collect(session.pending)
        if completed is None:
            return None
        session.pending = None
        session.response = completed
        if completed.committed and completed.current_plan is not None:
            session.current_plan = completed.current_plan
        _append_conversation(
            session,
            ConversationTurn(
                role="assistant",
                content=completed.message,
                source_references=completed.source_references,
            ),
        )
        session.session_summary = str(
            completed.metadata.get("session_summary", session.session_summary)
        )[:MAX_SESSION_SUMMARY]
        return completed

    @app.post("/api/session", status_code=201)
    def start_session(
        response: Response,
        request: Request,
        gtp_auth: str | None = Cookie(default=None, alias=AUTH_COOKIE_NAME),
        x_csrf_token: str | None = Header(default=None),
    ) -> dict[str, object]:
        user = mutation_user(gtp_auth, x_csrf_token)
        user_id = user.user_id if user is not None else None
        try:
            session_id, session = sessions.create(planner_service, user_id)
        except SessionCapacityExceeded as error:
            raise HTTPException(
                status_code=503,
                detail=localized("session_capacity_exhausted", "vi"),
            ) from error
        response.set_cookie(
            COOKIE_NAME,
            session_id,
            httponly=True,
            samesite="lax",
            secure=_secure_cookie(request),
            path="/",
        )
        return {**_session_payload(session, None), "thread_id": session.thread_id}

    @app.post("/api/session/reset")
    def reset_session(
        response: Response,
        request: Request,
        gtp_session: str | None = Cookie(default=None),
        gtp_auth: str | None = Cookie(default=None, alias=AUTH_COOKIE_NAME),
        x_csrf_token: str | None = Header(default=None),
    ) -> dict[str, object]:
        session = mutation_session(gtp_session, gtp_auth, x_csrf_token)
        try:
            session_id, session = sessions.replace(
                gtp_session, planner_service, session.owner_user_id
            )
        except SessionCapacityExceeded as error:
            raise HTTPException(
                status_code=503,
                detail=localized("session_capacity_exhausted", "vi"),
            ) from error
        response.set_cookie(
            COOKIE_NAME,
            session_id,
            httponly=True,
            samesite="lax",
            secure=_secure_cookie(request),
            path="/",
        )
        return {**_session_payload(session, None), "thread_id": session.thread_id}

    @app.put("/api/session/language")
    def update_language(
        payload: LanguageInput,
        gtp_session: str | None = Cookie(default=None),
        gtp_auth: str | None = Cookie(default=None, alias=AUTH_COOKIE_NAME),
        x_csrf_token: str | None = Header(default=None),
    ) -> dict[str, object]:
        """Change only UI/next-turn language for this existing browser session."""

        session = mutation_session(gtp_session, gtp_auth, x_csrf_token)
        with session.lock:
            session.language = payload.language
            return _session_payload(session, session.response)

    @app.get("/api/session")
    def read_session(
        gtp_session: str | None = Cookie(default=None),
        gtp_auth: str | None = Cookie(default=None, alias=AUTH_COOKIE_NAME),
    ) -> dict[str, object]:
        session = current_session(gtp_session, gtp_auth)
        with session.lock:
            completed = collect(session)
            return _session_payload(session, completed)

    @app.post("/api/turns", status_code=202)
    def submit_turn(
        payload: TurnInput,
        gtp_session: str | None = Cookie(default=None),
        gtp_auth: str | None = Cookie(default=None, alias=AUTH_COOKIE_NAME),
        x_csrf_token: str | None = Header(default=None),
    ) -> dict[str, bool]:
        session = mutation_session(gtp_session, gtp_auth, x_csrf_token)
        with session.lock:
            collect(session)
            if session.pending is not None:
                raise HTTPException(
                    status_code=409,
                    detail=localized("turn_pending", session.language),
                )
            quota = rate_limiter.reserve(turn_principal(session, gtp_auth))
            if isinstance(quota, TurnRateLimitExceeded):
                key = (
                    "turn_global_limit_exhausted"
                    if quota.scope in {"global", "principal_capacity"}
                    else "turn_rate_limit_exhausted"
                )
                raise HTTPException(
                    status_code=429,
                    detail=localized(key, session.language),
                    headers={"Retry-After": str(quota.retry_after_seconds)},
                )
            assert isinstance(quota, TurnQuotaReservation)
            try:
                pending = runner.submit(
                    planner_service,
                    thread_id=session.thread_id,
                    message=payload.message,
                    current_plan=session.current_plan,
                    request=payload.request,
                    session_summary=session.session_summary,
                    conversation_history=session.conversation[
                        -(MAX_CONVERSATION_TURNS - 1) :
                    ],
                    language=session.language,
                )
            except TurnCapacityExceeded as error:
                rate_limiter.refund(quota)
                raise HTTPException(
                    status_code=429,
                    detail=localized("turn_capacity_exhausted", session.language),
                ) from error
            session.response = None
            _append_conversation(
                session, ConversationTurn(role="user", content=payload.message)
            )
            session.pending = pending
        return {"accepted": True}

    @app.get("/api/graph")
    def graph() -> dict[str, str]:
        """Return the SVG fallback when the PNG renderer is unavailable."""

        return {"svg": compiled_graph_svg(planner_service.graph)}

    @app.get("/api/graph/image")
    def graph_image() -> Response:
        """Return a locally rendered graph SVG without running a planning turn."""

        try:
            image = compiled_graph_svg(planner_service.graph)
        except Exception as error:
            raise HTTPException(
                status_code=503,
                detail="Không thể tạo ảnh kiến trúc graph lúc này.",
            ) from error
        return Response(content=image, media_type="image/svg+xml")

    @app.get("/api/visuals")
    def plan_visuals(
        revision: int = Query(ge=1),
        gtp_session: str | None = Cookie(default=None),
        gtp_auth: str | None = Cookie(default=None, alias=AUTH_COOKIE_NAME),
    ) -> dict[str, object]:
        session = current_session(gtp_session, gtp_auth)
        with session.lock:
            plan = session.current_plan
            if plan is None or plan.revision != revision:
                raise HTTPException(status_code=409, detail="Lịch trình đã thay đổi.")
            captured_plan = plan.model_copy(deep=True)
        # Public image lookups are optional and may be slow. Do not hold the
        # session lock or let them affect the committed itinerary.
        try:
            resolved = visuals.resolve(captured_plan)
        except Exception:  # noqa: BLE001 - optional presentation data must not block UI
            resolved = {}
        return {
            "revision": revision,
            "visuals_by_entry": {
                entry_id: {
                    "image_url": visual.image_url,
                    "image_page_url": visual.image_page_url,
                    "image_alt": visual.image_alt,
                    "image_credit": visual.image_credit,
                    "image_license": visual.image_license,
                }
                for entry_id, visual in resolved.items()
            },
        }

    @app.get("/api/auth/me")
    def auth_me(gtp_auth: str | None = Cookie(default=None)) -> dict[str, object]:
        try:
            user = auth.authenticated(gtp_auth)
        except AuthError as error:
            raise HTTPException(
                status_code=503, detail="Không thể xác thực lúc này."
            ) from error
        if user is None:
            return {"authenticated": False}
        return {
            "authenticated": True,
            "email": user.email,
            "csrf_token": user.csrf_token,
        }

    @app.get("/api/auth/login")
    def auth_login(
        request: Request, return_to: str | None = Query(default=None)
    ) -> Response:
        nonlocal provider
        if provider is None:
            try:
                provider = Auth0OidcProvider.from_environment()
            except AuthError as error:
                raise HTTPException(
                    status_code=503, detail="Đăng nhập chưa được cấu hình."
                ) from error
        try:
            codec = pending_codec()
            pending, fields = codec.issue(return_to=safe_return_to(return_to))
            redirect = provider.authorization_url(
                state=fields["state"],
                nonce=fields["nonce"],
                code_verifier=fields["verifier"],
                redirect_uri=callback_uri(request),
            )
        except AuthError as error:
            raise HTTPException(
                status_code=503, detail="Không thể bắt đầu đăng nhập."
            ) from error
        response = RedirectResponse(redirect, status_code=307)
        response.set_cookie(
            AUTH_PENDING_COOKIE_NAME,
            pending,
            max_age=10 * 60,
            httponly=True,
            samesite="lax",
            secure=_secure_cookie(request),
            path="/api/auth",
        )
        return response

    @app.get("/api/auth/callback")
    def auth_callback(
        request: Request,
        code: str | None = Query(default=None),
        state: str | None = Query(default=None),
        gtp_auth_pending: str | None = Cookie(default=None),
        gtp_auth: str | None = Cookie(default=None),
        gtp_session: str | None = Cookie(default=None),
    ) -> Response:
        nonlocal provider
        if not code or not state or not gtp_auth_pending:
            raise HTTPException(
                status_code=400, detail="Phản hồi đăng nhập không hợp lệ."
            )
        try:
            codec = pending_codec()
            pending = codec.read(gtp_auth_pending)
            if not hmac.compare_digest(pending["state"], state):
                raise HTTPException(
                    status_code=400, detail="Trạng thái đăng nhập không hợp lệ."
                )
            if provider is None:
                provider = Auth0OidcProvider.from_environment()
            identity = provider.verify_callback(
                code=code,
                nonce=pending["nonce"],
                code_verifier=pending["verifier"],
                redirect_uri=callback_uri(request),
            )
            user_id, email = auth.find_or_create_user(identity)
            auth.revoke(gtp_auth)
            auth_token, _ = auth.issue_session(user_id, email)
            session_id, _ = sessions.bind_or_replace(
                gtp_session, planner_service, user_id
            )
        except (AuthError, SessionCapacityExceeded):
            failed = RedirectResponse("/?auth_error=login_failed", status_code=303)
            failed.delete_cookie(AUTH_PENDING_COOKIE_NAME, path="/api/auth")
            return failed
        completed = RedirectResponse(
            safe_return_to(pending["return_to"]), status_code=303
        )
        completed.delete_cookie(AUTH_PENDING_COOKIE_NAME, path="/api/auth")
        completed.set_cookie(
            AUTH_COOKIE_NAME,
            auth_token,
            max_age=AUTH_ABSOLUTE_SECONDS,
            httponly=True,
            samesite="lax",
            secure=_secure_cookie(request),
            path="/",
        )
        completed.set_cookie(
            COOKIE_NAME,
            session_id,
            httponly=True,
            samesite="lax",
            secure=_secure_cookie(request),
            path="/",
        )
        return completed

    @app.post("/api/auth/logout")
    def auth_logout(
        request: Request,
        gtp_auth: str | None = Cookie(default=None),
        gtp_session: str | None = Cookie(default=None),
        x_csrf_token: str | None = Header(default=None),
    ) -> Response:
        nonlocal provider
        user = csrf_user(gtp_auth, x_csrf_token)
        # Revoke first so a provider outage cannot leave an app session usable.
        auth.revoke(gtp_auth)
        sessions.discard(gtp_session, user.user_id)
        try:
            if provider is None:
                provider = Auth0OidcProvider.from_environment()
            logout_url = provider.logout_url(return_to=logout_return_to(request))
        except AuthError as error:
            raise HTTPException(
                status_code=503, detail="Không thể đăng xuất lúc này."
            ) from error
        completed = Response(
            content=json.dumps({"logout_url": logout_url}),
            media_type="application/json",
        )
        completed.delete_cookie(AUTH_COOKIE_NAME, path="/")
        completed.delete_cookie(COOKIE_NAME, path="/")
        return completed

    @app.get("/api/saved-tours")
    def list_saved_tours(
        request: Request,
        cursor: str | None = Query(default=None, max_length=512),
        limit: int = Query(default=LIST_LIMIT, ge=1, le=LIST_LIMIT),
        gtp_auth: str | None = Cookie(default=None),
    ) -> dict[str, object]:
        """List only snapshots belonging to the durable browser owner cookie."""

        try:
            if "offset" in request.query_params:
                raise InvalidSavedTourCursor("Offset pagination is not supported.")
            if cursor is not None:
                SavedTourRepository.decode_cursor(cursor)
            user = current_user(gtp_auth)
            page = saved_tours.list_for_user(user.user_id, cursor=cursor, limit=limit)
        except InvalidSavedTourCursor as error:
            raise HTTPException(
                status_code=422, detail="Cursor không hợp lệ."
            ) from error
        except SavedTourError as error:
            raise HTTPException(
                status_code=503, detail="Không thể tải tour đã lưu lúc này."
            ) from error
        return {
            "items": [item.payload() for item in page.items],
            "has_more": page.has_more,
            "next_cursor": page.next_cursor,
        }

    @app.post("/api/saved-tours")
    def save_current_tour(
        gtp_session: str | None = Cookie(default=None),
        gtp_auth: str | None = Cookie(default=None),
        x_csrf_token: str | None = Header(default=None),
    ) -> dict[str, object]:
        """Persist the current accepted plan only after an explicit user action."""

        user = csrf_user(gtp_auth, x_csrf_token)
        session = current_session(gtp_session, gtp_auth)
        with session.lock:
            if session.pending is not None:
                raise HTTPException(
                    status_code=409,
                    detail=localized("turn_pending", session.language),
                )
            if session.current_plan is None:
                raise HTTPException(
                    status_code=409, detail="Chưa có lịch trình hợp lệ để lưu."
                )
            plan = session.current_plan.model_copy(deep=True)
        try:
            resolved_visuals = visuals.resolve_saved(plan)
        except Exception:  # noqa: BLE001 - optional images cannot block a save
            resolved_visuals = {}
        visuals_by_entry = {
            entry_id: {
                key: value
                for key, value in {
                    "image_url": visual.image_url,
                    "image_page_url": visual.image_page_url,
                    "image_alt": visual.image_alt,
                    "image_credit": visual.image_credit,
                    "image_license": visual.image_license,
                    "image_data_base64": visual.image_data_base64,
                    "image_media_type": visual.image_media_type,
                }.items()
                if isinstance(value, str)
            }
            for entry_id, visual in resolved_visuals.items()
            if visual.image_data_base64 and visual.image_media_type
        }
        try:
            saved_tour = saved_tours.save_for_user(
                user.user_id, plan, visuals_by_entry=visuals_by_entry
            )
        except SavedTourError as error:
            raise HTTPException(
                status_code=503, detail="Không thể lưu tour lúc này."
            ) from error
        return saved_tour.payload()

    @app.get("/api/saved-tours/{tour_id}")
    def read_saved_tour(
        tour_id: str,
        gtp_auth: str | None = Cookie(default=None),
    ) -> dict[str, object]:
        user = current_user(gtp_auth)
        try:
            saved_tour = saved_tours.get_for_user(user.user_id, tour_id)
        except SavedTourError as error:
            raise HTTPException(
                status_code=503, detail="Không thể đọc tour đã lưu lúc này."
            ) from error
        if saved_tour is None:
            raise HTTPException(status_code=404, detail="Không tìm thấy tour đã lưu.")
        return saved_tour.payload()

    @app.delete("/api/saved-tours/{tour_id}", status_code=204)
    def delete_saved_tour(
        tour_id: str,
        gtp_auth: str | None = Cookie(default=None),
        x_csrf_token: str | None = Header(default=None),
    ) -> Response:
        user = csrf_user(gtp_auth, x_csrf_token)
        try:
            deleted = saved_tours.delete_for_user(user.user_id, tour_id)
        except SavedTourError as error:
            raise HTTPException(
                status_code=503, detail="Không thể xóa tour đã lưu lúc này."
            ) from error
        if not deleted:
            raise HTTPException(status_code=404, detail="Không tìm thấy tour đã lưu.")
        return Response(status_code=204)

    @app.post("/api/saved-tours/claim")
    def claim_saved_tours(
        gtp_auth: str | None = Cookie(default=None),
        x_csrf_token: str | None = Header(default=None),
        gtp_saved_tours_owner: str | None = Cookie(default=None),
    ) -> object:
        user = csrf_user(gtp_auth, x_csrf_token)
        if not gtp_saved_tours_owner:
            raise HTTPException(status_code=409, detail="Không có tour cũ để nhận.")
        try:
            return saved_tours.claim_for_user(user.user_id, gtp_saved_tours_owner)
        except SavedTourError as error:
            raise HTTPException(
                status_code=503, detail="Không thể nhận tour cũ lúc này."
            ) from error

    if FRONTEND_DIST.is_dir():
        app.mount(
            "/assets", StaticFiles(directory=FRONTEND_DIST / "assets"), name="assets"
        )

        @app.get("/{path:path}")
        def frontend(path: str) -> FileResponse:
            candidate = (FRONTEND_DIST / path).resolve()
            return FileResponse(
                candidate
                if path
                and candidate.is_relative_to(FRONTEND_DIST)
                and candidate.is_file()
                else FRONTEND_DIST / "index.html"
            )

    return app


app = create_app()
