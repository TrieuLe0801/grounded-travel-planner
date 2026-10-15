"""Provider protocols for model, search and tracing integrations."""

from collections.abc import Mapping
from typing import Any, Protocol, TypeVar

from pydantic import BaseModel

from grounded_travel_planner.contracts import SearchResult

T = TypeVar("T", bound=BaseModel)


class ProviderError(RuntimeError):
    """Sanitized provider-boundary failure safe for application handling."""


class StructuredChatModel(Protocol):
    @property
    def model_name(self) -> str:
        """Return the exact configured model identifier."""

    def generate_structured(
        self,
        prompt: str,
        schema: type[T],
        *,
        metadata: Mapping[str, str] | None = None,
    ) -> T:
        """Return model output parsed as the requested Pydantic schema."""


class PlaceSearchProvider(Protocol):
    def search_places(
        self,
        query: str,
        *,
        max_results: int,
        thread_id: str,
    ) -> list[SearchResult]:
        """Search for places and return normalized source URLs only."""


class TraceSink(Protocol):
    def record_event(
        self,
        name: str,
        payload: Mapping[str, Any],
        *,
        thread_id: str,
    ) -> None:
        """Record a redacted observability event keyed by thread_id."""
