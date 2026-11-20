"""Contract spec gate as pytest cases.

``run_contract_cases.py`` is the human-facing demo; this file is the same
expectations wired into the existing suite, so ``pytest -q`` covers Day 14 too.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from run_contract_cases import cases, verdict  # noqa: E402

SPECS = ROOT / "specs"


def test_gate_passes() -> None:
    completed = subprocess.run([sys.executable, str(ROOT / "check_specs.py")], capture_output=True, text=True)
    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert "contract specs ok" in completed.stdout


@pytest.mark.parametrize(("task", "case_id", "payload", "expected"), cases(), ids=[f"{t}-{c}" for t, c, _, _ in cases()])
def test_contract_case(task: str, case_id: str, payload: dict, expected: str) -> None:
    got, message = verdict(task, payload)
    assert got == expected, message


def test_every_contract_has_a_failure_code_subset() -> None:
    for task in ("compare", "attribution", "trend", "anomaly", "forecast"):
        subset = json.loads((SPECS / f"{task}.failure_codes.json").read_text(encoding="utf-8"))
        assert subset, f"{task} claims no failure codes"
        assert "failure_codes" not in json.loads((SPECS / f"{task}.schema.json").read_text())["properties"]


def test_legal_payloads_pass_schema_before_rules() -> None:
    """Guard the layer boundary: legal payloads must not be rejected by shape."""
    for task, case_id, payload, expected in cases():
        if case_id == "legal":
            assert expected == "PASS"
            assert verdict(task, payload)[0] == "PASS"