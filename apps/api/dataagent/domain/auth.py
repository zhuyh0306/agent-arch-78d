"""Authentication: turning an API key into a verified tenant.

Day 15 shipped routes with no auth at all. That is not a gap the rest of the
78-day plan closes -- Days 41 and 46 assume a verified tenant already exists
when the request arrives. So the boundary has to be built here, even though it
is deliberately small.

What this is NOT: an identity provider. There is no OAuth, no JWT verification,
no key rotation, no store beyond the process. It is the *seam* -- a single
function that maps a presented credential to a ``TenantContext`` -- so that
swapping in a real IdP later changes one adapter and touches no route.

Security properties that ARE implemented, because they are cheap and the
alternative is silently broken:

* a key maps to exactly one tenant; the caller cannot choose its tenant;
* keys are compared in constant time (``hmac.compare_digest``);
* the error response never reveals whether the key existed;
* a key that is absent or malformed is rejected before any work happens.
"""

from __future__ import annotations

import hmac
import os
from collections.abc import Mapping
from dataclasses import dataclass, field

from dataagent.domain.tenant import TenantContext, TenantResolutionError


class AuthenticationError(Exception):
    """No valid credential. Deliberately carries no detail about why."""


@dataclass(frozen=True, slots=True)
class ApiKey:
    """A static credential bound to one tenant and one principal label."""

    key: str
    tenant_id: str
    principal: str

    def __repr__(self) -> str:
        # Never let a key reach a log line or a traceback.
        return f"ApiKey(***, tenant_id={self.tenant_id!r}, principal={self.principal!r})"


@dataclass(frozen=True, slots=True)
class ApiKeyStore:
    """In-process key table. Replace with a real store behind the same method."""

    keys: tuple[ApiKey, ...] = field(default_factory=tuple)

    def authenticate(self, presented: str | None) -> TenantContext:
        """Return the verified context, or raise AuthenticationError."""
        if not presented:
            raise AuthenticationError("missing credential")
        presented_bytes = presented.encode()
        # Compare against every key so timing does not reveal a prefix match.
        match: ApiKey | None = None
        for candidate in self.keys:
            if hmac.compare_digest(presented_bytes, candidate.key.encode()):
                match = candidate
        if match is None:
            raise AuthenticationError("invalid credential")
        try:
            return TenantContext(tenant_id=match.tenant_id, principal=match.principal)
        except TenantResolutionError as exc:  # a misconfigured key must not become a 200
            raise AuthenticationError(f"key bound to an invalid tenant: {exc.reason}") from None

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> ApiKeyStore:
        """Parse ``DATAAGENT_API_KEYS`` as ``key:tenant:principal,...``.

        Format chosen for a skeleton: no dependency, no file, obviously not
        production-shaped. An empty/absent value yields an empty store, which
        rejects every request -- fail closed, never "auth disabled by default".
        """
        env = dict(os.environ if env is None else env)
        raw = env.get("DATAAGENT_API_KEYS", "").strip()
        if not raw:
            return cls()
        keys: list[ApiKey] = []
        for entry in raw.split(","):
            entry = entry.strip()
            if not entry:
                continue
            parts = entry.split(":")
            if len(parts) != 3:
                raise ValueError("DATAAGENT_API_KEYS entries must be key:tenant:principal")
            key, tenant_id, principal = (p.strip() for p in parts)
            if not key or not tenant_id or not principal:
                raise ValueError("DATAAGENT_API_KEYS entries must not be empty")
            keys.append(ApiKey(key=key, tenant_id=tenant_id, principal=principal))
        return cls(keys=tuple(keys))