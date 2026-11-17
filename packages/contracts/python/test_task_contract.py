import json
from pathlib import Path

import pytest

from task_contract import FailureCode, TaskInput, validate_task_output

CASES = json.loads((Path(__file__).resolve().parents[1] / "fixtures" / "cases.json").read_text())


def test_fixture_cases_match_expectations():
    for case in CASES["cases"]:
        result = validate_task_output(case["raw"], CASES["max_results"])
        got = "PASS" if result.ok else result.code.value
        assert got == case["expect"], f"{case['id']}: expected {case['expect']}, got {got}"


def test_input_rejects_out_of_range_max_results():
    with pytest.raises(Exception):
        TaskInput.model_validate({"query_text": "退款率", "scope": "tenant", "max_results": 0})


def test_citations_exceed_max_results():
    raw = json.dumps(
        {
            "answer": "退款率为 3.00%。",
            "citations": [{"doc_id": f"doc-{i}", "snippet": "订单 1200，退款 36。"} for i in range(3)],
            "confidence": "high",
        }
    )
    result = validate_task_output(raw, max_results=2)
    assert result.code is FailureCode.CONSTRAINT_VIOLATION


def test_citation_must_come_from_tool_result():
    raw = json.dumps(
        {
            "answer": "退款率为 3.00%。",
            "citations": [{"doc_id": "doc-9", "snippet": "订单 1200，退款 36。"}],
            "confidence": "high",
        }
    )
    result = validate_task_output(raw, allowed_doc_ids={"doc-1"})
    assert result.code is FailureCode.CONSTRAINT_VIOLATION


def test_unknown_field_is_not_silently_dropped():
    raw = json.dumps(
        {
            "answer": "退款率为 3.00%。",
            "citations": [],
            "confidence": "high",
            "reasoning": "模型自己加的字段",
        }
    )
    result = validate_task_output(raw)
    assert result.code is FailureCode.UNKNOWN_FIELD


def test_priority_missing_beats_enum():
    raw = json.dumps({"citations": [], "confidence": "very_high"})
    result = validate_task_output(raw)
    assert result.code is FailureCode.MISSING_FIELD