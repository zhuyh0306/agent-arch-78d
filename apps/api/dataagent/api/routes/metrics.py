"""The one business route the skeleton exposes, to prove the seam is real.

``GET /metrics/{metric_id}`` reads the dictionary through the repository port
and asks the model port for an explanation. It exists so the smoke test can
traverse api -> agent -> ports -> adapters end to end in one request, which a
health probe alone cannot show.

Since Day 15's gap-closing pass it also requires a verified tenant, so the
request hop from the Day 11 five-hop rule is exercised by every call rather than
being a promise in a document.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse

from dataagent.api.deps import get_tenant_context
from dataagent.domain.tenant import TenantContext

router = APIRouter(prefix="/metrics", tags=["metrics"])


@router.get("/{metric_id}")
def explain_metric(
    metric_id: str,
    request: Request,
    tenant: TenantContext = Depends(get_tenant_context),
) -> JSONResponse:
    container = request.app.state.container

    # The request hop must pass the Day 11 policy before any work happens.
    # Metric definitions are not tenant-scoped *yet*, so a failure here would be
    # a wiring error; keep the check so the hop cannot be silently skipped when
    # per-tenant dictionaries arrive.
    decision = tenant.authorize("request")
    if not decision.allow:
        return JSONResponse(status_code=403, content={"failure_code": "GUARDRAIL_BLOCKED", "detail": decision.reason.value})

    result = container.agent.explain_metric(metric_id)
    definition = container.metrics.get(metric_id)
    return JSONResponse(
        content={
            "metric_id": result.metric_id,
            "name": definition.name,
            "unit": definition.unit,
            "source": definition.source,
            "answer": result.answer,
            "model": result.model,
            "tenant_id": tenant.tenant_id,
        }
    )