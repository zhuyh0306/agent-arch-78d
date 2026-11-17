#!/usr/bin/env python3
"""Fail when the Python and TypeScript contracts disagree on the fixture."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "python"))

from task_contract import validate_task_output  # noqa: E402

FIXTURE = ROOT / "fixtures" / "cases.json"


def python_verdicts(fixture: dict) -> dict[str, str]:
    out: dict[str, str] = {}
    for case in fixture["cases"]:
        result = validate_task_output(case["raw"], fixture["max_results"])
        out[case["id"]] = "PASS" if result.ok else str(result.code.value)
    return out


def ts_verdicts() -> dict[str, str]:
    node = shutil.which("node")
    if node is None:
        raise SystemExit("node not found on PATH; run this script from a login shell (zsh -lic)")
    completed = subprocess.run(
        [node, str(ROOT / "ts" / "run_cases.ts")],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return {item["id"]: item["verdict"] for item in json.loads(completed.stdout)}


def main() -> int:
    fixture = json.loads(FIXTURE.read_text())
    expected = {case["id"]: case["expect"] for case in fixture["cases"]}
    py = python_verdicts(fixture)
    ts = ts_verdicts()

    rows = []
    failed = False
    for case in fixture["cases"]:
        case_id = case["id"]
        py_code, ts_code, want = py[case_id], ts[case_id], expected[case_id]
        agree = py_code == ts_code
        hit = py_code == want
        failed = failed or not agree or not hit
        rows.append((case_id, py_code, ts_code, want, "ok" if agree and hit else "MISMATCH"))

    width = max(len(row[0]) for row in rows)
    print(f"{'case'.ljust(width)}  {'python':<22}{'ts':<22}{'expected':<22}verdict")
    for case_id, py_code, ts_code, want, verdict in rows:
        print(f"{case_id.ljust(width)}  {py_code:<22}{ts_code:<22}{want:<22}{verdict}")

    if failed:
        print("contract drift: fix both schemas before touching callers", file=sys.stderr)
        return 1
    print("contracts agree")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())