"""Adapters: concrete implementations of the three ports.

This package is the only place allowed to know about YAML files, SDKs or
network shape. It is imported by the composition root (``dataagent.infra``),
never by the agent or the domain.
"""

from dataagent.agent.adapters.echo_llm import EchoLLM
from dataagent.agent.adapters.in_memory_tools import InMemoryTools, build_default_tools
from dataagent.agent.adapters.yaml_metrics import YamlMetricRepository

__all__ = ["EchoLLM", "InMemoryTools", "YamlMetricRepository", "build_default_tools"]