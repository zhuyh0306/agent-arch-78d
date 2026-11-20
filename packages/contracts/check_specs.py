#!/usr/bin/env python3
"""Structural gate for the five Day 14 contracts and the failure-code table.

What it proves (and, deliberately, what it does not):

1. every ``specs/*.schema.json`` is itself a valid JSON Schema document;
2. the five required task types exist, one file each, and each declares the
   matching ``task_type`` constant;
3. ``failure_codes.yaml`` and ``common.schema.json#/$defs/FailureCodeName``
   carry exactly the same codes, in the same order;
4. every contract's ``failure_codes`` is a non-empty *proper* subset of that
   table, with no duplicates;
5. the five subsets together cover the whole table, so a newly added code
   cannot sit unclaimed by any contract;
6. every ``$ref`` resolves, and no contract declares a field twice;
7. the metric ids referenced by the example payloads exist in
   ``metrics_dictionary.yaml``.

It does NOT validate example payloads against their schemas -- that is
``python/test_contract_specs.py``. A checker that validated data would be a
validator, not a gate; the two are kept apart on purpose.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import yaml
from jsonschema import Draft202012Validator
from jsonschema.exceptions import SchemaError

ROOT = Path(__file__).resolve().parent
SPECS = ROOT / "specs"
COMMON = SPECS / "common.schema.json"
FAILURE_TABLE = ROOT / "failure_codes.yaml"
METRICS = ROOT / "metrics_dictionary.yaml"
EXAMPLES = SPECS / "examples"

REQUIRED_TASKS = ("compare", "attribution", "trend", "anomaly", "forecast")


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def iter_schema_nodes(node, path="$"):
    """Yield every (path, dict) schema node so we can find consts and refs."""
    if isinstance(node, dict):
        yield path, node
        for key, value in node.items():
            yield from iter_schema_nodes(value, f"{path}.{key}")
    elif isinstance(node, list):
        for index, value in enumerate(node):
            yield from iter_schema_nodes(value, f"{path}[{index}]")


def check_schema_validity(docs: dict[str, dict]) -> list[str]:
    errors: list[str] = []
    for name, doc in docs.items():
        try:
            Draft202012Validator.check_schema(doc)
        except SchemaError as exc:
            errors.append(f"{name}: invalid JSON Schema: {exc.message}")
    return errors


def check_task_type(docs: dict[str, dict]) -> list[str]:
    errors: list[str] = []
    for task in REQUIRED_TASKS:
        if task not in docs:
            errors.append(f"compare: missing specs/{task}.schema.json")
            continue
        consts = [node.get("const") for _, node in iter_schema_nodes(docs[task].get("properties", {}).get("task_type", {}))]
        if consts != [task]:
            errors.append(f"{task}: task_type.const must be exactly '{task}', got {consts}")
    extra = sorted(set(docs) - set(REQUIRED_TASKS) - {"common"})
    if extra:
        errors.append(f"unexpected contract files in specs/: {extra}")
    return errors


def check_failure_table(docs: dict[str, dict], table: dict) -> list[str]:
    errors: list[str] = []
    enum = docs["common"]["$defs"]["FailureCodeName"]["enum"]
    codes = [item["code"] for item in table["codes"]]
    if codes != enum:
        missing = [c for c in enum if c not in codes]
        stale = [c for c in codes if c not in enum]
        errors.append(
            f"failure code drift: enum-only={missing} table-only={stale} "
            "(common.schema.json #/$defs/FailureCodeName is the machine truth)"
        )
    if len(set(codes)) != len(codes):
        errors.append("failure_codes.yaml has duplicate code entries")

    axes = {axis["id"] for axis in table["axes"]}
    for item in table["codes"]:
        if item.get("axis") not in axes:
            errors.append(f"{item['code']}: unknown axis {item.get('axis')}")
        for key in ("severity", "http", "when", "action"):
            if not item.get(key):
                errors.append(f"{item['code']}: missing {key}")

    covered: set[str] = set()
    for task in REQUIRED_TASKS:
        if task not in docs:
            continue
        sidecar = SPECS / f"{task}.failure_codes.json"
        if not sidecar.is_file():
            errors.append(f"{task}: missing specs/{task}.failure_codes.json")
            continue
        subset = json.loads(sidecar.read_text(encoding="utf-8"))
        if not isinstance(subset, list) or not subset:
            errors.append(f"{task}: failure_codes subset must be a non-empty list")
            continue
        if len(set(subset)) != len(subset):
            dup = sorted({c for c in subset if subset.count(c) > 1})
            errors.append(f"{task}: duplicate failure_codes {dup}")
        unknown = [c for c in subset if c not in enum]
        if unknown:
            errors.append(f"{task}: failure_codes not in the table: {unknown}")
        if set(subset) >= set(enum):
            errors.append(f"{task}: failure_codes must be a proper subset, currently covers the whole table")
        # The subset is file-level metadata, never a runtime field: the payload
        # schemas reject unknown fields, so keeping it there made every legal
        # payload fail validation.
        if "failure_codes" in docs[task].get("properties", {}):
            errors.append(f"{task}: failure_codes must not be a payload property (it is contract metadata)")
        covered |= set(subset)

    unclaimed = [c for c in enum if c not in covered]
    if unclaimed:
        errors.append(f"codes claimed by no contract: {unclaimed}")
    return errors


def check_refs(docs: dict[str, dict]) -> list[str]:
    """Every $ref must point at a sibling schema file and resolve inside it."""
    errors: list[str] = []
    for name, doc in docs.items():
        for path, node in iter_schema_nodes(doc):
            ref = node.get("$ref")
            if not ref:
                continue
            file_part, _, pointer = ref.partition("#")
            # docs is keyed by stem ("common"), refs name files ("common.schema.json")
            target = (file_part or f"{name}.schema.json").removesuffix(".json").removesuffix(".schema")
            if target not in docs:
                errors.append(f"{name}{path}: dangling $ref {ref} (no sibling schema {target!r})")
                continue
            if not pointer:
                continue
            node_target = docs[target]
            # NB: strip("/") would also eat the leading "$" of "$defs"; drop only the slash.
            for part in pointer.lstrip("/").split("/"):
                part = part.replace("~1", "/").replace("~0", "~")
                if not isinstance(node_target, dict) or part not in node_target:
                    errors.append(f"{name}{path}: $ref {ref} does not resolve")
                    break
                node_target = node_target[part]
    return errors


def check_duplicate_properties(docs: dict[str, dict]) -> list[str]:
    """Detect duplicate keys anywhere in a schema file.

    ``json.loads`` keeps the last duplicate silently, so a field declared twice
    would look fine; we re-read with an object_pairs_hook that reports it.
    """
    errors: list[str] = []

    def hook(pairs):
        seen: set[str] = set()
        for key, _ in pairs:
            if key in seen:
                duplicate_keys.add(key)
            seen.add(key)
        return dict(pairs)

    for name in docs:
        duplicate_keys: set[str] = set()
        raw = (SPECS / f"{name}.schema.json").read_text(encoding="utf-8")
        json.loads(raw, object_pairs_hook=hook)
        if duplicate_keys:
            errors.append(f"{name}: duplicate JSON keys {sorted(duplicate_keys)}")
    return errors


def check_example_metrics(docs: dict[str, dict]) -> list[str]:
    errors: list[str] = []
    if not EXAMPLES.is_dir():
        return errors
    known = {m["id"] for m in yaml.safe_load(METRICS.read_text(encoding="utf-8"))["metrics"]}
    for path in sorted(EXAMPLES.glob("*.json")):
        payload = load_json(path)
        metric = payload.get("metric")
        if metric and metric not in known:
            errors.append(f"examples/{path.name}: metric '{metric}' not in metrics_dictionary.yaml")
    return errors


def main() -> int:
    docs: dict[str, dict] = {p.stem.replace(".schema", ""): load_json(p) for p in sorted(SPECS.glob("*.schema.json"))}
    table = yaml.safe_load(FAILURE_TABLE.read_text(encoding="utf-8"))

    errors: list[str] = []
    errors += check_schema_validity(docs)
    errors += check_task_type(docs)
    errors += check_refs(docs)
    errors += check_duplicate_properties(docs)
    if "common" in docs:
        errors += check_failure_table(docs, table)
    errors += check_example_metrics(docs)

    enum = docs.get("common", {}).get("$defs", {}).get("FailureCodeName", {}).get("enum", [])
    print(f"contracts: {sorted(set(docs) - {'common'})}")
    print(f"failure codes: {len(enum)} ({len(table['codes'])} in table)")
    for task in REQUIRED_TASKS:
        sidecar = SPECS / f"{task}.failure_codes.json"
        subset = json.loads(sidecar.read_text(encoding="utf-8")) if sidecar.is_file() else []
        print(f"  {task:<12}{len(subset):>2} codes")

    for error in errors:
        print(f"FAIL {error}")
    if errors:
        return 1
    print("contract specs ok")
    return 0


if __name__ == "__main__":
    sys.exit(main())