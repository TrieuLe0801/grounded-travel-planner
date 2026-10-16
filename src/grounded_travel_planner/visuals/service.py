"""Bounded public lookups for visual itinerary presentation.

These lookups deliberately sit outside the planning graph.  Their results are
optional presentation data and are never evidence for a plan change.
"""

from __future__ import annotations

import json
import os
import threading
import time
import unicodedata
from dataclasses import dataclass
from html import unescape
from html.parser import HTMLParser
from typing import Any, ClassVar
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from grounded_travel_planner.contracts import SightseeingPlan, visible_schedule_entries

_COMMONS_API = "https://commons.wikimedia.org/w/api.php"
_WIKIPEDIA_API = "https://{language}.wikipedia.org/w/api.php"
_NOMINATIM_API = "https://nominatim.openstreetmap.org/search"
_MAX_STOPS = 12
_NOMINATIM_LOCK = threading.Lock()
_LAST_NOMINATIM_REQUEST = 0.0
_PLACE_TYPE_TOKENS = {
    "beach",
    "cathedral",
    "church",
    "citadel",
    "city",
    "district",
    "island",
    "lake",
    "market",
    "monument",
    "museum",
    "pagoda",
    "palace",
    "park",
    "temple",
    "village",
}


class _TextExtractor(HTMLParser):
    """Convert Commons' HTML metadata into a safe, readable credit string."""

    def __init__(self) -> None:
        super().__init__()
        self._parts: list[str] = []

    def handle_data(self, data: str) -> None:
        self._parts.append(data)

    def text(self) -> str:
        return " ".join(" ".join(self._parts).split())


@dataclass(frozen=True)
class PlaceVisual:
    """Source-backed image and coordinate data for one itinerary stop."""

    place_name: str
    latitude: float | None = None
    longitude: float | None = None
    coordinate_source_url: str | None = None
    coordinate_source_label: str | None = None
    image_url: str | None = None
    image_page_url: str | None = None
    image_credit: str | None = None
    image_license: str | None = None
    image_alt: str | None = None

    @property
    def has_coordinates(self) -> bool:
        return self.latitude is not None and self.longitude is not None


