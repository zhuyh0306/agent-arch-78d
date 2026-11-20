"""The tool port: what the agent needs to compute something it must not guess.

Day 14 established that the agent returns evidence-backed values, not memory.
This port is how a value becomes evidence: a named tool returns a typed result
or raises. There is no "question -> string" method, because that is the shape
that lets the model invent numbers and look right.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable


class ToolNotFound(LookupError):
    """The agent asked for a tool that is not registered."""


class ToolExecutionError(RuntimeError):
    """A registered tool ran and failed. The message is safe to log, not to show raw."""


@dataclass(frozen=True, slots=True)
class ToolInvocation:
    name: str
    arguments: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class ToolResult:
    name: str
    value: Any
    # Stable source string ("app.orders.gross_amount") so the answer can cite it
    # and an investigator can walk the lineage back.
    source: str = ""


@runtime_checkable
class ToolPort(Protocol):
    """A registry of named, callable tools."""

    def available(self) -> frozenset[str]:
        """Names the agent may call. The allowlist, not a suggestion."""
        ...

    def invoke(self, invocation: ToolInvocation) -> ToolResult:
        """Run one tool. Raises ToolNotFound / ToolExecutionError."""
        ...