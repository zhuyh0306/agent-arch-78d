"""The repository port: what the agent needs to know about metrics.

Scoped to the metric dictionary on purpose. A generic ``get(table, id)`` or a
``query(sql)`` here would hand the low-level storage abstraction straight to
the agent and kill the inversion -- that is exactly the "inject a JDBC
connection" mistake DIP in the Wild warns about. If a new domain concept needs
storage, add a new port for that concept; do not widen this one.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Protocol, runtime_checkable


class MetricNotFound(LookupError):
    """The requested metric id is not in the dictionary."""


@dataclass(frozen=True, slots=True)
class MetricDefinition:
    """One entry of the Day 13 metrics dictionary, flattened for the agent."""

    id: str
    name: str
    category: str
    definition: str
    unit: str
    source: str

    @classmethod
    def from_mapping(cls, raw: Mapping[str, Any]) -> MetricDefinition:
        missing = [k for k in ("id", "name", "category", "definition", "unit", "source") if not raw.get(k)]
        if missing:
            raise ValueError(f"metric entry missing {missing}")
        return cls(**{k: raw[k] for k in ("id", "name", "category", "definition", "unit", "source")})


@runtime_checkable
class MetricRepositoryPort(Protocol):
    """Read access to the metric dictionary."""

    def get(self, metric_id: str) -> MetricDefinition:
        """Return one definition or raise MetricNotFound."""
        ...

    def list_ids(self) -> frozenset[str]:
        """Every known metric id, for validation before a query is attempted."""
        ...