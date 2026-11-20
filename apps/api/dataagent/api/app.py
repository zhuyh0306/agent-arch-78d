"""FastAPI application factory.

The container is injected, never imported-and-built here. That single rule is
what lets ``tests/`` exercise the real routes with fake ports instead of
spinning a server with a real dictionary.
"""

from __future__ import annotations

import logging
from collections.abc import Callable

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from dataagent.agent.ports.repo import MetricNotFound
from dataagent.api import docs
from dataagent.api.routes import health, metrics, ui
from dataagent.infra.container import Container

logger = logging.getLogger(__name__)


def create_app(container: Container, *, expose_docs: bool = True) -> FastAPI:
    app = FastAPI(
        title=container.settings.app_name,
        version=container.settings.version,
        # Swagger/ReDoc are disabled here on purpose and re-added below behind
        # HTTP Basic (see dataagent/api/docs.py). FastAPI's built-ins are
        # anonymous; an endpoint inventory should not be.
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
    )
    app.state.container = container

    app.include_router(health.router)
    app.include_router(metrics.router)
    app.include_router(ui.router)

    @app.exception_handler(MetricNotFound)
    async def metric_not_found(_: Request, exc: MetricNotFound) -> JSONResponse:
        # METRIC_NOT_IN_DICTIONARY is a Day 14 code; reuse it rather than invent
        # a second vocabulary for the same condition.
        return JSONResponse(status_code=422, content={"failure_code": "METRIC_NOT_IN_DICTIONARY", "detail": str(exc)})

    if expose_docs:
        docs.add_docs_routes(app, container.api_keys)

    return app


def build_app(settings_factory: Callable | None = None) -> FastAPI:
    """Convenience for ``uvicorn dataagent.api.app:build_app`` style startup."""
    from dataagent.infra.container import build_container
    from dataagent.infra.settings import Settings

    settings = settings_factory() if settings_factory else Settings.from_env()
    return create_app(build_container(settings))