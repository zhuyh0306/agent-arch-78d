# db · 本地业务库

Day 13 的指标字典需要 8 张源表，这里提供可重复执行的 schema 与演示数据。

- 数据库：`dataagent`（独立于 Langfuse 的 `postgres` 库）
- schema：`app`
- 运行角色：`app_rw`（`NOLOGIN` + `NOBYPASSRLS`，非表 owner）
- 所有租户表：`tenant_id NOT NULL` + `ENABLE/FORCE ROW LEVEL SECURITY` + permissive 放行 + restrictive 租户收窄

## 文件

| 文件 | 作用 |
|---|---|
| `001_tenant_schema.sql` | 建 schema、9 张表、索引、角色、RLS 策略 |
| `002_seed_demo.sql` | tenant-a / tenant-b 的确定性演示数据，可重复执行 |
| `apply.sh` | 建库并依次应用上面两份 SQL |
| `verify.sh` | 打印表数、租户隔离、无上下文、跨租户写入、超级用户绕过 |

## 运行

```bash
cd infra
podman compose up -d postgres

cd db
./apply.sh
./verify.sh
```

预期 `verify.sh`：

- `app_tables = 9`
- tenant-a 看到 3 张订单，查 tenant-b 返回 0 行
- tenant-a 的 GMV = `480.00`
- tenant-b 看到 1 张订单
- 未设置 `app.tenant_id` 时返回 0 行
- tenant-a 写 tenant-b 的订单被 restrictive 策略拒绝
- 超级用户看到全部 4 张订单

## 规则

- 迁移只增不改；改表写 `003_*.sql`，不要回头改 `001`。
- 运行时角色 `app_rw` 不是 owner，也不能有 `BYPASSRLS`；迁移用 `postgres`。
- 应用每个事务内 `SET LOCAL app.tenant_id = '<tenant>'`，禁止 session 级 `SET`。
- 新表必须同时带 `tenant_id`、RLS 策略与至少一条越权用例；否则视为未完成（风险 R9）。
- 这里的 schema 服务于 Day 13 指标字典；字段变更先改 `packages/contracts/metrics_dictionary.yaml`，再写迁移。