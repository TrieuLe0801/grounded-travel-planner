"""Tavily search adapter."""

import os
import re
from urllib.parse import urlparse

from grounded_travel_planner.contracts import SearchResult
from grounded_travel_planner.providers import PlaceSearchProvider, ProviderError
from utils.ids import new_id
from utils.redaction import sanitize_error

_HOURS_MARKER = re.compile(
    r"\b(?:open(?:ing)? hours?|hours?|closed)\b",
    re.IGNORECASE,
)
_TIME_MARKER = re.compile(
    r"\b(?:[01]?\d|2[0-3]):[0-5]\d\b|\b\d{1,2}\s?(?:am|pm)\b",
    re.IGNORECASE,
)


class TavilyPlaceSearchProvider(PlaceSearchProvider):
    """Normalize Tavily results and keep only actual http(s) source URLs."""

    def __init__(self, api_key: str | None = None) -> None:
        self._api_key = api_key

    def search_places(
        self,
        query: str,
        *,
        max_results: int,
        thread_id: str,
    ) -> list[SearchResult]:
        api_key = self._api_key or os.getenv("TAVILY_API_KEY")
        if not api_key:
            raise ProviderError("Tavily is not configured")
        try:
            from tavily import TavilyClient

            client = TavilyClient(api_key=api_key)
            response = client.search(
                query=query[:400],
                max_results=max_results,
                search_depth="advanced",
                include_answer=False,
                include_raw_content=False,
            )
        except Exception as error:  # noqa: BLE001 - sanitize provider boundary
            raise ProviderError(
                f"Tavily search failed: {sanitize_error(error)}"
            ) from None
        raw_results = response.get("results", []) if isinstance(response, dict) else []
        results: list[SearchResult] = []
        seen_urls: set[str] = set()
        for item in raw_results:
            if not isinstance(item, dict):
                continue
            url = str(item.get("url") or "").strip()
            parsed = urlparse(url)
            if parsed.scheme not in {"http", "https"} or not parsed.netloc:
                continue
            canonical_url = url.rstrip("/")
            if canonical_url in seen_urls:
                continue
            seen_urls.add(canonical_url)
            content = str(item.get("content") or item.get("snippet") or "").strip()
            supports_hours = bool(
                _HOURS_MARKER.search(content) and _TIME_MARKER.search(content)
            )
            try:
                results.append(
                    SearchResult(
                        source_id=new_id("source"),
                        title=str(item.get("title") or parsed.netloc)[:240],
                        url=canonical_url,
                        snippet=content[:1000] or None,
                        score=item.get("score"),
                        supports_opening_hours=supports_hours,
                    )
                )
            except (TypeError, ValueError):
                continue
        return results
