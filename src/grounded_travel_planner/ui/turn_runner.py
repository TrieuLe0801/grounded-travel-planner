"""Background execution for bounded Streamlit planning turns."""

from __future__ import annotations

from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass
from uuid import uuid4

from grounded_travel_planner.contracts import (
    AgentResponse,
    ResponseStatus,
    SightseeingPlan,
    TripRequest,
    ValidationIssue,
)
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


class TurnRunner:
    """Run blocking service calls without letting workers touch Streamlit state."""

    def __init__(self, max_workers: int = 4) -> None:
        self._executor = ThreadPoolExecutor(
            max_workers=max_workers,
            thread_name_prefix="travel-planner-turn",
        )

    def submit(
        self,
        service: TravelPlannerService,
        *,
        thread_id: str,
        message: str,
        current_plan: SightseeingPlan | None,
        request: TripRequest | None = None,
    ) -> PendingTurn:
        """Capture a turn before scheduling it on the shared bounded executor."""

        captured_plan = current_plan.model_copy(deep=True) if current_plan else None
        captured_request = request.model_copy(deep=True) if request else None
        captured_thread_id = str(thread_id)
        captured_message = str(message)
        future = self._executor.submit(
            self._run_turn,
            service,
            captured_thread_id,
            captured_message,
            captured_plan,
            captured_request,
        )
        return PendingTurn(
            token=uuid4().hex,
            thread_id=captured_thread_id,
            message=captured_message,
            current_plan=captured_plan,
            request=captured_request,
            future=future,
        )

    @staticmethod
    def collect(pending: PendingTurn) -> AgentResponse | None:
        """Return a completed result, preserving the captured plan on failure."""

        if not pending.future.done():
            return None
        try:
            return pending.future.result()
        except Exception:  # noqa: BLE001 - executor failures must preserve the plan
            return TurnRunner._provider_error(pending.current_plan)

    @staticmethod
    def _run_turn(
        service: TravelPlannerService,
        thread_id: str,
        message: str,
        current_plan: SightseeingPlan | None,
        request: TripRequest | None,
    ) -> AgentResponse:
        """Invoke the service from a worker with captured data only."""

        try:
            return service.handle_turn(
                thread_id=thread_id,
                message=message,
                current_plan=current_plan,
                request=request,
            )
        except Exception:  # noqa: BLE001 - the UI must remain responsive
            return TurnRunner._provider_error(current_plan)

    @staticmethod
    def _provider_error(current_plan: SightseeingPlan | None) -> AgentResponse:
        safe_plan = current_plan.model_copy(deep=True) if current_plan else None
        return AgentResponse(
            status=ResponseStatus.PROVIDER_ERROR,
            message=(
                "Chưa thể hoàn tất yêu cầu; lịch trình trước đó vẫn được giữ nguyên."
            ),
            current_plan=safe_plan,
            validation_issues=[
                ValidationIssue(
                    code="background_turn_failure",
                    message="The background planning turn did not complete.",
                )
            ],
        )
