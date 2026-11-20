"""Domain layer: the business concepts, and nothing else.

Rules this package lives by (see docs/adr/0006-api-layering.md):

* no FastAPI, no pydantic request models, no imports from ``dataagent.api``;
* no database driver, no HTTP client, no LLM SDK;
* stdlib only.

If a module here needs to *do* something external -- read a row, call a model,
call a tool -- it declares a port instead. That is what makes the domain
testable without a server, a database or a network.
"""

from dataagent.domain.health import (
    DependencyResult,
    DependencySpec,
    DependencyState,
    HealthReport,
    build_report,
    check_dependency,
)

__all__ = [
    "DependencyResult",
    "DependencySpec",
    "DependencyState",
    "HealthReport",
    "build_report",
    "check_dependency",
]