#!/usr/bin/env bash
# apps/api quality gate: the checks a pull request must pass.
#
# Day 15 built the layers; this script keeps them from eroding. Without it,
# mypy and ruff were commands someone remembered to run, which means never.
#
# Each step fails the whole gate. Run order is cheapest-first so a broken
# import does not wait behind a full test run.
set -euo pipefail

cd "$(dirname "$0")"

VENV=".venv"
PY="$VENV/bin/python"

step() { printf '\n=== %s ===\n' "$1"; }

[ -x "$PY" ] || { echo "FAIL no venv at $VENV; run: uv sync --extra test"; exit 1; }

step "ruff (lint)"
"$VENV/bin/ruff" check dataagent tests main.py

step "mypy (types)"
"$VENV/bin/mypy" dataagent

step "pytest"
"$PY" -m pytest -q

printf '\napps/api gate ok\n'