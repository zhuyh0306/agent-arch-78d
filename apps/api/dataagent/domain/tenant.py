"""Tenant context: how a request proves which tenant it belongs to.

Day 11 established the five-hop rule (`docs/multi-tenancy.md`): ``tenant_id``
must ride along every hop -- request, db, vector, log, memory -- and must never
be re-derived mid-flight. Day 15's API had no request hop at all, so this module
is that hop.

The single most important decision here: **the tenant comes from the
authenticated identity, never from the request body or a query parameter.** A
caller-supplied ``tenant_id`` in a JSON body is indistinguishable from an
attempt to read another tenant's data; accepting it would make every downstream
RLS policy pointless, because the boundary would already have been crossed
before the database was asked.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from dataagent.domain.tenant_policy import Decision, Hop, authorize_hop

# Tenant ids appear in SQL session settings, log lines and vector namespaces.
# Keeping the charset to lowercase alnum + dash means no quoting or escaping is
# ever needed downstream; the alternative (accept anything, escape everywhere)
# is where injection bugs live.
_TENANT_RE = re.compile(r"^[a-z0-9][a-z0-9-]{1,31}$")


class TenantResolutionError(ValueError):
    """The request cannot be attributed to exactly one valid tenant."""

    def __init__(self, reason: str, detail: str = "") -> None:
        super().__init__(detail or reason)
        self.reason = reason


@dataclass(frozen=True, slots=True)
class TenantContext:
    """The verified tenant for one request, plus who authenticated it.

    Immutable on purpose: nothing downstream may rewrite it. A hop that needs a
    different tenant must fail, not mutate.
    """

    tenant_id: str
    principal: str

    def __post_init__(self) -> None:
        if not _TENANT_RE.match(self.tenant_id):
            raise TenantResolutionError("TENANT_INVALID", f"invalid tenant id: {self.tenant_id!r}")

    def authorize(self, hop: Hop | str, target_tenant: str | None = None) -> Decision:
        """Ask the Day 11 policy whether this context may touch a hop.

        ``target_tenant`` defaults to the context's own tenant: a hop that does
        not name a target is implicitly the caller's own data.
        """
        return authorize_hop(hop, self.tenant_id, target_tenant if target_tenant is not None else self.tenant_id)

    def as_log_fields(self) -> dict[str, str]:
        """Fields every log line for this request must carry."""
        return {"tenant_id": self.tenant_id, "principal": self.principal}