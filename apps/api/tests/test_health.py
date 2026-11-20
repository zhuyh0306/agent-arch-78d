"""Health behaviour: the probe must fail when a dependency fails.

These are the tests that stop ``/healthz`` from becoming a constant 200.
Every failing case drives the *real* route with a real container whose adapter
is broken, rather than mocking the route.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from dataagent.agent.ports.llm import LLMRequest, LLMResponse
from dataagent.agent.service import AgentService
from dataagent.api.app import create_app
from dataagent.infra.container import Container, build_container
from dataagent.infra.settings import Settings

DICTIONARY = Path(__file__).resolve().parents[3] / "packages" / "contracts" / "metrics_dictionary.yaml"


def client(**overrides) -> TestClient:
    settings = Settings(metrics_dictionary=DICTIONARY, **overrides)
    return TestClient(create_app(build_container(settings)))


def test_healthz_reports_ok() -> None:
    response = client().get("/healthz")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert set(body["dependencies"]) == {"metrics_dictionary", "llm", "tools"}
    assert all(d["state"] == "ok" for d in body["dependencies"].values())


def test_tools_are_non_critical() -> None:
    body = client().get("/healthz").json()
    assert body["dependencies"]["tools"]["critical"] is False
    assert body["dependencies"]["metrics_dictionary"]["critical"] is True


class BrokenLLM:
    """A valid LLMPort that always fails -- the shape of a dead provider."""

    def complete(self, request: LLMRequest) -> LLMResponse:
        raise ConnectionError("provider unreachable")


def test_healthz_fails_when_critical_llm_down() -> None:
    """A dead provider is critical: the probe must say so, not stay green."""
    container = build_container(Settings(metrics_dictionary=DICTIONARY))
    broken = BrokenLLM()
    broken_container = Container(
        settings=container.settings,
        llm=broken,
        tools=container.tools,
        metrics=container.metrics,
        agent=AgentService(llm=broken, tools=container.tools, metrics=container.metrics),
    )
    with TestClient(create_app(broken_container)) as test_client:
        response = test_client.get("/healthz")

    assert response.status_code == 503
    body = response.json()
    assert body["status"] == "fail"
    assert body["dependencies"]["llm"]["state"] == "down"
    assert "ConnectionError" in body["dependencies"]["llm"]["detail"]


def test_healthz_fails_when_dictionary_unreadable(tmp_path: Path) -> None:
    bad = tmp_path / "metrics.yaml"
    bad.write_text("metrics: []\n", encoding="utf-8")
    with pytest.raises(ValueError, match="no metrics found"):
        build_container(Settings(metrics_dictionary=bad))


def test_healthz_detail_is_absent_when_healthy() -> None:
    body = client().get("/healthz").json()
    assert "detail" not in body["dependencies"]["llm"]