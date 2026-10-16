# Offline Source Quality Baseline — 2026-10-15

Status: Evaluator and synthetic corpus verified; no live-source quality claim.

## Method

`data/eval/source-quality-v1.jsonl` contains 16 manually labelled, synthetic
source-to-place assertions across five example plans. Run:

```powershell
uv run python scripts/evaluate_source_quality.py
```

The script makes no model or search calls. Relevance precision is the share of
citations labelled `relevant` among all citations. Relevant-place coverage is
the share of distinct places with at least one `relevant` citation. Host counts
strip a leading `www.` but do not establish source independence or authority.
The labels are corpus inputs, not predictions made by the application.

## Recorded output

| Plan | Relevant-place coverage | Citation precision | Irrelevant citations | Distinct hosts |
|---|---:|---:|---:|---:|
| bergen-waterfront-3 | 2/3 | 2/4 | 1 | 4 |
| hue-heritage-3 | 3/3 | 3/3 | 0 | 3 |
| kyoto-temple-1 | 1/1 | 1/3 | 1 | 3 |
| lisbon-viewpoints-2 | 2/2 | 2/3 | 0 | 3 |
| rome-classics-2 | 1/2 | 1/3 | 1 | 3 |

Corpus totals: nine `relevant`, four `weak` and three `irrelevant` citations;
overall labelled relevance precision is 9/16 (56.25%). These values describe
the deliberately mixed synthetic corpus, not the app's live recommendations.

## Decision and next measurement

Keep source provenance as the runtime commit rule. Before a broad demo, label
citations from a representative set of live plans and report the same metrics.
The proposed demo criterion is at least one relevant citation per recommended
place and zero irrelevant citations; report host diversity separately, with
two hosts as a review target for plans containing at least two places. A plan
with one place is not scored against that diversity target. Editorial quality
does not yet block a runtime plan commit.
