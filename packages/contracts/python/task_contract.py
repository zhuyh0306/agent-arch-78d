"""TaskContract: the single shape DataAgent is allowed to return.

Python side (Pydantic v2). The TS side lives in ``ts/task_contract.ts`` and must
agree case by case; ``check_consistency.py`` is the gate.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError


class Confidence(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class FailureCode(str, Enum):
    PARSE_ERROR = "PARSE_ERROR"
    MISSING_FIELD = "MISSING_FIELD"
    ENUM_OUT_OF_RANGE = "ENUM_OUT_OF_RANGE"
    UNKNOWN_FIELD = "UNKNOWN_FIELD"
    TYPE_ERROR = "TYPE_ERROR"
    CONSTRAINT_VIOLATION = "CONSTRAINT_VIOLATION"
    RETRY_EXHAUSTED = "RETRY_EXHAUSTED"


class Citation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    doc_id: str = Field(min_length=1, max_length=64, description="来源条目编号，必须来自工具返回结果")
    snippet: str = Field(min_length=1, max_length=200, description="引用原文片段，不超过 200 字")


class TaskInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query_text: str = Field(min_length=1, max_length=500, description="用户原始问题")
    scope: Literal["tenant", "world"] = Field(description="检索范围")
    max_results: int = Field(default=5, ge=1, le=50, description="返回引用上限")


class TaskOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    answer: str = Field(min_length=1, max_length=4000, description="结论，先给结论后给依据")
    citations: list[Citation] = Field(default_factory=list, max_length=50)
    confidence: Confidence


# Most specific first: a payload with several problems still yields a stable code.
_ERROR_PRIORITY: tuple[tuple[str, FailureCode], ...] = (
    ("missing", FailureCode.MISSING_FIELD),
    ("literal_error", FailureCode.ENUM_OUT_OF_RANGE),
    ("enum", FailureCode.ENUM_OUT_OF_RANGE),
    ("extra_forbidden", FailureCode.UNKNOWN_FIELD),
    ("string_too_short", FailureCode.CONSTRAINT_VIOLATION),
    ("string_too_long", FailureCode.CONSTRAINT_VIOLATION),
    ("too_short", FailureCode.CONSTRAINT_VIOLATION),
    ("too_long", FailureCode.CONSTRAINT_VIOLATION),
    ("greater_than_equal", FailureCode.CONSTRAINT_VIOLATION),
    ("less_than_equal", FailureCode.CONSTRAINT_VIOLATION),
)


def _map_validation_error(exc: ValidationError) -> FailureCode:
    present = {item["type"] for item in exc.errors()}
    for error_type, code in _ERROR_PRIORITY:
        if error_type in present:
            return code
    return FailureCode.TYPE_ERROR


@dataclass(slots=True)
class ValidationResult:
    ok: bool
    code: FailureCode | None = None
    data: dict[str, Any] | None = None
    raw: str = ""
    detail: list[dict[str, Any]] = field(default_factory=list)


def validate_task_output(
    raw: str,
    max_results: int = 50,
    allowed_doc_ids: set[str] | None = None,
) -> ValidationResult:
    """Parse, validate and cross-check one model response.

    Order is deliberate: parse -> schema -> cross-field constraints. A retry
    loop can switch on ``code``; ``RETRY_EXHAUSTED`` belongs to the loop, not
    here.
    """
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        return ValidationResult(ok=False, code=FailureCode.PARSE_ERROR, raw=raw, detail=[{"json": str(exc)}])

    if not isinstance(payload, dict):
        return ValidationResult(
            ok=False,
            code=FailureCode.TYPE_ERROR,
            raw=raw,
            detail=[{"type": "object_type", "loc": ()}],
        )

    try:
        output = TaskOutput.model_validate(payload)
    except ValidationError as exc:
        return ValidationResult(ok=False, code=_map_validation_error(exc), raw=raw, detail=exc.errors())

    if len(output.citations) > max_results:
        return ValidationResult(
            ok=False,
            code=FailureCode.CONSTRAINT_VIOLATION,
            raw=raw,
            detail=[{"constraint": "citations_exceed_max_results", "got": len(output.citations), "max": max_results}],
        )

    if allowed_doc_ids is not None:
        unknown = sorted({c.doc_id for c in output.citations} - allowed_doc_ids)
        if unknown:
            return ValidationResult(
                ok=False,
                code=FailureCode.CONSTRAINT_VIOLATION,
                raw=raw,
                detail=[{"constraint": "citation_not_from_tool_result", "doc_ids": unknown}],
            )

    return ValidationResult(ok=True, data=output.model_dump(mode="json"), raw=raw)