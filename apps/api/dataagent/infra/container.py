"""The composition root: the only place that names a concrete adapter.

This is the payoff of the DIP. Every other module depends on a port; the
wiring -- which YAML file, which model, which timeout -- is decided exactly
here, once. Swapping the echo model for LiteLLM (Day 16) edits this file and
nothing else.

``Container`` is a plain dataclass of already-constructed objects. No lazy
resolution, no service locator: anything that could ask a global registry for a
dependency has stopped depending on its interface and started depending on the
container.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from dataagent.agent.adapters import EchoLLM, build_default_tools
from dataagent.agent.adapters.yaml_metrics import YamlMetricRepository
from dataagent.agent.ports import LLMPort, MetricRepositoryPort, ToolPort
from dataagent.agent.service import AgentService
from dataagent.domain.auth import ApiKeyStore
from dataagent.domain.health import DependencySpec
from dataagent.infra.settings import Settings


@dataclass(frozen=True, slots=True)
class Container:
    settings: Settings
    llm: LLMPort
    tools: ToolPort
    metrics: MetricRepositoryPort
    agent: AgentService
    api_keys: ApiKeyStore = field(default_factory=ApiKeyStore)

    def dependency_specs(self) -> tuple[DependencySpec, ...]:
        """Which dependencies /healthz promises to report on.

        The dictionary is critical: without it the agent cannot answer at all.
        The model is critical for the same reason. The tool registry is not --
        a broken tool degrades one capability, not the service.
        """
        return (
            DependencySpec("metrics_dictionary", critical=True),
            DependencySpec("llm", critical=True),
            DependencySpec("tools", critical=False),
        )


def build_container(settings: Settings) -> Container:
    """Construct the real object graph. Raises if the dictionary is unreadable."""
    metrics = YamlMetricRepository(settings.metrics_dictionary)
    llm: LLMPort = EchoLLM()
    tools: ToolPort = build_default_tools()
    agent = AgentService(llm=llm, tools=tools, metrics=metrics)
    api_keys = ApiKeyStore.from_env()
    return Container(
        settings=settings,
        llm=llm,
        tools=tools,
        metrics=metrics,
        agent=agent,
        api_keys=api_keys,
    )