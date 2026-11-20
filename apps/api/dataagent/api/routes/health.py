"""Health routes.

``/healthz`` is the Day 15 acceptance item. It is written to be honest:

* it actually exercises the critical dependencies (load a metric from the
  dictionary, run the model adapter) rather than returning a constant;
* it returns 503 when a critical dependency is down, because a probe that only
  ever answers 200 tells the load balancer nothing;
* the payload shape follows the domain report, so the route adds no logic.
"""

from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from dataagent.agent.ports.llm import LLMRequest
from dataagent.domain.health import DependencySpec, build_report

router = APIRouter(tags=["health"])


def _probe_metrics(request: Request):
    container = request.app.state.container

    def probe() -> None:
        metric_id = next(iter(container.metrics.list_ids()))
        container.metrics.get(metric_id)

    return probe


def _probe_llm(request: Request):
    container = request.app.state.container

    def probe() -> None:
        container.llm.complete(LLMRequest(system="healthz", user="ping", max_tokens=8))

    return probe


def _probe_tools(request: Request):
    container = request.app.state.container

    def probe() -> None:
        if not container.tools.available():
            raise RuntimeError("no tools registered")

    return probe


PROBES = {
    "metrics_dictionary": _probe_metrics,
    "llm": _probe_llm,
    "tools": _probe_tools,
}


@router.get("/healthz")
def healthz(request: Request) -> JSONResponse:
    """Unauthenticated on purpose.

    A load balancer has no API key, and a probe it cannot call is a probe that
    gets disabled. The payload is kept to dependency names and states -- no
    configuration, no key material, no tenant data -- so an anonymous caller
    learns nothing exploitable. Any detail added here owes the same test.
    """
    container = request.app.state.container
    specs: tuple[DependencySpec, ...] = container.dependency_specs()
    report = build_report(specs, {spec.name: PROBES[spec.name](request) for spec in specs})
    body = report.as_dict()
    body["app"] = container.settings.app_name
    body["version"] = container.settings.version
    return JSONResponse(status_code=200 if report.healthy else 503, content=body)