class VisualEnrichmentService:
    """Fetch and cache optional public metadata with conservative matching."""

    _cache: ClassVar[dict[tuple[str, str], PlaceVisual | None]] = {}
    _cache_lock: ClassVar[threading.Lock] = threading.Lock()

    def __init__(self, *, user_agent: str, timeout_seconds: float = 4.0) -> None:
        self._user_agent = user_agent
        self._timeout_seconds = timeout_seconds

    @classmethod
    def from_environment(cls) -> VisualEnrichmentService:
        """Build an HTTP client without exposing credentials or session state."""

        user_agent = os.getenv(
            "VISUAL_ENRICHMENT_USER_AGENT",
            "GroundedTravelPlanner/0.0 (visual enrichment; contact=local)",
        )
        try:
            timeout = float(os.getenv("VISUAL_ENRICHMENT_TIMEOUT_SECONDS", "4"))
        except ValueError:
            timeout = 4.0
        return cls(user_agent=user_agent, timeout_seconds=max(1.0, min(timeout, 10.0)))

    def resolve(self, plan: SightseeingPlan) -> dict[str, PlaceVisual]:
        """Return available presentation metadata keyed by schedule entry id.

        A failed public endpoint or one bad place is intentionally invisible to
        the planning runtime: callers receive an empty/partial mapping.
        """

        visuals: dict[str, PlaceVisual] = {}
        for entry in visible_schedule_entries(plan)[:_MAX_STOPS]:
            try:
                visual = self._resolve_place(entry.place.name, plan.destination)
            except (OSError, ValueError, json.JSONDecodeError):
                continue
            if visual is not None:
                visuals[entry.id] = visual
        return visuals

    def _resolve_place(self, place_name: str, destination: str) -> PlaceVisual | None:
        cache_key = (self._normalise(place_name), self._normalise(destination))
        with self._cache_lock:
            if cache_key in self._cache:
                return self._cache[cache_key]

        image = self._commons_image(place_name)
        coordinates = self._wikipedia_coordinates(place_name)
        if coordinates is None:
            coordinates = self._nominatim_coordinates(place_name, destination)
        if image is None and coordinates is None:
            with self._cache_lock:
                self._cache[cache_key] = None
            return None

        visual = PlaceVisual(
            place_name=place_name,
            latitude=coordinates[0] if coordinates else None,
            longitude=coordinates[1] if coordinates else None,
            coordinate_source_url=coordinates[2] if coordinates else None,
            coordinate_source_label=coordinates[3] if coordinates else None,
            image_url=image[0] if image else None,
            image_page_url=image[1] if image else None,
            image_credit=image[2] if image else None,
            image_license=image[3] if image else None,
            image_alt=image[4] if image else None,
        )
        with self._cache_lock:
            self._cache[cache_key] = visual
        return visual

    def _commons_image(self, place_name: str) -> tuple[str, str, str, str, str] | None:
        search = self._get_json(
            _COMMONS_API,
            {
                "action": "query",
                "list": "search",
                "srnamespace": "6",
                "srlimit": "5",
                "srsearch": place_name,
                "format": "json",
                "formatversion": "2",
            },
        )
        candidates = search.get("query", {}).get("search", [])
        title = next(
            (
                item.get("title")
                for item in candidates
                if isinstance(item, dict)
                and isinstance(item.get("title"), str)
                and self._name_matches(place_name, item["title"].removeprefix("File:"))
            ),
            None,
        )
        if title is None:
            return None
        details = self._get_json(
            _COMMONS_API,
            {
                "action": "query",
                "titles": title,
                "prop": "imageinfo",
                "iiprop": "url|extmetadata",
                "iiurlwidth": "960",
                "format": "json",
                "formatversion": "2",
            },
        )
        pages = details.get("query", {}).get("pages", [])
        if not isinstance(pages, list) or not pages:
            return None
        info = pages[0].get("imageinfo", [{}])[0]
        if not isinstance(info, dict):
            return None
        metadata = info.get("extmetadata", {})
        if not isinstance(metadata, dict):
            return None
        image_url = info.get("thumburl")
        page_url = info.get("descriptionurl")
        credit = self._metadata_value(metadata, "Artist") or self._metadata_value(
            metadata, "Credit"
        )
        license_name = self._metadata_value(metadata, "LicenseShortName")
        if (
            not all(
                isinstance(value, str) and value.startswith("https://")
                for value in (image_url, page_url)
            )
            or not credit
            or not license_name
        ):
            return None
        return image_url, page_url, credit, license_name, place_name

    def _wikipedia_coordinates(
        self, place_name: str
    ) -> tuple[float, float, str, str] | None:
        for language in ("vi", "en"):
            response = self._get_json(
                _WIKIPEDIA_API.format(language=language),
                {
                    "action": "query",
                    "list": "search",
                    "srsearch": place_name,
                    "srlimit": "5",
                    "format": "json",
                    "formatversion": "2",
                },
            )
            result = next(
                (
                    item
                    for item in response.get("query", {}).get("search", [])
                    if isinstance(item, dict)
                    and isinstance(item.get("title"), str)
                    and self._name_matches(place_name, item["title"])
                ),
                None,
            )
            if result is None:
                continue
            title = result["title"]
            page = self._get_json(
                _WIKIPEDIA_API.format(language=language),
                {
                    "action": "query",
                    "titles": title,
                    "prop": "coordinates",
                    "format": "json",
                    "formatversion": "2",
                },
            )
            pages = page.get("query", {}).get("pages", [])
            if not isinstance(pages, list) or not pages:
                continue
            coordinates = pages[0].get("coordinates", [])
            if not isinstance(coordinates, list) or not coordinates:
                continue
            coordinate = coordinates[0]
            latitude, longitude = coordinate.get("lat"), coordinate.get("lon")
            if self._valid_coordinate(latitude, longitude):
                url = "https://{language}.wikipedia.org/wiki/{title}".format(
                    language=language, title=title.replace(" ", "_")
                )
                return float(latitude), float(longitude), url, f"Wikipedia ({language})"
        return None

    def _nominatim_coordinates(
        self, place_name: str, destination: str
    ) -> tuple[float, float, str, str] | None:
        global _LAST_NOMINATIM_REQUEST
        with _NOMINATIM_LOCK:
            wait = 1.0 - (time.monotonic() - _LAST_NOMINATIM_REQUEST)
            if wait > 0:
                time.sleep(wait)
            try:
                response = self._get_json(
                    _NOMINATIM_API,
                    {
                        "q": f"{place_name}, {destination}",
                        "format": "jsonv2",
                        "limit": "3",
                    },
                )
            finally:
                # Count a failed attempt too: it may already have reached OSMF.
                _LAST_NOMINATIM_REQUEST = time.monotonic()
        if not isinstance(response, list) or not response:
            return None
        matching_results = [
            result
            for result in response
            if isinstance(result, dict)
            and self._name_matches(
                place_name, str(result.get("display_name", "")).split(",", 1)[0]
            )
            and self._valid_coordinate(result.get("lat"), result.get("lon"))
        ]
        if not matching_results:
            return None
        result = matching_results[0]
        latitude, longitude = result["lat"], result["lon"]
        if any(
            abs(float(latitude) - float(other["lat"])) > 0.1
            or abs(float(longitude) - float(other["lon"])) > 0.1
            for other in matching_results[1:]
        ):
            return None
        osm_type = result.get("osm_type")
        osm_id = result.get("osm_id")
        if osm_type not in {"node", "way", "relation"} or not isinstance(
            osm_id, (int, str)
        ):
            return None
        return (
            float(latitude),
            float(longitude),
            f"https://www.openstreetmap.org/{osm_type}/{osm_id}",
            "OpenStreetMap / Nominatim",
        )

    def _get_json(self, endpoint: str, parameters: dict[str, str]) -> Any:
        request = Request(
            f"{endpoint}?{urlencode(parameters)}",
            headers={"Accept": "application/json", "User-Agent": self._user_agent},
        )
        with urlopen(request, timeout=self._timeout_seconds) as response:  # nosec B310
            return json.loads(response.read().decode("utf-8"))

    @staticmethod
    def _metadata_value(metadata: dict[str, Any], key: str) -> str | None:
        value = metadata.get(key)
        if isinstance(value, dict) and isinstance(value.get("value"), str):
            parser = _TextExtractor()
            parser.feed(unescape(value["value"]))
            return parser.text() or None
        return None

    @staticmethod
    def _normalise(value: str) -> str:
        decomposed = unicodedata.normalize("NFKD", value.casefold()).replace("đ", "d")
        return " ".join(
            "".join(
                character if character.isalnum() else " "
                for character in decomposed
                if not unicodedata.combining(character)
            ).split()
        )

    @classmethod
    def _name_matches(cls, requested: str, candidate: str) -> bool:
        requested_tokens = set(cls._normalise(requested).split())
        candidate_tokens = set(cls._normalise(candidate).split())
        requested_core = requested_tokens - _PLACE_TYPE_TOKENS
        candidate_core = candidate_tokens - _PLACE_TYPE_TOKENS
        return bool(requested_core) and requested_core == candidate_core

    @staticmethod
    def _valid_coordinate(latitude: Any, longitude: Any) -> bool:
        try:
            return -90 <= float(latitude) <= 90 and -180 <= float(longitude) <= 180
        except (TypeError, ValueError):
            return False
