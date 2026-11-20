"""Run a tool under a deadline and report failure in the Day 14 vocabulary.

Why an executor exists at all when the port already has ``invoke``: the port
says what a tool call *is*; the executor enforces *how long* it may take and
translates its failure into a stable code. Putting the timeout here instead of
in every tool means no tool can accidentally become unbounded.

The mapping is not invented: ``SUBTASK_TIMEOUT`` and ``SOURCE_UNAVAILABLE`` are
real codes from packages/contracts/failure_codes.yaml, so a failed tool call is
reportable with the same words the contracts use.
"""

from __future__ import annotations

import concurrent.futures
from dataclasses import dataclass

from dataagent.agent.ports.tool import ToolExecutionError, ToolInvocation, ToolNotFound, ToolPort, ToolResult


@dataclass(frozen=True, slots=True)
class ToolOutcome:
    ok: bool
    result: ToolResult | None = None
    failure_code: str | None = None
    detail: str = ""


class SandboxedToolExecutor:
    """Wraps any ToolPort, adding a deadline and failure-code translation."""

    def __init__(self, tools: ToolPort, timeout_seconds: float = 5.0) -> None:
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        self._tools = tools
        self._timeout = timeout_seconds

    def available(self) -> frozenset[str]:
        return self._tools.available()

    def run(self, invocation: ToolInvocation) -> ToolOutcome:
        try:
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                future = pool.submit(self._tools.invoke, invocation)
                try:
                    return ToolOutcome(ok=True, result=future.result(timeout=self._timeout))
                except concurrent.futures.TimeoutError:
                    future.cancel()
                    return ToolOutcome(
                        ok=False,
                        failure_code="SUBTASK_TIMEOUT",
                        detail=f"{invocation.name} exceeded {self._timeout}s",
                    )
        except ToolNotFound:
            return ToolOutcome(ok=False, failure_code="METRIC_NOT_IN_DICTIONARY", detail=f"unknown tool {invocation.name}")
        except ToolExecutionError as exc:
            return ToolOutcome(ok=False, failure_code="SOURCE_UNAVAILABLE", detail=str(exc))