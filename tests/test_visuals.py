"""Offline contracts for source-backed itinerary photos."""

from __future__ import annotations

from datetime import date, time

import pytest

from grounded_travel_planner.contracts import (
    PlaceRecommendation,
    ScheduleEntry,
    SightseeingPlan,
    SourceReference,
)
from grounded_travel_planner.visuals import PlaceVisual, VisualEnrichmentService


@pytest.fixture(autouse=True)
def clear_public_visual_cache() -> None:
    VisualEnrichmentService._cache.clear()


def _plan(names: list[str]) -> SightseeingPlan:
    source = SourceReference(
        source_id="source_visual",
        title="Imperial City of Hue",
        url="https://travel.example/hue/imperial-city",
    )
    return SightseeingPlan(
        plan_id="visual_test",
        destination="Hue",
        start_date=date(2026, 11, 1),
        day_count=1,
        entries=[
            ScheduleEntry(
                id=f"entry_{index}",
                day_index=1,
                start_time=time(9),
                end_time=time(10),
                place=PlaceRecommendation(
                    place_id=f"place_{index}",
                    name=name,
                    description="A sourced place.",
                    source_references=[source],
                    opening_hours="unverified",
                ),
            )
            for index, name in enumerate(names)
        ],
    )


def test_commons_photo_keeps_attribution_and_cache(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = VisualEnrichmentService(user_agent="visual-test")
    calls: list[tuple[str, dict[str, str]]] = []

    def fake_get(endpoint: str, params: dict[str, str]):
        calls.append((endpoint, params))
        if params.get("list") == "search":
            return {
                "query": {"search": [{"title": "File:Gate in Imperial City, Huế.jpg"}]}
            }
        assert params["iiurlwidth"] == "960"
        return {
            "query": {
                "pages": [
                    {
                        "imageinfo": [
                            {
                                "thumburl": "https://thumb.wikimedia.org/city.jpg",
                                "descriptionurl": "https://commons.wikimedia.org/wiki/File:City.jpg",
                                "extmetadata": {
                                    "Artist": {"value": "<a>Example photographer</a>"},
                                    "LicenseShortName": {"value": "CC BY-SA 4.0"},
                                },
                            }
                        ]
                    }
                ]
            }
        }

    monkeypatch.setattr(service, "_get_json", fake_get)
    visual = service.resolve(_plan(["Imperial City"]))["entry_0"]

    assert visual.image_url == "https://thumb.wikimedia.org/city.jpg"
    assert visual.image_page_url == "https://commons.wikimedia.org/wiki/File:City.jpg"
    assert visual.image_credit == "Example photographer"
    assert visual.image_license == "CC BY-SA 4.0"
    assert visual.image_alt == "Gate in Imperial City, Huế"
    assert not hasattr(visual, "latitude")
    assert len(calls) == 2
    assert service.resolve(_plan(["Imperial City"]))["entry_0"] == visual
    assert len(calls) == 2


def test_missing_or_failed_photo_lookup_returns_no_visual(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = VisualEnrichmentService(user_agent="visual-test")
    monkeypatch.setattr(
        service, "_get_json", lambda endpoint, params: {"query": {"search": []}}
    )

    assert service.resolve(_plan(["Imperial City"])) == {}

    failing_service = VisualEnrichmentService(user_agent="visual-test")
    monkeypatch.setattr(
        failing_service,
        "_get_json",
        lambda endpoint, params: (_ for _ in ()).throw(OSError("image unavailable")),
    )
    assert failing_service.resolve(_plan(["Hue Museum"])) == {}


def test_photo_lookups_are_bounded_to_twelve_stops() -> None:
    class CountingService(VisualEnrichmentService):
        def __init__(self) -> None:
            super().__init__(user_agent="visual-test")
            self.calls: list[str] = []

        def _resolve_place(self, place_name: str, destination: str) -> PlaceVisual:
            self.calls.append(place_name)
            return PlaceVisual(place_name=place_name)

    service = CountingService()
    visuals = service.resolve(_plan([f"Place {index}" for index in range(13)]))

    assert len(visuals) == 12
    assert len(service.calls) == 12
