#!/usr/bin/env python3
"""Prove the five contracts accept a legal payload and reject the illegal ones.

Two layers, run in order and never conflated:

  schema   -- Draft 2020-12 validation (shape, enums, value domains)
  rules    -- contract_rules.check_cross_field (relations no keyword can say)

A case passes when the combined verdict equals its expectation. Expectations
are written as ``new_expected`` so a regression shows up as a named code, not a
bare ``False``.
"""

from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

from jsonschema import Draft202012Validator
from referencing import Registry, Resource

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "python"))

from contract_rules import check_cross_field  # noqa: E402

SPECS = ROOT / "specs"
TASKS = ("compare", "attribution", "trend", "anomaly", "forecast")


def registry() -> Registry:
    resources = []
    for path in SPECS.glob("*.schema.json"):
        doc = json.loads(path.read_text(encoding="utf-8"))
        resources.append((doc["$id"], Resource.from_contents(doc)))
    return Registry().with_resources(resources)


REGISTRY = registry()
VALIDATORS = {
    task: Draft202012Validator(json.loads((SPECS / f"{task}.schema.json").read_text(encoding="utf-8")), registry=REGISTRY)
    for task in TASKS
}


def verdict(task: str, payload: dict) -> tuple[str, str]:
    """Return (code, message). code is 'PASS' when the payload is fully legal."""
    schema_errors = sorted(VALIDATORS[task].iter_errors(payload), key=lambda e: list(e.path))
    if schema_errors:
        first = schema_errors[0]
        where = "/".join(str(p) for p in first.path) or "<root>"
        return "SCHEMA_REJECT", f"{where}: {first.validator} -> {first.message[:120]}"
    violations = check_cross_field(task, payload)
    if violations:
        return violations[0].failure_code, f"{violations[0].rule}: {violations[0].detail}"
    return "PASS", "ok"


# ---------------------------------------------------------------- fixtures

GC_SOURCE = "orders.gross_amount, orders.shipping_fee, orders.tax_amount"


def base_compare() -> dict:
    return {
        "contract_version": "1",
        "task_type": "compare",
        "metric": "gmv",
        "unit": "CNY",
        "window": {"start": "2026-11-01", "end": "2026-11-08", "timezone": "Asia/Shanghai"},
        "left": {"label": "渠道A", "value": 128000.0, "dimensions": [{"field": "channel", "value": "A"}]},
        "right": {"label": "渠道B", "value": 112000.0, "dimensions": [{"field": "channel", "value": "B"}]},
        "delta": {"absolute": 16000.0, "relative": 16000.0 / 112000.0},
        "direction": "up",
        "verdict": "渠道A比渠道B高16000元，主要来自客单价。",
        "evidence": [{"source": GC_SOURCE, "value": 128000.0, "unit": "CNY"}],
        "constraints": {"left_right_not_equal": True, "max_dimensions": 5},
    }


def base_attribution() -> dict:
    return {
        "contract_version": "1",
        "task_type": "attribution",
        "metric": "gmv",
        "unit": "CNY",
        "window": {"start": "2026-11-01", "end": "2026-11-08", "timezone": "Asia/Shanghai"},
        "baseline_window": {"start": "2026-10-25", "end": "2026-11-01", "timezone": "Asia/Shanghai"},
        "total_change": -20000.0,
        "contributors": [
            {"dimension": "channel", "value": "A", "contribution": -15000.0, "share": 0.75, "evidence": [{"source": "orders.status"}]},
            {"dimension": "province", "value": "广东", "contribution": -4000.0, "share": 0.2, "evidence": [{"source": "orders.status"}]},
            {"dimension": "other", "value": "其他", "contribution": -1000.0, "share": 0.05, "evidence": [{"source": "orders.status"}]},
        ],
        "residual": 0.0,
        "method": "shapley",
        "verdict": "GMV下降2万元，75%来自渠道A。",
        "evidence": [{"source": GC_SOURCE}],
        "constraints": {"closure_tolerance": 0.01, "max_contributors": 8, "contribution_sorted_desc": True},
    }


