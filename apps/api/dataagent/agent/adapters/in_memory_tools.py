"""An in-process tool registry -- the shape real tools will slot into.

Today's tools are trivial placeholders that return fixed values. That is
intentional: the acceptance item is the skeleton, and a placeholder that
returns a *known wrong-looking* value (``NotImplementedYet``) is safer than one
that looks like real data. When the SQL tool lands, it registers here and the
agent code does not change.

The allowlist matters more than the implementations: ``available()`` is the
tool whitelist that the harness (Day 5) will enforce, so it exists from day one
rather than being retrofitted under time pressure.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any

from dataagent.agent.ports.tool import ToolExecutionError, ToolInvocation, ToolNotFound, ToolResult

ToolFn = Callable[[Mapping[str, Any]], tuple[Any, str]]


class InMemoryTools:
    """Satisfies ToolPort with an explicit registry of named callables."""

    def __init__(self, registry: Mapping[str, ToolFn] | None = None) -> None:
        self._registry: dict[str, ToolFn] = dict(registry or {})

    def register(self, name: str, fn: ToolFn) -> None:
        if not name or not name.strip():
            raise ValueError("tool name must be non-empty")
        self._registry[name] = fn

    def available(self) -> frozenset[str]:
        return frozenset(self._registry)

    def invoke(self, invocation: ToolInvocation) -> ToolResult:
        try:
            fn = self._registry[invocation.name]
        except KeyError:
            raise ToolNotFound(invocation.name) from None
        try:
            value, source = fn(invocation.arguments)
        except Exception as exc:
            raise ToolExecutionError(f"{invocation.name}: {exc}") from exc
        return ToolResult(name=invocation.name, value=value, source=source)


def metric_lookup(_: Mapping[str, Any]) -> tuple[Any, str]:
    """Placeholder: a real tool that reads the business database."""

    raise NotImplementedError("metric_lookup is a Day 16+ tool; it has no data source yet")


def build_default_tools() -> InMemoryTools:
    """The registry as the skeleton ships it: one honest placeholder."""
    tools = InMemoryTools()
    tools.register("metric_lookup", metric_lookup)
    return tools