"""Health as a domain concept, not a route concern.

``/healthz`` answers one question for a load balancer: should traffic go here
right now? That question is business logic -- it decides what "healthy" means
and which dependencies are critical -- so it lives in the domain layer and the
route only formats the answer.

Deliberate design choice: *liveness* and *readiness* are the same call here.
This process has no background recovery state to distinguish "alive but not
ready", and inventing one would make the probe lie. When a component that
genuinely needs warm-up appears (a vector index, a cache), add a ``ready``
field to ``DependencySpec`` then -- not speculatively now.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from enum import Enum


class DependencyState(str, Enum):
    OK = "ok"
    DOWN = "down"


@dataclass(frozen=True, slots=True)
class DependencySpec:
    """A dependency we promise to report on, and whether it can take us down."""

    name: str
    critical: bool = True


@dataclass(frozen=True, slots=True)
class DependencyResult:
    name: str
    state: DependencyState
    critical: bool = True
    detail: str = ""


@dataclass(frozen=True, slots=True)
class HealthReport:
    """Overall verdict plus per-dependency detail.

    ``healthy`` is true only when every *critical* dependency is OK. A failing
    non-critical dependency does not fail the probe, but it stays visible --
    otherwise a green check hides a broken tool until someone trips on it.
    """

    dependencies: Sequence[DependencyResult] = field(default_factory=tuple)

    @property
    def healthy(self) -> bool:
        return all(d.state is DependencyState.OK for d in self.dependencies if d.critical)

    @property
    def status(self) -> str:
        return "ok" if self.healthy else "fail"

    def as_dict(self) -> dict[str, object]:
        return {
            "status": self.status,
            "dependencies": {
                d.name: {
                    "state": d.state.value,
                    "critical": d.critical,
                    **({"detail": d.detail} if d.detail else {}),
                }
                for d in self.dependencies
            },
        }


def check_dependency(spec: DependencySpec, probe: Callable[[], None]) -> DependencyResult:
    """Run one dependency probe, turning any exception into a state.

    A probe signals failure by raising. It must not return a bool -- a probe
    that can report "looks fine" without doing anything is the most common way
    a health check becomes a lie.
    """
    try:
        probe()
    except Exception as exc:  # noqa: BLE001 - a probe may fail any way; that is the point
        return DependencyResult(spec.name, DependencyState.DOWN, spec.critical, f"{type(exc).__name__}: {exc}")
    return DependencyResult(spec.name, DependencyState.OK, spec.critical)


def build_report(specs: Sequence[DependencySpec], probes: dict[str, Callable[[], None]]) -> HealthReport:
    """Run every registered probe and fold the results into one report."""
    return HealthReport(tuple(check_dependency(spec, probes[spec.name]) for spec in specs if spec.name in probes))