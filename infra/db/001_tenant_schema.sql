-- Day 13 business schema: every tenant-scoped table carries tenant_id and RLS.
-- Apply to the dedicated `dataagent` database, not Langfuse's `postgres` database.

DO $$
BEGIN
  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'app_rw') THEN
    CREATE ROLE app_rw NOLOGIN NOBYPASSRLS;
  END IF;
END
$$;

CREATE SCHEMA IF NOT EXISTS app;
GRANT USAGE ON SCHEMA app TO app_rw;

CREATE TABLE IF NOT EXISTS app.tenants (
  tenant_id text PRIMARY KEY,
  name text NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS app.customers (
  tenant_id text NOT NULL REFERENCES app.tenants(tenant_id),
  customer_id text NOT NULL,
  first_order_at timestamptz,
  created_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (tenant_id, customer_id)
);

CREATE TABLE IF NOT EXISTS app.products (
  tenant_id text NOT NULL REFERENCES app.tenants(tenant_id),
  sku_id text NOT NULL,
  name text NOT NULL,
  category text NOT NULL,
  list_price numeric(14, 2) NOT NULL CHECK (list_price >= 0),
  launch_date date,
  status text NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'inactive')),
  PRIMARY KEY (tenant_id, sku_id)
);

CREATE TABLE IF NOT EXISTS app.orders (
  tenant_id text NOT NULL REFERENCES app.tenants(tenant_id),
  order_id text NOT NULL,
  customer_id text,
  status text NOT NULL CHECK (status IN ('created', 'paid', 'shipped', 'completed', 'cancelled', 'refunded')),
  channel text,
  region text,
  paid_at timestamptz,
  created_at timestamptz NOT NULL DEFAULT now(),
  gross_amount numeric(14, 2) NOT NULL DEFAULT 0 CHECK (gross_amount >= 0),
  discount_amount numeric(14, 2) NOT NULL DEFAULT 0 CHECK (discount_amount >= 0),
  shipping_fee numeric(14, 2) NOT NULL DEFAULT 0 CHECK (shipping_fee >= 0),
  tax_amount numeric(14, 2) NOT NULL DEFAULT 0 CHECK (tax_amount >= 0),
  PRIMARY KEY (tenant_id, order_id),
  FOREIGN KEY (tenant_id, customer_id) REFERENCES app.customers(tenant_id, customer_id)
);

CREATE TABLE IF NOT EXISTS app.order_items (
  tenant_id text NOT NULL REFERENCES app.tenants(tenant_id),
  order_id text NOT NULL,
  line_id integer NOT NULL CHECK (line_id > 0),
  sku_id text NOT NULL,
  qty integer NOT NULL CHECK (qty > 0),
  unit_price numeric(14, 2) NOT NULL CHECK (unit_price >= 0),
  list_amount numeric(14, 2) NOT NULL CHECK (list_amount >= 0),
  discount_amount numeric(14, 2) NOT NULL DEFAULT 0 CHECK (discount_amount >= 0),
  cost_amount numeric(14, 2) NOT NULL CHECK (cost_amount >= 0),
  PRIMARY KEY (tenant_id, order_id, line_id),
  FOREIGN KEY (tenant_id, order_id) REFERENCES app.orders(tenant_id, order_id),
  FOREIGN KEY (tenant_id, sku_id) REFERENCES app.products(tenant_id, sku_id)
);

CREATE TABLE IF NOT EXISTS app.refunds (
  tenant_id text NOT NULL REFERENCES app.tenants(tenant_id),
  refund_id text NOT NULL,
  order_id text NOT NULL,
  amount numeric(14, 2) NOT NULL CHECK (amount >= 0),
  status text NOT NULL CHECK (status IN ('pending', 'completed', 'rejected')),
  created_at timestamptz NOT NULL DEFAULT now(),
  completed_at timestamptz,
  PRIMARY KEY (tenant_id, refund_id),
  FOREIGN KEY (tenant_id, order_id) REFERENCES app.orders(tenant_id, order_id)
);

