"""Request-time dependency: authenticate, then pin the tenant for the request.

Every business route depends on ``get_tenant_context``. Because it is a FastAPI
dependency rather than an optional call, a route that forgets it is not a
security hole -- it is simply a route that cannot read a tenant. That is the
property worth having: the safe path is the only path.

Deliberately **no fallback tenant**. If ``DATAAGENT_API_KEYS`` is unset the store
is empty and every request is rejected. A "dev default tenant" would be the
single easiest way to ship a cross-tenant leak to production, because it would
silently work in every environment that forgot to set the variable.
"""

from __future__ import annotations

import logging

from fastapi import Header, HTTPException, Request

from dataagent.domain.auth import AuthenticationError
from dataagent.domain.tenant import TenantContext

logger = logging.getLogger(__name__)


async def get_tenant_context(
    request: Request,
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
) -> TenantContext:
    """Resolve the verified tenant, or fail closed with 401.

    The rejection is logged with the path but never with the credential: a key
    leaked into a log file is as bad as a key leaked anywhere else.
    """
    container = request.app.state.container
    try:
        context = container.api_keys.authenticate(x_api_key)
    except AuthenticationError:
        logger.warning(
            "auth rejected path=%s method=%s has_credential=%s",
            request.url.path,
            request.method,
            bool(x_api_key),
        )
        # 401 with a Day 14 code: GUARDRAIL_BLOCKED is what the table calls
        # "a boundary rule stopped this", and it keeps one vocabulary.
        raise HTTPException(
            status_code=401,
            detail={"failure_code": "GUARDRAIL_BLOCKED", "detail": "unauthorized"},
        ) from None

    request.state.tenant = context
    return context