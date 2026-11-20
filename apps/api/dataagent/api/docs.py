"""Interactive API docs, gated behind HTTP Basic.

Why gated: a schema page is a complete inventory of every endpoint, every
parameter and every enum. Publishing it anonymously hands an attacker the map
for free -- that is why Day 15 disabled it entirely. Now that credentials
exist, the right move is not "leave it off" but "put it behind the same gate as
the data".

Why Basic and not the X-API-Key header: a browser cannot send a custom header
on a plain navigation, but it *can* prompt for Basic credentials. Using Basic
here means the page works when you open it in a tab, without a browser
extension, and without pasting a token into a URL (which would then sit in the
history and in the server log).

The credential checked is the same ``ApiKeyStore`` as the API: one key set, one
source of truth. Swap the store and both gates move together.
"""

from __future__ import annotations

import base64
import binascii
import logging

from fastapi import FastAPI, Request
from fastapi.openapi.docs import get_swagger_ui_html
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse, Response

from dataagent.domain.auth import ApiKeyStore, AuthenticationError

logger = logging.getLogger(__name__)

_REALM = 'Basic realm="DataAgent docs", charset="UTF-8"'


def _parse_basic(header: str | None) -> tuple[str, str] | None:
    if not header:
        return None
    scheme, _, encoded = header.partition(" ")
    if scheme.lower() != "basic" or not encoded:
        return None
    try:
        decoded = base64.b64decode(encoded, validate=True).decode("utf-8", "strict")
    except (binascii.Error, UnicodeDecodeError):
        return None
    username, sep, password = decoded.partition(":")
    if not sep:
        return None
    return username, password


class BasicAuthGuard(BaseHTTPMiddleware):
    """Reject anything that does not carry a valid key in either field.

    Only the paths in ``PROTECTED`` are challenged. Mounting this as app-wide
    middleware would also put a Basic challenge in front of ``/metrics``, which
    authenticates with ``X-API-Key`` -- two credential styles on one route is
    how callers end up sending the wrong one and getting a confusing 401.

    Convention: put the API key in the **password** field and any label in the
    username. Browsers handle a blank username poorly, but the key is what is
    checked; the username is only a convenience for the browser prompt.
    """

    PROTECTED = ("/docs", "/openapi.json")

    def __init__(self, app, api_keys: ApiKeyStore) -> None:
        super().__init__(app)
        self._api_keys = api_keys

    async def dispatch(self, request: Request, call_next):
        if not any(request.url.path.startswith(p) for p in self.PROTECTED):
            return await call_next(request)

        credentials = _parse_basic(request.headers.get("authorization"))
        if credentials is None:
            return _challenge()
        username, password = credentials
        # Accept the key in either position so the browser prompt is usable
        # without a convention the user has to remember.
        for candidate in (password, username):
            try:
                request.scope["dataagent.principal"] = self._api_keys.authenticate(candidate).principal
                return await call_next(request)
            except AuthenticationError:
                continue
        logger.warning("docs auth rejected path=%s", request.url.path)
        return _challenge()


def _challenge() -> Response:
    return JSONResponse(
        status_code=401,
        content={"detail": {"failure_code": "GUARDRAIL_BLOCKED", "detail": "docs require credentials"}},
        headers={"WWW-Authenticate": _REALM},
    )


def add_docs_routes(app: FastAPI, api_keys: ApiKeyStore) -> None:
    """Mount a guarded Swagger UI and the OpenAPI document it reads."""
    app.add_middleware(BasicAuthGuard, api_keys=api_keys)

    @app.get("/openapi.json", include_in_schema=False)
    async def openapi_document() -> JSONResponse:
        return JSONResponse(app.openapi())

    @app.get("/docs", include_in_schema=False)
    async def swagger_ui() -> Response:
        # The Swagger bundle is fetched from a CDN. It is the framework default;
        # noted as a limitation because a network-restricted deployment would
        # need a vendored copy.
        return get_swagger_ui_html(openapi_url="/openapi.json", title=f"{app.title} · API docs")