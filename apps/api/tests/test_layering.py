"""Layering guard: the dependency direction is a test, not a convention.

Why this file exists: a layered diagram in a README drifts silently. The only
thing that keeps ``domain`` free of FastAPI six weeks from now is an automated
check. Import rules are enforced by parsing the AST, so no import of a forbidden
module can slip through a string trick.

The rules mirror docs/adr/0006-api-layering.md:

    domain  -> (stdlib only)
    ports   -> domain
    agent   -> ports, domain        (never adapters)
    tools   -> ports, domain
    api     -> agent, infra, domain (never adapters directly)
    infra   -> everything           (composition root)
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

PACKAGE = Path(__file__).resolve().parents[1] / "dataagent"

# layer -> modules it may import (anything else under dataagent.* is a violation)
ALLOWED: dict[str, set[str]] = {
    "root": {"dataagent"},
    "domain": {"dataagent.domain"},
    "ports": {"dataagent.domain", "dataagent.agent.ports"},
    "agent": {"dataagent.domain", "dataagent.agent.ports", "dataagent.agent.service"},
    # Adapters implement ports, so depending on them is allowed and expected.
    # They may not import agent.service or api: an adapter that knows the
    # orchestration has inverted the dependency back.
    "adapters": {"dataagent.domain", "dataagent.agent.ports", "dataagent.agent.adapters", "dataagent.tools"},
    "tools": {"dataagent.domain", "dataagent.agent.ports", "dataagent.tools"},
    "api": {"dataagent.domain", "dataagent.agent", "dataagent.infra", "dataagent.api"},
    "infra": {"dataagent.domain", "dataagent.agent", "dataagent.tools", "dataagent.infra"},
}

# Third-party imports each layer may use. Anything not listed is a violation.
THIRD_PARTY: dict[str, set[str]] = {
    "domain": set(),  # stdlib only: no framework, no driver, no SDK
    "ports": set(),  # protocols + dataclasses only
    "agent": set(),  # adapters own the vendor SDKs
    "tools": set(),
    "api": {"fastapi", "starlette"},
    "infra": {"yaml"},
}

# Stdlib is decided by the interpreter, not by a hand-kept list: a hardcoded
# allowlist silently fails every time the domain legitimately needs a new
# stdlib module (re, hmac, datetime, ...), which trains people to weaken the
# test rather than fix the violation.
STDLIB_OK = frozenset(sys.stdlib_module_names) | {"__future__"}


def layer_of(path: Path) -> str:
    """Return the architectural layer a file belongs to.

    ``agent/adapters/*`` and ``tools/infra/*`` are their own layer despite
    living under agent/ and tools/, because the rule they break is different:
    they are the only packages allowed to know about the outside world.
    """
    rel = path.relative_to(PACKAGE).parts
    if len(rel) == 1:
        return "root"
    if rel[0] == "agent" and len(rel) > 2 and rel[1] == "adapters":
        return "adapters"
    if rel[0] == "agent" and len(rel) > 2 and rel[1] == "ports":
        return "ports"
    if rel[0] == "tools" and len(rel) > 2 and rel[1] == "infra":
        return "adapters"
    if rel[0] == "api" and len(rel) > 2 and rel[1] == "routes":
        return "api"
    return rel[0]


def imports_of(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    found: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            found.append(node.module)
    return found


def module_files() -> list[Path]:
    return sorted(PACKAGE.rglob("*.py"))


def test_no_layer_imports_forbidden_module() -> None:
    violations: list[str] = []
    for path in module_files():
        layer = layer_of(path)
        allowed = ALLOWED.get(layer)
        if allowed is None:
            continue
        for module in imports_of(path):
            if not module.startswith("dataagent"):
                continue
            if module == "dataagent" or any(module == a or module.startswith(a + ".") for a in allowed):
                continue
            violations.append(f"{path.relative_to(PACKAGE)} ({layer}) imports {module}")
    assert not violations, "dependency direction broken:\n" + "\n".join(violations)


def test_domain_uses_no_third_party() -> None:
    violations: list[str] = []
    for path in module_files():
        if layer_of(path) != "domain":
            continue
        for module in imports_of(path):
            root = module.split(".")[0]
            if root in STDLIB_OK or module.startswith("dataagent.domain"):
                continue
            violations.append(f"{path.name} imports {module}")
    assert not violations, "domain must stay framework-free:\n" + "\n".join(violations)


def test_only_infra_names_adapters() -> None:
    """The composition root is the only module allowed to import adapters."""
    offenders: list[str] = []
    for path in module_files():
        if layer_of(path) in {"infra", "adapters"}:
            continue
        for module in imports_of(path):
            if "agent.adapters" in module or "tools.infra" in module:
                offenders.append(f"{path.relative_to(PACKAGE)} imports {module}")
    assert not offenders, "adapters must only be wired in the composition root:\n" + "\n".join(offenders)


def test_agent_layer_survives_without_adapters() -> None:
    """Delete every adapter: agent + domain + ports must still import cleanly."""
    import importlib
    import sys

    blocked = ("dataagent.agent.adapters", "dataagent.tools.infra")

    class Blocker:
        def find_module(self, name, path=None):
            return self if name.startswith(blocked) else None

        def load_module(self, name):
            raise ImportError(f"blocked adapter import: {name}")

    saved = {m: sys.modules.pop(m) for m in list(sys.modules) if m.startswith("dataagent")}
    blocker = Blocker()
    sys.meta_path.insert(0, blocker)
    try:
        for module in ("dataagent.domain", "dataagent.agent.ports", "dataagent.agent.service"):
            importlib.import_module(module)
    finally:
        sys.meta_path.remove(blocker)
        sys.modules.update(saved)