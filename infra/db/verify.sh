#!/usr/bin/env bash
# Print isolation evidence for the local business database.
set -u
cd "$(dirname "$0")"

CONTAINER="${PG_CONTAINER:-agent-lab-day01_postgres_1}"
DB="${DB_NAME:-dataagent}"

podman exec -i "$CONTAINER" psql -U postgres -d "$DB" -v ON_ERROR_STOP=0 <<'SQL'
\echo '--- tables ---'
SELECT count(*) AS app_tables
FROM information_schema.tables
WHERE table_schema = 'app';

\echo '--- as app_rw, tenant-a ---'
SET ROLE app_rw;
BEGIN;
SET LOCAL app.tenant_id = 'tenant-a';
SELECT count(*) AS tenant_a_orders FROM app.orders;
SELECT count(*) AS tenant_b_rows_visible FROM app.orders WHERE tenant_id = 'tenant-b';
SELECT COALESCE(sum(gross_amount + shipping_fee + tax_amount), 0) AS tenant_a_gmv
FROM app.orders
WHERE status IN ('paid', 'shipped', 'completed', 'refunded');
COMMIT;

\echo '--- as app_rw, tenant-b ---'
BEGIN;
SET LOCAL app.tenant_id = 'tenant-b';
SELECT count(*) AS tenant_b_orders FROM app.orders;
COMMIT;

\echo '--- no tenant context (fail closed) ---'
BEGIN;
SELECT count(*) AS no_context_orders FROM app.orders;
COMMIT;

\echo '--- cross-tenant insert (expected error) ---'
BEGIN;
SET LOCAL app.tenant_id = 'tenant-a';
INSERT INTO app.orders (tenant_id, order_id, status, gross_amount)
VALUES ('tenant-b', 'x-o1', 'paid', 1);
ROLLBACK;
RESET ROLE;

\echo '--- superuser (expected bypass) ---'
SELECT count(*) AS superuser_orders FROM app.orders;
SQL