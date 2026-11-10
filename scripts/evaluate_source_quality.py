"""Report offline source-quality labels; never make live provider calls."""

from __future__ import annotations

import json
from collections import Counter
from dataclasses import asdict
from pathlib import Path

from grounded_travel_planner.evaluation.source_quality import (
    SourceRelevance,
    evaluate_source_quality,
    load_source_quality_rows,
)

CORPUS = (
    Path(__file__).resolve().parents[1] / "data" / "eval" / "source-quality-v1.jsonl"
)


def main() -> int:
    rows = load_source_quality_rows(CORPUS)
    report = evaluate_source_quality(rows)
    counts = Counter(row.expected_relevance for row in rows)
    result = {
        "corpus": CORPUS.name,
        "citation_count": len(rows),
        "plan_count": len(report.plans),
        "relevance_counts": {label.value: counts[label] for label in SourceRelevance},
        "plans": [asdict(plan) for plan in report.plans],
    }
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
