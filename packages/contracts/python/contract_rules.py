"""Cross-field rules the five contracts need but JSON Schema cannot express.

JSON Schema validates shape and value domains. It has no verb for "delta must
equal left.value minus right.value", because a keyword cannot reference another
instance location. Those rules live here, in code, so they are testable and so
there is exactly one place callers can look.

Each rule is a pure function ``payload -> list[RuleViolation]``; an empty list
means the payload satisfies that rule.
"""

from __future__ import annotations

import math
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True, slots=True)
class RuleViolation:
    rule: str
    failure_code: str
    detail: str


def _close(a: float, b: float, tol: float = 1e-6) -> bool:
    return math.isclose(a, b, rel_tol=1e-6, abs_tol=tol)


def _parse_day(value: str) -> date:
    return date.fromisoformat(value)


# ---------------------------------------------------------------- compare


def check_compare(payload: dict) -> list[RuleViolation]:
    out: list[RuleViolation] = []
    left, right, delta = payload["left"], payload["right"], payload["delta"]

    if left["label"] == right["label"]:
        out.append(RuleViolation("distinct_labels", "CONSTRAINT_VIOLATION", "left.label == right.label：自比无意义"))

    expected_abs = left["value"] - right["value"]
    if not _close(delta["absolute"], expected_abs):
        out.append(
            RuleViolation(
                "delta_absolute",
                "CONSTRAINT_VIOLATION",
                f"delta.absolute={delta['absolute']} 与 left-right={expected_abs} 不符",
            )
        )

    if right["value"] == 0:
        if delta["relative"] is not None:
            out.append(
                RuleViolation("relative_null_on_zero_base", "CONSTRAINT_VIOLATION", "基期为 0 时 relative 必须为 null")
            )
    elif delta["relative"] is None:
        out.append(RuleViolation("relative_required", "CONSTRAINT_VIOLATION", "基期非 0 时 relative 不能为空"))
    elif not _close(delta["relative"], delta["absolute"] / right["value"]):
        out.append(
            RuleViolation(
                "relative_value",
                "CONSTRAINT_VIOLATION",
                f"delta.relative={delta['relative']} 与 absolute/right={delta['absolute'] / right['value']} 不符",
            )
        )

    magnitude = abs(delta["absolute"])
    expected_dir = "flat" if magnitude < 1e-9 else ("up" if delta["absolute"] > 0 else "down")
    if payload["direction"] != expected_dir:
        out.append(
            RuleViolation("direction_matches_sign", "CONSTRAINT_VIOLATION", f"direction={payload['direction']} 应为 {expected_dir}")
        )

    cap = payload["constraints"]["max_dimensions"]
    for side in ("left", "right"):
        dims = payload[side].get("dimensions") or []
        if len(dims) > cap:
            out.append(RuleViolation("dimension_cap", "CONSTRAINT_VIOLATION", f"{side} 维度数 {len(dims)} > {cap}"))
    if len(payload["evidence"]) > 10:
        out.append(RuleViolation("evidence_cap", "CONSTRAINT_VIOLATION", "evidence 超过 10 条"))
    return out


# ------------------------------------------------------------ attribution


