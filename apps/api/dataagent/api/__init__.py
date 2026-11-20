"""API layer: HTTP in, HTTP out, and nothing else.

Routes translate a request into a call on the container and translate the
result back. They must not contain business rules -- "what counts as healthy"
lives in the domain, "what to do about a missing metric" lives in the agent.

The app factory takes the container as a parameter rather than building one,
so tests can hand it fakes and the process wiring stays in ``dataagent.infra``.
"""

from dataagent.api.app import create_app

__all__ = ["create_app"]