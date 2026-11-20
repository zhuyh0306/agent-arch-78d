"""The metric dictionary as a repository -- read from the Day 13 YAML.

This is where the low-level detail (a YAML file on disk, its schema) is
absorbed. The agent only ever sees ``MetricDefinition`` objects, so moving the
dictionary to Postgres or to an OpenMetadata API later changes this file alone.

The file is read once at construction and cached: the dictionary changes when
someone edits it and restarts the process, not per request.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path

import yaml

from dataagent.agent.ports.repo import MetricDefinition, MetricNotFound


class YamlMetricRepository:
    """Satisfies MetricRepositoryPort from a metrics_dictionary.yaml."""

    def __init__(self, path: Path) -> None:
        self.path = path
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
        entries = raw.get("metrics") if isinstance(raw, Mapping) else None
        if not entries:
            raise ValueError(f"no metrics found in {path}")
        self._definitions: dict[str, MetricDefinition] = {}
        for entry in entries:
            definition = MetricDefinition.from_mapping(entry)
            self._definitions[definition.id] = definition

    def get(self, metric_id: str) -> MetricDefinition:
        try:
            return self._definitions[metric_id]
        except KeyError:
            raise MetricNotFound(metric_id) from None

    def list_ids(self) -> frozenset[str]:
        return frozenset(self._definitions)

    def __len__(self) -> int:
        return len(self._definitions)

    def __repr__(self) -> str:
        return f"YamlMetricRepository({json.dumps(str(self.path))}, {len(self)} metrics)"