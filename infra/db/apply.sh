#!/usr/bin/env bash
# Apply the business schema and demo seed to the local Postgres container.
set -euo pipefail
cd "$(dirname "$0")"

CONTAINER="${PG_CONTAINER:-agent-lab-day01_postgres_1}"
DB="${DB_NAME:-dataagent}"

if ! podman ps --format '{{.Names}}' | grep -qx "$CONTAINER"; then
  echo "postgres container is not running: $CONTAINER" >&2
  echo "start it with: (cd .. && podman compose up -d postgres)" >&2
  exit 1
fi

exists=$(podman exec -i "$CONTAINER" psql -U postgres -tAc "SELECT 1 FROM pg_database WHERE datname = '$DB'")
if [ "$exists" != "1" ]; then
  podman exec -i "$CONTAINER" psql -U postgres -v ON_ERROR_STOP=1 -c "CREATE DATABASE \"$DB\""
fi

podman exec -i "$CONTAINER" psql -U postgres -d "$DB" -v ON_ERROR_STOP=1 < 001_tenant_schema.sql
podman exec -i "$CONTAINER" psql -U postgres -d "$DB" -v ON_ERROR_STOP=1 < 002_seed_demo.sql

echo "applied 001_tenant_schema.sql + 002_seed_demo.sql to $DB"