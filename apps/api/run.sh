#!/usr/bin/env bash
# Start the DataAgent API. Port and log level are overridable.
set -euo pipefail

cd "$(dirname "$0")"

PORT="${PORT:-8000}"
LOG_LEVEL="${LOG_LEVEL:-info}"

exec .venv/bin/uvicorn "dataagent.api.app:build_app" \
  --factory \
  --host "${HOST:-127.0.0.1}" \
  --port "$PORT" \
  --log-level "$LOG_LEVEL"
