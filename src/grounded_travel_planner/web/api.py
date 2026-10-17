"""Thin HTTP adapter that keeps itinerary state in one browser session only."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from threading import Lock
from uuid import uuid4

from fastapi import Cookie, FastAPI, HTTPException, Query, Response
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from grounded_travel_planner.contracts import (
    AgentResponse,
    SightseeingPlan,
    TripRequest,
)
from grounded_travel_planner.service import TravelPlannerService
from grounded_travel_planner.ui.graph_diagram import compiled_graph_svg
from grounded_travel_planner.ui.turn_runner import PendingTurn, TurnRunner
from grounded_travel_planner.visuals import VisualEnrichmentService

COOKIE_NAME = "gtp_session"
FRONTEND_DIST = Path(
    os.getenv("GTP_FRONTEND_DIST", Path.cwd() / "frontend" / "dist")
).resolve()


class TurnInput(BaseModel):
    """HTTP payload for either a new itinerary or a chat turn."""

    message: str = Field(min_length=1, max_length=4000)
    request: TripRequest | None = None


@dataclass
class WebSession:
    """Volatile state keyed only by an opaque HttpOnly browser cookie."""

    thread_id: str
    current_plan: SightseeingPlan | None = None
    pending: PendingTurn | None = None
    response: AgentResponse | None = None
    lock: Lock = field(default_factory=Lock)


class SessionStore:
    """Small in-memory store; replacing the process intentionally clears it."""

    def __init__(self) -> None:
        self._sessions: dict[str, WebSession] = {}
        self._lock = Lock()

    def create(self, service: TravelPlannerService) -> tuple[str, WebSession]:
        session_id = uuid4().hex
        session = WebSession(thread_id=service.create_session())
        with self._lock:
            self._sessions[session_id] = session
        return session_id, session

    def get(self, session_id: str | None) -> WebSession:
        if not session_id:
            raise HTTPException(status_code=401, detail="Hãy bắt đầu một phiên mới.")
        with self._lock:
            session = self._sessions.get(session_id)
        if session is None:
            raise HTTPException(
                status_code=401, detail="Phiên đã hết hạn. Hãy tạo lại lịch."
            )
        return session


def _response_payload(response: AgentResponse | None) -> dict[str, object] | None:
    return response.model_dump(mode="json") if response else None


def create_app(
    service: TravelPlannerService | None = None,
    visual_service: VisualEnrichmentService | None = None,
) -> FastAPI:
    """Create an injectable app so endpoint tests need no live provider calls."""

    planner_service = service or TravelPlannerService.from_environment()
    visuals = visual_service or VisualEnrichmentService.from_environment()
    runner = TurnRunner()
    sessions = SessionStore()
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
        return completed

    @app.post("/api/session", status_code=201)
    def start_session(response: Response) -> dict[str, object]:
        session_id, session = sessions.create(planner_service)
        response.set_cookie(
            COOKIE_NAME,
            session_id,
            httponly=True,
            samesite="lax",
            secure=False,
            path="/",
        )
        return {
            "plan": None,
            "response": None,
            "pending": False,
            "thread_id": session.thread_id,
        }

    @app.post("/api/session/reset")
    def reset_session(response: Response) -> dict[str, object]:
        session_id, session = sessions.create(planner_service)
        response.set_cookie(
            COOKIE_NAME, session_id, httponly=True, samesite="lax", path="/"
        )
        return {
            "plan": None,
            "response": None,
            "pending": False,
            "thread_id": session.thread_id,
        }

    @app.get("/api/session")
    def read_session(
        gtp_session: str | None = Cookie(default=None),
    ) -> dict[str, object]:
        session = current_session(gtp_session)
        with session.lock:
            completed = collect(session)
            return {
                "plan": (
                    session.current_plan.model_dump(mode="json")
                    if session.current_plan
                    else None
                ),
                "response": _response_payload(completed or session.response),
                "pending": session.pending is not None,
            }

    @app.post("/api/turns", status_code=202)
    def submit_turn(
        payload: TurnInput, gtp_session: str | None = Cookie(default=None)
    ) -> dict[str, bool]:
        session = current_session(gtp_session)
        with session.lock:
            collect(session)
            if session.pending is not None:
                raise HTTPException(
                    status_code=409, detail="Một yêu cầu đang được xử lý."
                )
            session.response = None
            session.pending = runner.submit(
                planner_service,
                thread_id=session.thread_id,
                message=payload.message,
                current_plan=session.current_plan,
                request=payload.request,
            )
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