def base_trend() -> dict:
    pts = [
        {"period": "2026-11-01", "value": 1000.0, "is_complete": True},
        {"period": "2026-11-02", "value": 1100.0, "is_complete": True},
        {"period": "2026-11-03", "value": 1200.0, "is_complete": True},
        {"period": "2026-11-04", "value": 900.0, "is_complete": False},
    ]
    return {
        "contract_version": "1",
        "task_type": "trend",
        "metric": "gmv",
        "unit": "CNY",
        "window": {"start": "2026-11-01", "end": "2026-11-05", "timezone": "Asia/Shanghai"},
        "granularity": "day",
        "points": pts,
        "direction": "up",
        "period_change": {"absolute": 200.0, "relative": 0.2},
        "fit": {"method": "ols", "r2": 0.91},
        "change_points": [],
        "verdict": "完整日三天里GMV持续上行，11-04尚未结束不计入。",
        "evidence": [{"source": GC_SOURCE}],
        "constraints": {"min_points": 3, "week_start": "monday", "exclude_incomplete_period": True, "max_points": 400},
    }


def base_anomaly() -> dict:
    return {
        "contract_version": "1",
        "task_type": "anomaly",
        "metric": "gmv",
        "unit": "CNY",
        "window": {"start": "2026-11-01", "end": "2026-11-08", "timezone": "Asia/Shanghai"},
        "granularity": "day",
        "baseline": {"kind": "trailing_mean", "lookback_days": 28},
        "method": {"kind": "zscore", "threshold": 3.0},
        "anomalies": [
            {
                "period": "2026-11-05",
                "value": 40000.0,
                "baseline_value": 62000.0,
                "deviation": -22000.0,
                "score": -3.6,
                "severity": "high",
                "evidence": [{"source": GC_SOURCE}],
            }
        ],
        "conclusion": "anomaly_found",
        "verdict": "11-05 GMV 低于基线3.6个标准差。",
        "evidence": [{"source": GC_SOURCE}],
        "constraints": {"min_baseline_points": 28, "baseline_excludes_window": True, "threshold_from_baseline": True, "max_anomalies": 20},
    }


def base_forecast() -> dict:
    return {
        "contract_version": "1",
        "task_type": "forecast",
        "metric": "gmv",
        "unit": "CNY",
        "history_window": {"start": "2026-10-01", "end": "2026-11-01", "timezone": "Asia/Shanghai"},
        "horizon": {"start": "2026-11-01", "end": "2026-11-04", "granularity": "day"},
        "method": {"kind": "holt_winters", "params": {"season_length": 7}},
        "backtest": {"holdout_periods": 7, "mape": 0.08, "mae": 4200.0},
        "points": [
            {"period": "2026-11-01", "value": 100000.0, "low": 90000.0, "high": 110000.0},
            {"period": "2026-11-02", "value": 104000.0, "low": 93000.0, "high": 115000.0},
        ],
        "interval_level": 0.8,
        "assumptions": ["无大促活动", "供给与库存稳定"],
        "verdict": "未来两天GMV预计在9万到11.5万之间。",
        "evidence": [{"source": GC_SOURCE}],
        "constraints": {
            "max_horizon_periods": 60,
            "min_history_periods": 14,
            "interval_required": True,
            "backtest_required": True,
            "max_backtest_mape": 0.3,
        },
    }


BASE = {
    "compare": base_compare,
    "attribution": base_attribution,
    "trend": base_trend,
    "anomaly": base_anomaly,
    "forecast": base_forecast,
}


def mutate(task: str, fn) -> dict:
    payload = copy.deepcopy(BASE[task]())
    fn(payload)
    return payload


