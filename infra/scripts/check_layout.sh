#!/usr/bin/env bash
# Layout guard: fail fast when the five-layer skeleton drifts.
#
# Two levels are checked:
#   1. repository layers (ADR-0002): apps / packages / skills / eval / infra
#   2. app-internal layers (ADR-0006): api / domain / agent / tools / infra
# The second level is also enforced by apps/api/tests/test_layering.py; this
# script only checks that the directories still exist, so a rename fails here
# before it fails in a test run.
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

# App-internal layering (ADR-0006).
app_layers=(dataagent/api dataagent/domain dataagent/agent dataagent/tools dataagent/infra)
for p in "${app_layers[@]}"; do
  [ -d "apps/api/$p" ] || { echo "MISSING apps/api/$p"; exit 1; }
done

echo "layout ok"