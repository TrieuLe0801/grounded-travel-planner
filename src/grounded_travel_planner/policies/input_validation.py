"""Input checks run before Planner or Tavily calls."""

from __future__ import annotations

from grounded_travel_planner.contracts import TripRequest, ValidationIssue


def validate_trip_request(request: TripRequest | None) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    if request is None:
        return [
            ValidationIssue(
                code="trip_request_required",
                message="Destination, concrete start date and day count are required.",
            )
        ]
    if not request.destination.strip():
        issues.append(
            ValidationIssue(
                code="destination_required",
                message="Destination or place must not be blank.",
            )
        )
    if request.day_count < 1 or request.day_count > 7:
        issues.append(
            ValidationIssue(
                code="day_count_out_of_range",
                message="Day count must be between 1 and 7.",
            )
        )
    return issues
