"""Ports: the three things the agent needs from the outside world.

A port is written from the point of view of *what the agent's job requires*,
not from what a library happens to offer. That distinction is the whole point
of the Dependency Inversion Principle: injecting a raw SDK client would invert
the instantiation but keep the low-level abstraction, which buys nothing.

Rules for this package:

* protocols only -- no imports from adapters, api, or any vendor SDK;
* every method is described in the agent's vocabulary (a metric, an answer,
  a tool result), never in a library's vocabulary (a Row, a Completion, a Chat);
* port methods raise the errors defined here, so the agent never learns which
  adapter it is talking to.
"""

from dataagent.agent.ports.llm import LLMPort, LLMRequest, LLMResponse
from dataagent.agent.ports.repo import MetricNotFound, MetricRepositoryPort
from dataagent.agent.ports.tool import ToolExecutionError, ToolNotFound, ToolPort

__all__ = [
    "LLMPort",
    "LLMRequest",
    "LLMResponse",
    "MetricNotFound",
    "MetricRepositoryPort",
    "ToolExecutionError",
    "ToolNotFound",
    "ToolPort",
]