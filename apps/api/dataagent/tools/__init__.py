"""Tools layer: the side-effect boundary.

Two things live here and nowhere else:

* the *executor* that runs a tool with timeouts and turns failures into the
  Day 14 failure codes -- so the API never has to guess what went wrong;
* the adapters that actually touch the warehouse.

The agent receives tools through the ``ToolPort`` interface defined in
``dataagent.agent.ports.tool``; it never imports this package. That is what
keeps the tool implementation swappable without touching orchestration.
"""

from dataagent.tools.executor import SandboxedToolExecutor

__all__ = ["SandboxedToolExecutor"]