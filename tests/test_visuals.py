"""Offline contracts for source-backed itinerary photos."""

from __future__ import annotations

from base64 import b64decode
from datetime import date, time
from urllib.error import HTTPError

import pytest
from typing_extensions import Self

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


def test_saved_visual_encodes_downloaded_image_and_keeps_attribution(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Explicit archive saves retain local image bytes without another lookup."""

    service = VisualEnrichmentService(user_agent="visual-test")
    visual = PlaceVisual(
        place_name="Imperial City",
        image_url="https://thumb.wikimedia.org/city.jpg",
        image_page_url="https://commons.wikimedia.org/wiki/File:City.jpg",
        image_alt="Gate in Imperial City, Huế",
        image_credit="Example photographer",
        image_license="CC BY-SA 4.0",
    )
    monkeypatch.setattr(service, "resolve", lambda plan: {"entry_0": visual})
    monkeypatch.setattr(
        service,
        "_download_saved_image",
        lambda image_url: (b"offline-image", "image/jpeg"),
    )

    saved = service.resolve_saved(_plan(["Imperial City"]))["entry_0"]

    assert b64decode(saved.image_data_base64 or "") == b"offline-image"
    assert saved.image_media_type == "image/jpeg"
    assert saved.image_page_url == visual.image_page_url
    assert saved.image_credit == visual.image_credit
    assert saved.image_license == visual.image_license


def test_saved_visual_rejects_untrusted_image_host() -> None:
    service = VisualEnrichmentService(user_agent="visual-test")

    with pytest.raises(ValueError, match="trusted"):
        service._download_saved_image("https://example.test/image.jpg")


class _FakeHeaders:
    def __init__(self, media_type: str, content_length: str | None = None) -> None:
        self._media_type = media_type
        self._content_length = content_length

    def get_content_type(self) -> str:
        return self._media_type

    def get(self, name: str) -> str | None:
        return self._content_length if name == "Content-Length" else None


class _FakeImageResponse:
    def __init__(
        self, media_type: str, body: bytes, content_length: str | None = None
    ) -> None:
        self.headers = _FakeHeaders(media_type, content_length)
        self._body = body

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def read(self, size: int) -> bytes:
        return self._body[:size]


class _FakeOpener:
    def __init__(self, response: _FakeImageResponse | Exception) -> None:
        self._response = response

    def open(self, request: object, timeout: float) -> _FakeImageResponse:
        if isinstance(self._response, Exception):
            raise self._response
        return self._response


def test_saved_visual_rejects_bad_content_before_base64_encoding(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = VisualEnrichmentService(user_agent="visual-test")
    trusted_url = "https://thumb.wikimedia.org/offline.jpg"

    monkeypatch.setattr(
        "grounded_travel_planner.visuals.service.build_opener",
        lambda handler: _FakeOpener(_FakeImageResponse("text/html", b"not an image")),
    )
    with pytest.raises(ValueError, match="media type"):
        service._download_saved_image(trusted_url)

    monkeypatch.setattr(
        "grounded_travel_planner.visuals.service.build_opener",
        lambda handler: _FakeOpener(_FakeImageResponse("image/jpeg", b"x" * 1_000_001)),
    )
    with pytest.raises(ValueError, match="too large"):
        service._download_saved_image(trusted_url)


def test_saved_visual_rejects_redirects(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = VisualEnrichmentService(user_agent="visual-test")
    redirect = HTTPError(
        "https://thumb.wikimedia.org/offline.jpg", 302, "Found", {}, None
    )
    monkeypatch.setattr(
        "grounded_travel_planner.visuals.service.build_opener",
        lambda handler: _FakeOpener(redirect),
    )

    with pytest.raises(HTTPError):
        service._download_saved_image("https://thumb.wikimedia.org/offline.jpg")
