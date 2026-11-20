"""Port and adapter behaviour.

The point of these tests is not coverage for its own sake -- it is that each
adapter is exercised *through its port*, so a future replacement must satisfy
the same contract.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from dataagent.agent.adapters.in_memory_tools import InMemoryTools, build_default_tools
from dataagent.agent.adapters.yaml_metrics import YamlMetricRepository
from dataagent.agent.ports.llm import LLMRequest
from dataagent.agent.ports.repo import MetricNotFound
from dataagent.agent.ports.tool import ToolExecutionError, ToolInvocation, ToolNotFound
from dataagent.agent.service import AgentService

DICTIONARY = Path(__file__).resolve().parents[3] / "packages" / "contracts" / "metrics_dictionary.yaml"


def test_yaml_repository_reads_the_day13_dictionary() -> None:
    repo = YamlMetricRepository(DICTIONARY)
    assert len(repo) == 20
    assert "gmv" in repo.list_ids()
    gmv = repo.get("gmv")
    assert gmv.unit == "CNY"
    assert gmv.source.startswith("orders.gross_amount")


def test_yaml_repository_raises_for_unknown_metric() -> None:
    repo = YamlMetricRepository(DICTIONARY)
    with pytest.raises(MetricNotFound):
        repo.get("not_a_metric")


def test_default_tools_expose_an_allowlist() -> None:
    tools = build_default_tools()
    assert tools.available() == frozenset({"metric_lookup"})


def test_placeholder_tool_raises_rather_than_inventing_a_value() -> None:
    """A placeholder that returned a number would be mistaken for real data."""
    tools = build_default_tools()
    with pytest.raises(ToolExecutionError):
        tools.invoke(ToolInvocation("metric_lookup", {"metric_id": "gmv"}))


def test_unknown_tool_is_rejected() -> None:
    with pytest.raises(ToolNotFound):
        InMemoryTools().invoke(ToolInvocation("rm_rf"))


def test_agent_uses_the_dictionary_not_memory() -> None:
    metrics = YamlMetricRepository(DICTIONARY)
    from dataagent.agent.adapters.echo_llm import EchoLLM

    llm = EchoLLM()
    agent = AgentService(llm=llm, tools=InMemoryTools(), metrics=metrics)

    result = agent.explain_metric("gmv")

    assert result.metric_id == "gmv"
    # The definition text must reach the model prompt verbatim: the answer is
    # grounded in the dictionary, not in what the model remembers about GMV.
    assert "成交总额" in llm.calls[0].user


def test_agent_propagates_metric_not_found() -> None:
    from dataagent.agent.adapters.echo_llm import EchoLLM

    agent = AgentService(llm=EchoLLM(), tools=InMemoryTools(), metrics=YamlMetricRepository(DICTIONARY))
    with pytest.raises(MetricNotFound):
        agent.explain_metric("not_a_metric")


def test_echo_llm_satisfies_the_port() -> None:
    from dataagent.agent.adapters.echo_llm import EchoLLM
    from dataagent.agent.ports.llm import LLMPort

    adapter = EchoLLM()
    assert isinstance(adapter, LLMPort)  # runtime_checkable Protocol
    response = adapter.complete(LLMRequest(system="s", user="hello"))
    assert response.text.startswith("[echo]")
    assert response.output_tokens > 0