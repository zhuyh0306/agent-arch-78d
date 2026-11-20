"""The one piece of agent logic the skeleton actually has.

It is intentionally thin -- one method that validates a metric against the
dictionary and asks the model to explain it. The point is not the feature; it
is that the class takes three *ports* in its constructor and therefore cannot
reach a file, a socket or an SDK without an adapter being handed to it.
"""

from __future__ import annotations

from dataclasses import dataclass

from dataagent.agent.ports.llm import LLMPort, LLMRequest
from dataagent.agent.ports.repo import MetricRepositoryPort
from dataagent.agent.ports.tool import ToolPort


@dataclass(frozen=True, slots=True)
class ExplainResult:
    metric_id: str
    answer: str
    model: str


class AgentService:
    """Assembles an explanation for one metric, using ports only."""

    def __init__(self, llm: LLMPort, tools: ToolPort, metrics: MetricRepositoryPort) -> None:
        self._llm = llm
        self._tools = tools
        self._metrics = metrics

    @property
    def tool_names(self) -> frozenset[str]:
        return self._tools.available()

    def explain_metric(self, metric_id: str) -> ExplainResult:
        """Return the dictionary definition, never a model's recollection of it.

        ``MetricNotFound`` propagates unchanged: the API layer already maps it to
        METRIC_NOT_IN_DICTIONARY, so translating it here would only lose detail.
        """
        definition = self._metrics.get(metric_id)

        request = LLMRequest(
            system="你是数据指标解释器。只依据给定定义作答，不得补充字典外的口径。",
            user=f"指标：{definition.name}\n定义：{definition.definition}\n单位：{definition.unit}",
            metadata={"metric_id": metric_id},
        )
        response = self._llm.complete(request)
        return ExplainResult(metric_id=metric_id, answer=response.text, model=response.model)