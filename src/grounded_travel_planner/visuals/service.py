"""Bounded public lookups for visual itinerary presentation.

These lookups deliberately sit outside the planning graph.  Their results are
optional presentation data and are never evidence for a plan change.
"""

from __future__ import annotations

import json
import logging
import os
import threading
import unicodedata
from dataclasses import dataclass
from html import unescape
from html.parser import HTMLParser
from typing import Any, ClassVar
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from grounded_travel_planner.contracts import SightseeingPlan, visible_schedule_entries

_COMMONS_API = "https://commons.wikimedia.org/w/api.php"
_LOG = logging.getLogger(__name__)
MAX_VISUAL_STOPS = 12
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
    """Source-backed image data for one itinerary stop."""

    place_name: str
    image_url: str | None = None
    image_page_url: str | None = None
    image_credit: str | None = None
    image_license: str | None = None
    image_alt: str | None = None


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
            "GroundedTravelPlanner/0.1 "
            "(+https://github.com/TrieuLe0801/grounded-travel-planner)",
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
        for entry in visible_schedule_entries(plan)[:MAX_VISUAL_STOPS]:
            try:
                visual = self._resolve_place(entry.place.name, plan.destination)
            except Exception as error:  # noqa: BLE001 - visual data cannot block plan
                _LOG.debug("Visual lookup skipped after %s", type(error).__name__)
                continue
            if visual is not None:
                visuals[entry.id] = visual
        return visuals

    def _resolve_place(self, place_name: str, destination: str) -> PlaceVisual | None:
        cache_key = (self._normalise(place_name), self._normalise(destination))
        with self._cache_lock:
            if cache_key in self._cache:
                return self._cache[cache_key]

        try:
            image = self._commons_image(place_name)
        except (OSError, ValueError, TypeError, json.JSONDecodeError):
            image = None
        if image is None:
            with self._cache_lock:
                self._cache[cache_key] = None
            return None

        visual = PlaceVisual(
            place_name=place_name,
            image_url=image[0],
            image_page_url=image[1],
            image_credit=image[2],
            image_license=image[3],
            image_alt=image[4],
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
        image_alt = title.removeprefix("File:").rsplit(".", 1)[0].replace("_", " ")
        return image_url, page_url, credit, license_name, image_alt[:160]

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
    def _name_matches(
        cls,
        requested: str,
        candidate: str,
    ) -> bool:
        requested_all = cls._normalise(requested).split()
        candidate_all = cls._normalise(candidate).split()
        requested_core = [
            token for token in requested_all if token not in _PLACE_TYPE_TOKENS
        ]
        if not requested_core:
            return False
        phrase = requested_core if len(requested_core) >= 2 else requested_all
        return any(
            candidate_all[index : index + len(phrase)] == phrase
            for index in range(len(candidate_all) - len(phrase) + 1)
        )