CREATE TABLE IF NOT EXISTS app.inventory_snapshots (
  tenant_id text NOT NULL REFERENCES app.tenants(tenant_id),
  snapshot_date date NOT NULL,
  sku_id text NOT NULL,
  on_hand_qty integer NOT NULL CHECK (on_hand_qty >= 0),
  available_qty integer NOT NULL CHECK (available_qty >= 0),
  inventory_cost numeric(14, 2) NOT NULL CHECK (inventory_cost >= 0),
  PRIMARY KEY (tenant_id, snapshot_date, sku_id),
  FOREIGN KEY (tenant_id, sku_id) REFERENCES app.products(tenant_id, sku_id)
);

CREATE TABLE IF NOT EXISTS app.shipments (
  tenant_id text NOT NULL REFERENCES app.tenants(tenant_id),
  shipment_id text NOT NULL,
  order_id text NOT NULL,
  status text NOT NULL CHECK (status IN ('created', 'shipped', 'delivered', 'returned')),
  shipped_at timestamptz,
  delivered_at timestamptz,
  PRIMARY KEY (tenant_id, shipment_id),
  FOREIGN KEY (tenant_id, order_id) REFERENCES app.orders(tenant_id, order_id)
);

CREATE TABLE IF NOT EXISTS app.sessions (
  tenant_id text NOT NULL REFERENCES app.tenants(tenant_id),
  session_id text NOT NULL,
  visitor_id text NOT NULL,
  started_at timestamptz NOT NULL,
  converted_order_id text,
  PRIMARY KEY (tenant_id, session_id),
  FOREIGN KEY (tenant_id, converted_order_id) REFERENCES app.orders(tenant_id, order_id)
);

CREATE INDEX IF NOT EXISTS orders_tenant_paid_idx ON app.orders (tenant_id, paid_at);
CREATE INDEX IF NOT EXISTS order_items_tenant_sku_idx ON app.order_items (tenant_id, sku_id);
CREATE INDEX IF NOT EXISTS refunds_tenant_created_idx ON app.refunds (tenant_id, created_at);
CREATE INDEX IF NOT EXISTS inventory_tenant_sku_date_idx ON app.inventory_snapshots (tenant_id, sku_id, snapshot_date);
CREATE INDEX IF NOT EXISTS sessions_tenant_started_idx ON app.sessions (tenant_id, started_at);

-- RLS: permissive role policy + restrictive tenant policy, both required.
DO $$
DECLARE
  table_name text;
BEGIN
  FOREACH table_name IN ARRAY ARRAY[
    'tenants', 'customers', 'products', 'orders', 'order_items',
    'refunds', 'inventory_snapshots', 'shipments', 'sessions'
  ]
  LOOP
    EXECUTE format('ALTER TABLE app.%I ENABLE ROW LEVEL SECURITY', table_name);
    EXECUTE format('ALTER TABLE app.%I FORCE ROW LEVEL SECURITY', table_name);
    EXECUTE format('GRANT SELECT, INSERT, UPDATE, DELETE ON app.%I TO app_rw', table_name);
    EXECUTE format('DROP POLICY IF EXISTS %I ON app.%I', table_name || '_access', table_name);
    EXECUTE format('DROP POLICY IF EXISTS %I ON app.%I', table_name || '_isolation', table_name);
    EXECUTE format('CREATE POLICY %I ON app.%I AS PERMISSIVE TO app_rw USING (true) WITH CHECK (true)',
                   table_name || '_access', table_name);
    EXECUTE format($fmt$CREATE POLICY %I ON app.%I AS RESTRICTIVE TO app_rw
      USING (tenant_id = nullif(current_setting('app.tenant_id', true), ''))
      WITH CHECK (tenant_id = nullif(current_setting('app.tenant_id', true), ''))$fmt$,
                   table_name || '_isolation', table_name);
  END LOOP;
END
$$;