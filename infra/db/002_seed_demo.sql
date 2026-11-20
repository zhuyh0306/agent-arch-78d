-- Small deterministic dataset for tenant isolation checks and metric sanity.
-- Safe to re-run: every insert uses ON CONFLICT DO NOTHING.

INSERT INTO app.tenants (tenant_id, name) VALUES
  ('tenant-a', 'Tenant A'),
  ('tenant-b', 'Tenant B')
ON CONFLICT DO NOTHING;

INSERT INTO app.customers (tenant_id, customer_id, first_order_at) VALUES
  ('tenant-a', 'a-c1', '2026-11-01 10:00:00+08'),
  ('tenant-a', 'a-c2', '2026-11-02 11:00:00+08'),
  ('tenant-b', 'b-c1', '2026-11-01 09:00:00+08')
ON CONFLICT DO NOTHING;

INSERT INTO app.products (tenant_id, sku_id, name, category, list_price, launch_date, status) VALUES
  ('tenant-a', 'a-p1', '基础款T恤', '服装', 120, '2026-10-01', 'active'),
  ('tenant-a', 'a-p2', '帆布包', '配件', 60, '2026-10-15', 'active'),
  ('tenant-b', 'b-p1', 'B款卫衣', '服装', 80, '2026-10-01', 'active')
ON CONFLICT DO NOTHING;

INSERT INTO app.orders
  (tenant_id, order_id, customer_id, status, channel, region, paid_at, gross_amount, discount_amount, shipping_fee, tax_amount)
VALUES
  ('tenant-a', 'a-o1', 'a-c1', 'completed', 'web', '华东', '2026-11-01 10:00:00+08', 250, 20, 10, 20),
  ('tenant-a', 'a-o2', 'a-c2', 'refunded',  'web', '华东', '2026-11-02 11:00:00+08', 100, 0, 0, 10),
  ('tenant-a', 'a-o3', 'a-c1', 'paid',      'app', '华南', '2026-11-03 12:00:00+08', 80, 20, 5, 5),
  ('tenant-b', 'b-o1', 'b-c1', 'completed', 'web', '华北', '2026-11-01 09:00:00+08', 240, 0, 0, 20)
ON CONFLICT DO NOTHING;

INSERT INTO app.order_items
  (tenant_id, order_id, line_id, sku_id, qty, unit_price, list_amount, discount_amount, cost_amount)
VALUES
  ('tenant-a', 'a-o1', 1, 'a-p1', 2, 100, 240, 20, 50),
  ('tenant-a', 'a-o1', 2, 'a-p2', 1, 50, 60, 0, 20),
  ('tenant-a', 'a-o2', 1, 'a-p1', 1, 100, 120, 0, 50),
  ('tenant-a', 'a-o3', 1, 'a-p2', 2, 40, 120, 20, 20),
  ('tenant-b', 'b-o1', 1, 'b-p1', 3, 80, 240, 0, 40)
ON CONFLICT DO NOTHING;

INSERT INTO app.refunds (tenant_id, refund_id, order_id, amount, status, created_at, completed_at) VALUES
  ('tenant-a', 'a-r1', 'a-o2', 100, 'completed', '2026-11-03 09:00:00+08', '2026-11-04 15:00:00+08')
ON CONFLICT DO NOTHING;

INSERT INTO app.inventory_snapshots
  (tenant_id, snapshot_date, sku_id, on_hand_qty, available_qty, inventory_cost)
VALUES
  ('tenant-a', '2026-11-01', 'a-p1', 10, 8, 500),
  ('tenant-a', '2026-11-01', 'a-p2', 5, 5, 100),
  ('tenant-b', '2026-11-01', 'b-p1', 20, 18, 800)
ON CONFLICT DO NOTHING;

INSERT INTO app.shipments (tenant_id, shipment_id, order_id, status, shipped_at, delivered_at) VALUES
  ('tenant-a', 'a-sh1', 'a-o1', 'delivered', '2026-11-02 09:00:00+08', '2026-11-03 18:00:00+08'),
  ('tenant-a', 'a-sh2', 'a-o2', 'delivered', '2026-11-03 09:00:00+08', '2026-11-04 18:00:00+08'),
  ('tenant-a', 'a-sh3', 'a-o3', 'shipped',   '2026-11-04 09:00:00+08', NULL),
  ('tenant-b', 'b-sh1', 'b-o1', 'delivered', '2026-11-02 09:00:00+08', '2026-11-03 18:00:00+08')
ON CONFLICT DO NOTHING;

INSERT INTO app.sessions (tenant_id, session_id, visitor_id, started_at, converted_order_id) VALUES
  ('tenant-a', 'a-s1', 'a-v1', '2026-11-01 09:50:00+08', 'a-o1'),
  ('tenant-a', 'a-s2', 'a-v2', '2026-11-02 10:50:00+08', 'a-o2'),
  ('tenant-a', 'a-s3', 'a-v3', '2026-11-03 11:50:00+08', NULL),
  ('tenant-b', 'b-s1', 'b-v1', '2026-11-01 08:50:00+08', 'b-o1')
ON CONFLICT DO NOTHING;