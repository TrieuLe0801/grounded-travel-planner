"""Grounding checks for place references returned by search."""

from __future__ import annotations

import unicodedata
from urllib.parse import urlparse

from grounded_travel_planner.contracts import SightseeingPlan, ValidationIssue


def _tokens(value: str) -> set[str]:
    normalized = unicodedata.normalize("NFKD", value)
    ascii_value = "".join(
        char for char in normalized if not unicodedata.combining(char)
    )
    return {
        token
        for token in "".join(
            char.lower() if char.isalnum() else " " for char in ascii_value
        ).split()
        if len(token) >= 4
    }


def validate_sources(
    plan: SightseeingPlan,
    returned_source_urls: set[str],
) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    allowed_urls = {url.rstrip("/") for url in returned_source_urls}
    for place in plan.entries:
        recommendation = place.place
        if not recommendation.source_references:
            issues.append(
                ValidationIssue(
                    code="place_source_required",
                    message=f"{recommendation.name} needs a returned source.",
                    entry_id=place.id,
                )
            )
            continue
        place_tokens = _tokens(recommendation.name)
        for source in recommendation.source_references:
            url = str(source.url).rstrip("/")
            parsed = urlparse(url)
            if parsed.scheme not in {"http", "https"} or not parsed.netloc:
                issues.append(
                    ValidationIssue(
                        code="invalid_source_url",
                        message=f"Source for {recommendation.name} is not HTTP(S).",
                        entry_id=place.id,
                    )
                )
            if url not in allowed_urls:
                issues.append(
                    ValidationIssue(
                        code="source_not_returned",
                        message=(
                            f"Source for {recommendation.name} was not returned by "
                            "the active search provider."
                        ),
                        entry_id=place.id,
                    )
                )
            # The query expresses intent; it is not evidence that the returned
            # page actually identifies the recommended place.
            evidence_text = " ".join(filter(None, (source.title, source.snippet)))
            if place_tokens and not place_tokens.intersection(_tokens(evidence_text)):
                issues.append(
                    ValidationIssue(
                        code="source_place_mismatch",
                        message=f"Source does not identify {recommendation.name}.",
                        entry_id=place.id,
                    )
                )
        if recommendation.opening_hours_verified:
            if not recommendation.opening_hours:
                issues.append(
                    ValidationIssue(
                        code="opening_hours_missing",
                        message=f"Verified hours are missing for {recommendation.name}.",
                        entry_id=place.id,
                    )
                )
            if not any(
                source.supports_opening_hours
                for source in recommendation.source_references
            ):
                issues.append(
                    ValidationIssue(
                        code="opening_hours_unsubstantiated",
                        message=(
                            f"Opening hours for {recommendation.name} are not "
                            "supported by returned evidence."
                        ),
                        entry_id=place.id,
                    )
                )
        elif recommendation.opening_hours not in {None, "unverified"}:
            issues.append(
                ValidationIssue(
                    code="opening_hours_must_be_unverified",
                    message=(
                        f"Opening hours for {recommendation.name} must be labelled "
                        "unverified."
                    ),
                    entry_id=place.id,
                )
            )
    return issues
