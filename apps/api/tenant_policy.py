"""Reference tenant boundary checks for the five data hops (Day 11).

This is a policy simulator, not the database enforcement itself. The RLS
snippet lives in docs/multi-tenancy.md; this module makes the five attack
cases executable before tenant tables exist.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from enum import Enum
from pathlib import Path


class Hop(str, Enum):
    REQUEST = "request"
    DB = "db"
    VECTOR = "vector"
    LOG = "log"
    MEMORY = "memory"


class Reason(str, Enum):
    OK = "OK"
    TENANT_MISSING = "TENANT_MISSING"
    TENANT_MISMATCH = "TENANT_MISMATCH"
    FILTER_MISSING = "FILTER_MISSING"
    UNKNOWN_HOP = "UNKNOWN_HOP"


@dataclass(frozen=True, slots=True)
class Decision:
    allow: bool
    reason: Reason


def authorize_hop(
    hop: str,
    auth_tenant: str | None,
    target_tenant: str | None,
    *,
    tenant_in_filter: bool = True,
) -> Decision:
    """Decide whether one hop may touch the target tenant.

    ``auth_tenant`` must come from the verified session, never from the request
    body. ``target_tenant`` is what this hop is about to read or write.
    """
    try:
        parsed = Hop(hop)
    except ValueError:
        return Decision(False, Reason.UNKNOWN_HOP)

    if not auth_tenant:
        return Decision(False, Reason.TENANT_MISSING)

    if parsed is Hop.REQUEST and target_tenant is None:
        target_tenant = auth_tenant

    if not target_tenant:
        return Decision(False, Reason.TENANT_MISSING)

    if target_tenant != auth_tenant:
        return Decision(False, Reason.TENANT_MISMATCH)

    if parsed is Hop.VECTOR and not tenant_in_filter:
        return Decision(False, Reason.FILTER_MISSING)

    return Decision(True, Reason.OK)


def load_cases(path: Path | None = None) -> list[dict]:
    fixture = path or Path(__file__).resolve().parent / "fixtures" / "tenant_cases.json"
    return json.loads(fixture.read_text())["cases"]


def main() -> int:
    rows: list[tuple[str, str, str, str, str]] = []
    failed = False
    for case in load_cases():
        decision = authorize_hop(
            case["hop"],
            case.get("auth_tenant"),
            case.get("target_tenant"),
            tenant_in_filter=case.get("tenant_in_filter", True),
        )
        got = "ALLOW" if decision.allow else f"DENY:{decision.reason.value}"
        expected = case["expect"]
        ok = got == expected
        failed = failed or not ok
        rows.append((case["id"], case["hop"], expected, got, "ok" if ok else "MISMATCH"))

    width = max(len(row[0]) for row in rows)
    print(f"{'case'.ljust(width)}  {'hop':<8}{'expected':<24}{'got':<24}verdict")
    for case_id, hop, expected, got, verdict in rows:
        print(f"{case_id.ljust(width)}  {hop:<8}{expected:<24}{got:<24}{verdict}")

    denied = sum(1 for row in rows if row[2].startswith("DENY"))
    print(f"{denied} attacks denied, {len(rows) - denied} control allowed")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())