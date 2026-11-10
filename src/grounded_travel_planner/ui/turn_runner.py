"""Background execution for bounded Streamlit planning turns."""

from __future__ import annotations

from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass
from threading import BoundedSemaphore
from uuid import uuid4

from grounded_travel_planner.contracts import (
    AgentResponse,
    ConversationTurn,
    ResponseStatus,
    SightseeingPlan,
    TripRequest,
    ValidationIssue,
)
from grounded_travel_planner.conversation import bounded_history, bounded_summary
from grounded_travel_planner.i18n import Language, localized
from grounded_travel_planner.service import TravelPlannerService


@dataclass(frozen=True)
class PendingTurn:
    """An immutable UI-session record for a submitted planning turn."""

    token: str
    thread_id: str
    message: str
    current_plan: SightseeingPlan | None
    request: TripRequest | None
    future: Future[AgentResponse]
    language: Language = "vi"


class TurnCapacityExceeded(RuntimeError):
    """Raised when the shared worker queue has reached its bounded capacity."""


class TurnRunner:
    """Run blocking service calls without letting workers touch Streamlit state."""

    def __init__(self, max_workers: int = 4, max_pending_turns: int = 8) -> None:
        if max_workers < 1:
            raise ValueError("max_workers must be positive")
        if max_pending_turns < 1:
            raise ValueError("max_pending_turns must be positive")
        self._executor = ThreadPoolExecutor(
            max_workers=max_workers,
            thread_name_prefix="travel-planner-turn",
        )
        # ThreadPoolExecutor bounds workers, but its internal queue is unbounded.
        # Reserve one slot for every queued or executing turn before submitting.
        self._pending_slots = BoundedSemaphore(max_pending_turns)

    def submit(
        self,
        service: TravelPlannerService,
        *,
        thread_id: str,
        message: str,
        current_plan: SightseeingPlan | None,
        request: TripRequest | None = None,
        session_summary: str = "",
        conversation_history: list[ConversationTurn] | None = None,
        language: Language = "vi",
    ) -> PendingTurn:
        """Capture a turn before scheduling it on the shared bounded executor."""

        if not self._pending_slots.acquire(blocking=False):
            raise TurnCapacityExceeded("The shared turn capacity is exhausted.")

        try:
            captured_plan = current_plan.model_copy(deep=True) if current_plan else None
            captured_request = request.model_copy(deep=True) if request else None
            captured_thread_id = str(thread_id)
            captured_message = str(message)
            captured_summary = bounded_summary(session_summary)
            captured_history = bounded_history(conversation_history or [])
            future = self._executor.submit(
                self._run_turn,
                service,
                captured_thread_id,
                captured_message,
                captured_plan,
                captured_request,
                captured_summary,
                captured_history,
                language,
            )
        except Exception:
            self._pending_slots.release()
            raise
        future.add_done_callback(self._release_pending_slot)
        return PendingTurn(
            token=uuid4().hex,
            thread_id=captured_thread_id,
            message=captured_message,
            current_plan=captured_plan,
            request=captured_request,
            language=language,
            future=future,
        )

    def _release_pending_slot(self, _: Future[AgentResponse]) -> None:
        """Release capacity once, even when no UI request polls the Future."""

        self._pending_slots.release()

    @staticmethod
    def collect(pending: PendingTurn) -> AgentResponse | None:
        """Return a completed result, preserving the captured plan on failure."""

        if not pending.future.done():
            return None
        try:
            return pending.future.result()
        except Exception:  # noqa: BLE001 - executor failures must preserve the plan
            return TurnRunner._provider_error(pending.current_plan, pending.language)

    @staticmethod
    def _run_turn(
        service: TravelPlannerService,
        thread_id: str,
        message: str,
        current_plan: SightseeingPlan | None,
        request: TripRequest | None,
        session_summary: str,
        conversation_history: list[ConversationTurn],
        language: Language,
    ) -> AgentResponse:
        """Invoke the service from a worker with captured data only."""

        try:
            return service.handle_turn(
                thread_id=thread_id,
                message=message,
                current_plan=current_plan,
                request=request,
                session_summary=session_summary,
                conversation_history=conversation_history,
                language=language,
            )
        except Exception:  # noqa: BLE001 - the UI must remain responsive
            return TurnRunner._provider_error(current_plan, language)

    @staticmethod
    def _provider_error(
        current_plan: SightseeingPlan | None, language: Language = "vi"
    ) -> AgentResponse:
        safe_plan = current_plan.model_copy(deep=True) if current_plan else None
        return AgentResponse(
            status=ResponseStatus.PROVIDER_ERROR,
            message=localized("background_failure", language),
            current_plan=safe_plan,
            validation_issues=[
                ValidationIssue(
                    code="background_turn_failure",
                    message="The background planning turn did not complete.",
                )
            ],
        )
