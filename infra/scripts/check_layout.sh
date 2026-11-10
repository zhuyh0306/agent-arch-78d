#!/usr/bin/env bash
# Day 2 layout guard: fail fast when the five-layer skeleton drifts.
set -euo pipefail

cd "$(dirname "$0")/../.."

need=(apps/api apps/web packages/contracts skills/retrieval
      eval/datasets infra/scripts docs/adr)

for p in "${need[@]}"; do
  [ -d "$p" ] || { echo "MISSING $p"; exit 1; }
done

[ -f pnpm-workspace.yaml ] || { echo "MISSING workspace"; exit 1; }
[ -f apps/api/pyproject.toml ] || { echo "MISSING pyproject"; exit 1; }
[ ! -f pyproject.toml ] || { echo "ROOT pyproject.toml must not exist"; exit 1; }

echo "layout ok"
