"""Tests for deterministic source-quality evaluation."""

from __future__ import annotations

import json

import pytest

from grounded_travel_planner.evaluation.source_quality import (
    SourceQualityRow,
    SourceRelevance,
    evaluate_source_quality,
    load_source_quality_rows,
    normalize_host,
)


def _row(
    plan_id: str,
    place_name: str,
    url: str,
    relevance: SourceRelevance,
    source_class: str,
) -> SourceQualityRow:
    return SourceQualityRow(
        case_id=f"case-{place_name}",
        plan_id=plan_id,
        place_name=place_name,
        url=url,
        title=f"{place_name} title",
        snippet=f"{place_name} snippet",
        expected_relevance=relevance,
        expected_source_class=source_class,
    )


def test_evaluates_per_plan_coverage_precision_hosts_and_classes() -> None:
    report = evaluate_source_quality(
        [
            _row(
                "plan-b",
                "Citadel",
                "https://www.Example.com/citadel",
                SourceRelevance.RELEVANT,
                "official",
            ),
            _row(
                "plan-b",
                "Citadel",
                "https://example.com/video",
                SourceRelevance.WEAK,
                "video",
            ),
            _row(
                "plan-b",
                "Pagoda",
                "https://guide.example.org/pagoda",
                SourceRelevance.IRRELEVANT,
                "guide",
            ),
            _row(
                "plan-a",
                "Museum",
                "https://museum.example.net/visit",
                SourceRelevance.RELEVANT,
                "official",
            ),
        ]
    )

    plan_a, plan_b = report.plans
    assert plan_a.plan_id == "plan-a"
    assert plan_a.relevant_place_coverage == 1.0
    assert plan_b.citation_count == 3
    assert plan_b.relevant_place_coverage == 0.5
    assert plan_b.relevance_precision == pytest.approx(1 / 3)
    assert plan_b.irrelevant_citation_count == 1
    assert plan_b.distinct_normalized_hosts == ("example.com", "guide.example.org")
    assert plan_b.source_class_distribution == {
        "guide": 1,
        "official": 1,
        "video": 1,
    }


def test_loads_jsonl_and_reports_invalid_row_line(tmp_path) -> None:
    corpus = tmp_path / "source-quality.jsonl"
    corpus.write_text(
        json.dumps(
            {
                "case_id": "case-1",
                "plan_id": "plan-1",
                "place_name": "Citadel",
                "url": "https://www.example.com/citadel",
                "title": "Citadel",
                "snippet": "Opening information",
                "expected_relevance": "relevant",
                "expected_source_class": "official",
            }
        ),
        encoding="utf-8",
    )

    rows = load_source_quality_rows(corpus)

    assert rows[0].expected_relevance is SourceRelevance.RELEVANT
    assert normalize_host(rows[0].url) == "example.com"

    corpus.write_text('{"case_id": "missing-fields"}', encoding="utf-8")
    with pytest.raises(ValueError, match=r"source-quality.jsonl:1"):
        load_source_quality_rows(corpus)


def test_row_validation_rejects_invalid_relevance_and_url() -> None:
    data = {
        "case_id": "case-1",
        "plan_id": "plan-1",
        "place_name": "Citadel",
        "url": "https://example.com/citadel",
        "title": "Citadel",
        "snippet": "Opening information",
        "expected_relevance": "unsupported",
        "expected_source_class": "official",
    }
    with pytest.raises(ValueError, match="expected_relevance"):
        SourceQualityRow.from_mapping(data)

    data["expected_relevance"] = "relevant"
    data["url"] = "relative-url"
    with pytest.raises(ValueError, match="absolute HTTP"):
        SourceQualityRow.from_mapping(data)