def cases() -> list[tuple[str, str, dict, str]]:
    """(task, case_id, payload, expected_code)."""
    out: list[tuple[str, str, dict, str]] = []
    for task, make in BASE.items():
        out.append((task, "legal", make(), "PASS"))

    # --- shape layer: these must be caught by JSON Schema, not by rules
    out.append(("compare", "unknown_metric_field", mutate("compare", lambda p: p.update(extra="x")), "SCHEMA_REJECT"))
    out.append(("compare", "bad_direction", mutate("compare", lambda p: p.update(direction="sideways")), "SCHEMA_REJECT"))
    out.append(("compare", "missing_verdict", mutate("compare", lambda p: p.pop("verdict")), "SCHEMA_REJECT"))
    out.append(("compare", "bad_timezone", mutate("compare", lambda p: p["window"].update(timezone="UTC")), "SCHEMA_REJECT"))
    out.append(("trend", "too_few_points", mutate("trend", lambda p: p.update(points=p["points"][:2])), "SCHEMA_REJECT"))
    out.append(("anomaly", "bogus_conclusion", mutate("anomaly", lambda p: p.update(conclusion="maybe")), "SCHEMA_REJECT"))
    out.append(("forecast", "bad_interval_level", mutate("forecast", lambda p: p.update(interval_level=1.5)), "SCHEMA_REJECT"))

    # --- rules layer: shape is fine, relations are not
    out.append(("compare", "self_compare", mutate("compare", lambda p: p["right"].update(label="渠道A")), "CONSTRAINT_VIOLATION"))
    out.append(("compare", "delta_mismatch", mutate("compare", lambda p: p["delta"].update(absolute=999.0)), "CONSTRAINT_VIOLATION"))
    out.append(("compare", "relative_on_zero_base", mutate("compare", lambda p: (p["right"].update(value=0.0), p["delta"].update(absolute=128000.0, relative=0.0), p.update(direction="up"))), "CONSTRAINT_VIOLATION"))
    out.append(
        ("compare", "direction_wrong", mutate("compare", lambda p: p.update(direction="down")), "CONSTRAINT_VIOLATION")
    )

    out.append(("attribution", "residual_open", mutate("attribution", lambda p: p.update(residual=0.0, total_change=-21000.0)), "CONSTRAINT_VIOLATION"))
    out.append(("attribution", "unsorted", mutate("attribution", lambda p: p["contributors"].reverse()), "CONSTRAINT_VIOLATION"))
    out.append(
        (
            "attribution",
            "baseline_after_window",
            mutate("attribution", lambda p: p.update(baseline_window={"start": "2026-11-02", "end": "2026-11-09", "timezone": "Asia/Shanghai"})),
            "WINDOW_INVALID",
        )
    )

    out.append(("trend", "changepoint_on_incomplete", mutate("trend", lambda p: p["change_points"].append({"period": "2026-11-04", "kind": "level_shift", "evidence": [{"source": "orders.paid_at"}]})), "CONSTRAINT_VIOLATION"))
    out.append(("trend", "period_change_wrong", mutate("trend", lambda p: p["period_change"].update(absolute=-100.0, relative=-0.1)), "CONSTRAINT_VIOLATION"))
    out.append(("trend", "unsorted_points", mutate("trend", lambda p: p["points"].reverse()), "CONSTRAINT_VIOLATION"))

    out.append(("anomaly", "conclusion_without_rows", mutate("anomaly", lambda p: p.update(anomalies=[], conclusion="anomaly_found")), "CONSTRAINT_VIOLATION"))
    out.append(("anomaly", "rows_without_anomaly", mutate("anomaly", lambda p: p.update(conclusion="no_anomaly")), "CONSTRAINT_VIOLATION"))
    out.append(("anomaly", "score_under_threshold", mutate("anomaly", lambda p: p["anomalies"][0].update(score=1.2)), "THRESHOLD_UNJUSTIFIED"))
    out.append(("anomaly", "deviation_mismatch", mutate("anomaly", lambda p: p["anomalies"][0].update(deviation=-100.0)), "CONSTRAINT_VIOLATION"))

    out.append(("forecast", "interval_misses_value", mutate("forecast", lambda p: p["points"][0].update(low=120000.0)), "CONSTRAINT_VIOLATION"))
    out.append(("forecast", "history_overlaps_horizon", mutate("forecast", lambda p: p["history_window"].update(end="2026-11-02")), "WINDOW_INVALID"))
    out.append(("forecast", "mape_cap", mutate("forecast", lambda p: p["backtest"].update(mape=0.45)), "CONSTRAINT_VIOLATION"))
    return out


def main() -> int:
    rows = []
    failed = 0
    for task, case_id, payload, expected in cases():
        code, message = verdict(task, payload)
        ok = code == expected
        failed += 0 if ok else 1
        rows.append((task, case_id, code, expected, "ok" if ok else "FAIL", message))

    w1 = max(len(r[0]) for r in rows)
    w2 = max(len(r[1]) for r in rows)
    w3 = max(len(r[2]) for r in rows)
    print(f"{'task'.ljust(w1)}  {'case'.ljust(w2)}  {'got':<{w3}}  {'want':<{w3}}  verdict")
    for task, case_id, code, expected, status, message in rows:
        print(f"{task.ljust(w1)}  {case_id.ljust(w2)}  {code:<{w3}}  {expected:<{w3}}  {status}")
        if status == "FAIL":
            print(f"{'':>{w1}}    └ {message}")

    total = len(rows)
    print(f"\n{total - failed}/{total} cases behave as expected")
    if failed:
        print("contract regression: fix the schema or the rule before shipping", file=sys.stderr)
        return 1
    print("contracts behave")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())