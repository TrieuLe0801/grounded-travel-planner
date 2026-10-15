"""Candidate validation before canonical plan mutation."""

from __future__ import annotations

from grounded_travel_planner.contracts import (
    PlanCandidate,
    PlanChangeIntent,
    SightseeingPlan,
    TripRequest,
    ValidationIssue,
)
from grounded_travel_planner.policies.change_validation import (
    validate_requested_change,
)
from grounded_travel_planner.policies.input_validation import validate_trip_request
from grounded_travel_planner.policies.schedule_validation import validate_schedule
from grounded_travel_planner.policies.source_validation import validate_sources


def validate_candidate(
    candidate: PlanCandidate | None,
    request: TripRequest | None,
    *,
    intent: PlanChangeIntent | None = None,
    current_plan: SightseeingPlan | None = None,
) -> list[ValidationIssue]:
    issues = validate_trip_request(request)
    if candidate is None or candidate.plan is None:
        issues.append(
            ValidationIssue(
                code="candidate_required",
                message="Planner did not produce a candidate plan.",
            )
        )
        return issues
    plan = candidate.plan
    if request is not None and (
        plan.destination.casefold() != request.destination.casefold()
        or plan.start_date != request.start_date
        or plan.day_count != request.day_count
    ):
        issues.append(
            ValidationIssue(
                code="candidate_request_mismatch",
                message="Candidate does not preserve destination, start date and days.",
            )
        )
    # Model-authored notes are advisory. Only deterministic policies below may
    # block commit; otherwise an informational "unverified" note can reject an
    # otherwise grounded plan.
    issues.extend(validate_schedule(plan))
    issues.extend(validate_sources(plan, candidate.returned_source_urls))
    issues.extend(validate_requested_change(intent, current_plan, plan))
    return issues