def check_attribution(payload: dict) -> list[RuleViolation]:
    out: list[RuleViolation] = []
    total = payload["total_change"]
    contributors = payload["contributors"]
    constraints = payload["constraints"]

    base_start = payload["baseline_window"]["start"]
    base_end = payload["baseline_window"]["end"]
    if base_start >= base_end:
        out.append(RuleViolation("baseline_window_order", "WINDOW_INVALID", "baseline_window.start 不早于 end"))
    if not base_end <= payload["window"]["start"]:
        out.append(RuleViolation("baseline_before_window", "WINDOW_INVALID", "基线期必须早于被观察期"))

    total_contrib = 0.0
    for i, item in enumerate(contributors):
        total_contrib += item["contribution"]
        if total == 0:
            if item["share"] is not None:
                out.append(RuleViolation("share_null_on_zero_total", "CONSTRAINT_VIOLATION", f"contributors[{i}] 总变化为 0，share 必须 null"))
        elif item["share"] is None:
            out.append(RuleViolation("share_required", "CONSTRAINT_VIOLATION", f"contributors[{i}] 总变化非 0，share 不能 null"))
        elif not _close(item["share"], item["contribution"] / total):
            out.append(RuleViolation("share_value", "CONSTRAINT_VIOLATION", f"contributors[{i}] share 与 contribution/total 不符"))
        if i and abs(contributors[i - 1]["contribution"]) < abs(item["contribution"]):
            out.append(RuleViolation("sorted_desc", "CONSTRAINT_VIOLATION", f"contributors[{i}] 未按 |contribution| 降序"))

    residual = total - total_contrib
    if not _close(payload["residual"], residual):
        out.append(
            RuleViolation("residual_value", "CONSTRAINT_VIOLATION", f"residual={payload['residual']} 与 total-sum={residual} 不符")
        )
    if abs(residual) > constraints["closure_tolerance"]:
        out.append(
            RuleViolation(
                "closure",
                "CONSTRAINT_VIOLATION",
                f"|residual|={abs(residual):.6f} > closure_tolerance={constraints['closure_tolerance']}：归因未闭合",
            )
        )
    if len(contributors) > constraints["max_contributors"]:
        out.append(RuleViolation("contributor_cap", "CONSTRAINT_VIOLATION", "contributors 超过 max_contributors"))
    return out


# ------------------------------------------------------------------ trend


def check_trend(payload: dict) -> list[RuleViolation]:
    out: list[RuleViolation] = []
    points = payload["points"]
    constraints = payload["constraints"]

    if payload["window"]["start"] >= payload["window"]["end"]:
        out.append(RuleViolation("window_order", "WINDOW_INVALID", "window.start 不早于 end"))
    if len(points) < constraints["min_points"]:
        out.append(RuleViolation("min_points", "INSUFFICIENT_DATA", f"点数 {len(points)} < {constraints['min_points']}"))
    if len(points) > constraints["max_points"]:
        out.append(RuleViolation("max_points", "WINDOW_TOO_LONG", "点数超过 max_points"))

    periods = [p["period"] for p in points]
    if periods != sorted(periods):
        out.append(RuleViolation("points_sorted", "CONSTRAINT_VIOLATION", "points 未按 period 升序"))
    if len(set(periods)) != len(periods):
        out.append(RuleViolation("points_unique", "CONSTRAINT_VIOLATION", "points 存在重复周期"))
    for p in points:
        if not (payload["window"]["start"] <= p["period"] < payload["window"]["end"]):
            out.append(RuleViolation("point_in_window", "WINDOW_INVALID", f"{p['period']} 不在时窗内"))
            break

    if constraints["exclude_incomplete_period"]:
        for cp in payload["change_points"]:
            if cp["period"] in {p["period"] for p in points if not p["is_complete"]}:
                out.append(
                    RuleViolation("changepoint_on_incomplete", "CONSTRAINT_VIOLATION", f"拐点 {cp['period']} 落在未完成周期上，会被误读")
                )

    complete = [p for p in points if p["is_complete"]]
    if len(complete) >= 2:
        expected_abs = complete[-1]["value"] - complete[0]["value"]
        pc = payload["period_change"]
        if not _close(pc["absolute"], expected_abs):
            out.append(
                RuleViolation(
                    "period_change_absolute",
                    "CONSTRAINT_VIOLATION",
                    f"period_change.absolute={pc['absolute']} 与首尾完整点差 {expected_abs} 不符",
                )
            )
        if complete[0]["value"] == 0:
            if pc["relative"] is not None:
                out.append(RuleViolation("period_change_relative_null", "CONSTRAINT_VIOLATION", "首点为 0 时 relative 必须 null"))
        elif pc["relative"] is None:
            out.append(RuleViolation("period_change_relative_required", "CONSTRAINT_VIOLATION", "首点非 0 时 relative 不能为空"))
        elif not _close(pc["relative"], pc["absolute"] / complete[0]["value"]):
            out.append(RuleViolation("period_change_relative", "CONSTRAINT_VIOLATION", "period_change.relative 与 absolute/首点 不符"))

    return out


