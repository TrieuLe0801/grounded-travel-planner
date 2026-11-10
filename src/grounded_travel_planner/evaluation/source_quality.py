"""Offline metrics for labelled itinerary source citations.

The evaluator deliberately consumes recorded labels only.  It makes no provider
calls and does not decide whether a source is relevant at runtime.
"""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from urllib.parse import urlsplit


class SourceRelevance(str, Enum):
    """Human-assigned relevance labels for an individual citation."""

    RELEVANT = "relevant"
    WEAK = "weak"
    IRRELEVANT = "irrelevant"


@dataclass(frozen=True)
class SourceQualityRow:
    """One labelled citation from an offline source-quality corpus."""

    case_id: str
    plan_id: str
    place_name: str
    url: str
    title: str
    snippet: str
    expected_relevance: SourceRelevance
    expected_source_class: str

    @classmethod
    def from_mapping(cls, value: Mapping[str, object]) -> SourceQualityRow:
        """Build and validate a corpus row loaded from JSONL."""

        required = (
            "case_id",
            "plan_id",
            "place_name",
            "url",
            "title",
            "snippet",
            "expected_relevance",
            "expected_source_class",
        )
        missing = [field for field in required if field not in value]
        if missing:
            raise ValueError(
                f"Source-quality row is missing fields: {', '.join(missing)}"
            )

        strings: dict[str, str] = {}
        for field in required:
            item = value[field]
            if not isinstance(item, str) or not item.strip():
                raise ValueError(
                    f"Source-quality row field {field!r} must be a non-empty string"
                )
            strings[field] = item.strip()

        parsed_url = urlsplit(strings["url"])
        if parsed_url.scheme not in {"http", "https"} or not parsed_url.hostname:
            raise ValueError("Source-quality row url must be an absolute HTTP(S) URL")

        try:
            relevance = SourceRelevance(strings["expected_relevance"].casefold())
        except ValueError as error:
            allowed = ", ".join(label.value for label in SourceRelevance)
            raise ValueError(f"expected_relevance must be one of: {allowed}") from error

        return cls(
            case_id=strings["case_id"],
            plan_id=strings["plan_id"],
            place_name=strings["place_name"],
            url=strings["url"],
            title=strings["title"],
            snippet=strings["snippet"],
            expected_relevance=relevance,
            expected_source_class=strings["expected_source_class"],
        )


@dataclass(frozen=True)
class SourceQualityMetrics:
    """Source metrics for one labelled plan.

    Coverage counts a place as covered when it has at least one ``relevant``
    citation. Precision is ``relevant citations / all citations``; ``weak``
    citations are retained in the denominator but do not count as relevant.
    """

    plan_id: str
    citation_count: int
    relevant_place_coverage: float
    irrelevant_citation_count: int
    distinct_normalized_hosts: tuple[str, ...]
    source_class_distribution: Mapping[str, int]
    relevance_precision: float


@dataclass(frozen=True)
class SourceQualityReport:
    """Deterministic result for a complete labelled corpus."""

    plans: tuple[SourceQualityMetrics, ...]


def normalize_host(url: str) -> str:
    """Return a lower-case hostname with one leading ``www.`` removed."""

    hostname = urlsplit(url).hostname
    if hostname is None:
        raise ValueError("URL has no hostname")
    normalized = hostname.casefold()
    return normalized.removeprefix("www.")


def load_source_quality_rows(path: Path) -> list[SourceQualityRow]:
    """Load a JSONL source-quality corpus with line-specific errors."""

    rows: list[SourceQualityRow] = []
    for line_number, raw_line in enumerate(
        path.read_text(encoding="utf-8").splitlines(), 1
    ):
        if not raw_line.strip():
            continue
        try:
            value = json.loads(raw_line)
        except json.JSONDecodeError as error:
            raise ValueError(f"Invalid JSON at {path}:{line_number}") from error
        if not isinstance(value, dict):
            raise TypeError(f"Expected an object at {path}:{line_number}")
        try:
            rows.append(SourceQualityRow.from_mapping(value))
        except ValueError as error:
            raise ValueError(
                f"Invalid source-quality row at {path}:{line_number}: {error}"
            ) from error
    return rows


def evaluate_source_quality(rows: Iterable[SourceQualityRow]) -> SourceQualityReport:
    """Measure labelled citation quality, grouped by plan in stable ID order."""

    rows_by_plan: dict[str, list[SourceQualityRow]] = defaultdict(list)
    for row in rows:
        rows_by_plan[row.plan_id].append(row)

    metrics: list[SourceQualityMetrics] = []
    for plan_id in sorted(rows_by_plan):
        plan_rows = rows_by_plan[plan_id]
        normalized_places = {_normalize_place(row.place_name) for row in plan_rows}
        relevant_places = {
            _normalize_place(row.place_name)
            for row in plan_rows
            if row.expected_relevance is SourceRelevance.RELEVANT
        }
        relevant_count = sum(
            row.expected_relevance is SourceRelevance.RELEVANT for row in plan_rows
        )
        classes = Counter(row.expected_source_class for row in plan_rows)
        metrics.append(
            SourceQualityMetrics(
                plan_id=plan_id,
                citation_count=len(plan_rows),
                relevant_place_coverage=len(relevant_places) / len(normalized_places),
                irrelevant_citation_count=sum(
                    row.expected_relevance is SourceRelevance.IRRELEVANT
                    for row in plan_rows
                ),
                distinct_normalized_hosts=tuple(
                    sorted({normalize_host(row.url) for row in plan_rows})
                ),
                source_class_distribution=dict(sorted(classes.items())),
                relevance_precision=relevant_count / len(plan_rows),
            )
        )
    return SourceQualityReport(plans=tuple(metrics))


def _normalize_place(place_name: str) -> str:
    return " ".join(place_name.casefold().split())
