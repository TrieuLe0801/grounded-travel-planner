"""Thin HTTP adapter that keeps itinerary state in one browser session only."""

from __future__ import annotations

import os
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from threading import Lock
from time import monotonic
from typing import Literal
from uuid import uuid4

from fastapi import Cookie, FastAPI, HTTPException, Query, Response
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

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
from grounded_travel_planner.service import TravelPlannerService
from grounded_travel_planner.ui.graph_diagram import compiled_graph_svg
from grounded_travel_planner.ui.turn_runner import (
    PendingTurn,
    TurnCapacityExceeded,
    TurnRunner,
)
from grounded_travel_planner.visuals import VisualEnrichmentService

COOKIE_NAME = "gtp_session"
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

    def create(self, service: TravelPlannerService) -> tuple[str, WebSession]:
        with self._lock:
            now = self._clock()
            self._evict_idle(now)
            if len(self._sessions) >= self._max_sessions:
                raise SessionCapacityExceeded("The session capacity is exhausted.")
            session_id = uuid4().hex
            session = WebSession(thread_id=service.create_session(), last_accessed=now)
            self._sessions[session_id] = session
        return session_id, session

    def replace(
        self, session_id: str | None, service: TravelPlannerService
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
                language=language,
                last_accessed=now,
            )
            replacement_id = uuid4().hex
            if session_id:
                self._sessions.pop(session_id, None)
            self._sessions[replacement_id] = replacement
        return replacement_id, replacement

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


def create_app(
    service: TravelPlannerService | None = None,
    visual_service: VisualEnrichmentService | None = None,
    turn_runner: TurnRunner | None = None,
    session_store: SessionStore | None = None,
) -> FastAPI:
    """Create an injectable app so endpoint tests need no live provider calls."""

    planner_service = service or TravelPlannerService.from_environment()
    visuals = visual_service or VisualEnrichmentService.from_environment()
    runner = turn_runner or TurnRunner()
    sessions = session_store or SessionStore()
    app = FastAPI(title="Grounded Travel Planner", docs_url=None, redoc_url=None)

    def current_session(session_id: str | None) -> WebSession:
        return sessions.get(session_id)

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
    def start_session(response: Response) -> dict[str, object]:
        try:
            session_id, session = sessions.create(planner_service)
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
            secure=False,
            path="/",
        )
        return {**_session_payload(session, None), "thread_id": session.thread_id}

    @app.post("/api/session/reset")
    def reset_session(
        response: Response, gtp_session: str | None = Cookie(default=None)
    ) -> dict[str, object]:
        try:
            session_id, session = sessions.replace(gtp_session, planner_service)
        except SessionCapacityExceeded as error:
            raise HTTPException(
                status_code=503,
                detail=localized("session_capacity_exhausted", "vi"),
            ) from error
        response.set_cookie(
            COOKIE_NAME, session_id, httponly=True, samesite="lax", path="/"
        )
        return {**_session_payload(session, None), "thread_id": session.thread_id}

    @app.put("/api/session/language")
    def update_language(
        payload: LanguageInput,
        gtp_session: str | None = Cookie(default=None),
    ) -> dict[str, object]:
        """Change only UI/next-turn language for this existing browser session."""

        session = current_session(gtp_session)
        with session.lock:
            session.language = payload.language
            return _session_payload(session, session.response)

    @app.get("/api/session")
    def read_session(
        gtp_session: str | None = Cookie(default=None),
    ) -> dict[str, object]:
        session = current_session(gtp_session)
        with session.lock:
            completed = collect(session)
            return _session_payload(session, completed)

    @app.post("/api/turns", status_code=202)
    def submit_turn(
        payload: TurnInput, gtp_session: str | None = Cookie(default=None)
    ) -> dict[str, bool]:
        session = current_session(gtp_session)
        with session.lock:
            collect(session)
            if session.pending is not None:
                raise HTTPException(
                    status_code=409,
                    detail=localized("turn_pending", session.language),
                )
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
        """Return the compiled LangGraph PNG without running a planning turn."""

        try:
            image = planner_service.get_graph_image()
        except Exception as error:
            raise HTTPException(
                status_code=503,
                detail="Không thể tạo ảnh kiến trúc graph lúc này.",
            ) from error
        return Response(content=image, media_type="image/png")

    @app.get("/api/visuals")
    def plan_visuals(
        revision: int = Query(ge=1),
        gtp_session: str | None = Cookie(default=None),
    ) -> dict[str, object]:
        session = current_session(gtp_session)
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