# ---------------------------------------------------------------- anomaly


def check_anomaly(payload: dict) -> list[RuleViolation]:
    out: list[RuleViolation] = []
    anomalies = payload["anomalies"]
    conclusion = payload["conclusion"]
    method_threshold = payload["method"]["threshold"]

    if payload["window"]["start"] >= payload["window"]["end"]:
        out.append(RuleViolation("window_order", "WINDOW_INVALID", "window.start 不早于 end"))

    if len(anomalies) > payload["constraints"]["max_anomalies"]:
        out.append(RuleViolation("anomaly_cap", "CONSTRAINT_VIOLATION", "anomalies 超过 max_anomalies"))

    if conclusion == "anomaly_found" and not anomalies:
        out.append(RuleViolation("conclusion_needs_rows", "CONSTRAINT_VIOLATION", "anomaly_found 但 anomalies 为空"))
    if conclusion == "no_anomaly" and anomalies:
        out.append(RuleViolation("no_anomaly_needs_empty", "CONSTRAINT_VIOLATION", "no_anomaly 但 anomalies 非空"))
    if conclusion == "insufficient_data":
        out.append(RuleViolation("insufficient_is_not_anomaly", "INSUFFICIENT_DATA", "数据不足时不应给出异常结论"))

    for i, a in enumerate(anomalies):
        expected = a["value"] - a["baseline_value"]
        if not _close(a["deviation"], expected):
            out.append(RuleViolation("deviation_value", "CONSTRAINT_VIOLATION", f"anomalies[{i}].deviation 与 value-baseline 不符"))
        if abs(a["score"]) < method_threshold:
            out.append(
                RuleViolation(
                    "score_below_threshold",
                    "THRESHOLD_UNJUSTIFIED",
                    f"anomalies[{i}].score={a['score']} 未达到 method.threshold={method_threshold} 却入选",
                )
            )
    return out


# --------------------------------------------------------------- forecast


def check_forecast(payload: dict) -> list[RuleViolation]:
    out: list[RuleViolation] = []
    points = payload["points"]
    horizon = payload["horizon"]
    constraints = payload["constraints"]

    if _parse_day(horizon["start"]) >= _parse_day(horizon["end"]):
        out.append(RuleViolation("horizon_order", "WINDOW_INVALID", "horizon.start 不早于 end"))
    if not _parse_day(payload["history_window"]["end"]) <= _parse_day(horizon["start"]):
        out.append(RuleViolation("history_before_horizon", "WINDOW_INVALID", "history_window.end 必须不晚于 horizon.start"))
    if len(points) > constraints["max_horizon_periods"]:
        out.append(RuleViolation("horizon_cap", "WINDOW_TOO_LONG", f"预测点数 {len(points)} > {constraints['max_horizon_periods']}"))

    periods = [p["period"] for p in points]
    if periods != sorted(periods):
        out.append(RuleViolation("points_sorted", "CONSTRAINT_VIOLATION", "points 未按 period 升序"))
    for p in points:
        if p["low"] > p["value"] or p["high"] < p["value"]:
            out.append(RuleViolation("interval_brackets_value", "CONSTRAINT_VIOLATION", f"{p['period']} 区间未包住点估计"))
            break

    bt = payload["backtest"]
    if bt["mape"] is not None and bt["mape"] > constraints["max_backtest_mape"]:
        out.append(
            RuleViolation(
                "backtest_mape_cap",
                "CONSTRAINT_VIOLATION",
                f"回测 MAPE={bt['mape']} 超过上限 {constraints['max_backtest_mape']}：模型误差过大，不得出结论",
            )
        )
    return out


CHECKERS: dict[str, Callable[[dict], list[RuleViolation]]] = {
    "compare": check_compare,
    "attribution": check_attribution,
    "trend": check_trend,
    "anomaly": check_anomaly,
    "forecast": check_forecast,
}


def check_cross_field(task_type: str, payload: dict) -> list[RuleViolation]:
    """Run the rule set for one contract. Assumes the payload already passed schema."""
    return CHECKERS[task_type](payload)