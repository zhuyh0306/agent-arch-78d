"""Validate the Day 13 metrics dictionary before it reaches prompts or SQL."""

from __future__ import annotations

from collections import Counter
from pathlib import Path

import yaml

DICTIONARY = Path(__file__).resolve().parents[1] / "metrics_dictionary.yaml"
REQUIRED = (
    "id",
    "name",
    "category",
    "definition",
    "formula",
    "unit",
    "grain",
    "time_window",
    "source",
    "pitfalls",
    "miscalculation_risk",
)
RISKS = {"high", "medium", "low"}


def main() -> int:
    data = yaml.safe_load(DICTIONARY.read_text(encoding="utf-8"))
    metrics = data.get("metrics") or []
    errors: list[str] = []

    if len(metrics) != 20:
        errors.append(f"expected 20 metrics, got {len(metrics)}")

    ids = [metric.get("id") for metric in metrics]
    duplicates = [metric_id for metric_id, count in Counter(ids).items() if count > 1]
    if duplicates:
        errors.append(f"duplicate ids: {duplicates}")

    for metric in metrics:
        metric_id = metric.get("id", "<missing-id>")
        missing = [key for key in REQUIRED if not metric.get(key)]
        if missing:
            errors.append(f"{metric_id}: missing {missing}")
            continue
        if not isinstance(metric["pitfalls"], list) or not metric["pitfalls"]:
            errors.append(f"{metric_id}: pitfalls must be a non-empty list")
        if metric["miscalculation_risk"] not in RISKS:
            errors.append(f"{metric_id}: bad risk {metric['miscalculation_risk']}")

    high_risk = [metric["id"] for metric in metrics if metric.get("miscalculation_risk") == "high"]
    if len(high_risk) != 3:
        errors.append(f"expected exactly 3 high-risk metrics, got {len(high_risk)}: {high_risk}")

    categories = Counter(metric.get("category", "?") for metric in metrics)
    print(f"metrics: {len(metrics)}")
    print(f"categories: {dict(sorted(categories.items()))}")
    print(f"high-risk: {high_risk}")
    print(f"source_status: {data.get('source_status')}")

    for error in errors:
        print(f"FAIL {error}")
    if errors:
        return 1
    print("metrics dictionary ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())