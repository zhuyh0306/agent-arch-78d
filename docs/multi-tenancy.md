# 多租户与权限模型（Day 11）

> 一句话：多租户不是加一个 `tenant_id` 字段，而是让这个字段在请求、DB、向量库、日志、记忆五跳都不可丢、不可被客户端改写。

## 1. 结论

- **隔离方案**：共享 schema + PostgreSQL 行级安全（RLS）作为当前基线；运行角色非表 owner、无 `BYPASSRLS`，表上 `FORCE ROW LEVEL SECURITY`；策略是**一条 permissive 放行 + 一条 restrictive 收窄租户**，只有 restrictive 会默认全拒。
- **租户来源**：只从已验证的 token / session 解析，请求体和 query 参数里的 tenant 一律视为不可信输入。
- **纵深防御**：应用层上下文 + RLS + 向量 filter + 记忆分区 + 日志作用域，五层各自校验，任何一层都不假设另一层已经做过。
- **升级条件**：出现合规要求、租户数或数据量超出共享实例承载、需要按租户独立扩缩 / 迁移时，再切 schema-per-tenant 或 DB-per-tenant，并新写 ADR。

## 2. 威胁模型

| # | 攻击 | 目标 | 对策层 |
|---|---|---|---|
| 1 | 已认证的 tenant-a 直接查 tenant-b 的数据 | 业务库 | RLS + 应用上下文 |
| 2 | 请求体 / header 伪造 tenant | 入口 | 只信 token，忽略客户端 tenant |
| 3 | 向量检索不注入 tenant filter | 向量库 | 服务端强制注入 filter |
| 4 | 记忆写到 / 读到别的租户分区 | 长期记忆 | 分区键 + 双向校验 |
| 5 | 按别的租户查日志 / Trace | 可观测 | 日志带 tenant 标签 + 查询作用域 |

还有两类运维风险不在 5 条用例里，但必须写进制度：表 owner / 超级用户 / `BYPASSRLS` 角色会绕过 RLS；连接池里用 session 级 `SET` 会把租户上下文泄漏给下一个请求。

## 3. 零信任底线

NIST SP 800-207 的 Abstract 给出三条与今天直接相关的判断：

1. **不因网络位置或资产归属给予隐式信任**：内网、本机、同 VPC 都不是免检理由；每个请求都要重新认证与授权。
2. **认证与授权是离散动作**：在建立资源会话之前分别执行，不能靠「登录过一次」推断后续请求都合法。
3. **保护对象是资源，不是网段**：租户隔离要落到每条数据、每次检索、每条日志，而不是只在入口划一条网络边界。

对应到本项目：Policy Engine 做判断，Policy Administrator 下发策略，Policy Enforcement Point（PEP）在 Gateway、工具网关、DB 访问层、向量检索、记忆读写、日志查询各拦一次。PEP 不判断策略，只执行；判断集中在控制面。

## 4. 隔离三级：选哪个

| 方案 | 隔离强度 | 运维成本 | 迁移成本 | 适用 | 主要风险 |
|---|---|---|---|---|---|
| DB per tenant | 最强 | 每租户一套实例 / 连接 / 备份 | 高 | 强合规、租户数少、需要独立扩缩 | 成本与运维随租户线性增长 |
| Schema per tenant | 强 | 中；每租户一套表与迁移 | 中 | 租户数中等、需要较硬边界 | 迁移脚本要按 schema 跑，跨租户统计麻烦 |
| 共享 schema + RLS | 中 | 低；一套表与迁移 | 低 | 单维护者、租户数少、数据量可控 | 策略写错或角色绕过即失效 |

**当前选择：共享 schema + RLS。** 理由：

- 维护者 1 人，Postgres 已经同时承载业务与 Langfuse 元数据，再为每个租户起库 / 起 schema 会把运维成本放大。
- 租户数量与数据量尚未出现必须物理隔离的信号；先用可测试的逻辑隔离，把真实痛点留到出现时再升级。
- RLS 的风险是「写错或绕过」，不是「能力不够」；用非 owner 运行角色、`FORCE RLS`、restrictive 策略和 5 条用例把它变成可验证的门禁。

## 5. `tenant_id` 五跳

| 跳 | 带什么 | 强制点 | 失败时 |
|---|---|---|---|
| 请求 | 已验证 token 中的 tenant | Gateway 解析后写入请求上下文；忽略 body / query 里的 tenant | 400 / 403，不进入业务逻辑 |
| DB | 行上的 `tenant_id` | RLS 策略 + 应用 `WHERE tenant_id = ...` 双保险 | 查询返回 0 行；写入被 `WITH CHECK` 拒绝 |
| 向量库 | payload 中的 `tenant_id` | 检索服务端注入 filter；客户端 filter 不能覆盖或删除它 | 拒绝检索，不返回近似结果 |
| 日志 / Trace | 每条记录的 `tenant_id` 标签 | 查询 API 强制作用域；审计角色显式提权 | 返回空 / 403，并记审计事件 |
| 记忆 | 分区键 `tenant_id` | 写入与读取双向校验；mem0 metadata 必须带 | 拒绝读写 |

缺任何一跳都不是「少一个字段」，而是一类可复现的越权路径。

## 6. RLS 落地要点

示意 SQL（表名与角色名按实际替换）：

```sql
-- 运行角色不能是表 owner，也不能有 BYPASSRLS
CREATE ROLE app_rw NOBYPASSRLS;

ALTER TABLE orders ENABLE ROW LEVEL SECURITY;
ALTER TABLE orders FORCE ROW LEVEL SECURITY;

-- 先放行角色，再用 restrictive 收窄；只有 restrictive 会默认全拒
CREATE POLICY orders_app_rw ON orders
  AS PERMISSIVE
  TO app_rw
  USING (true) WITH CHECK (true);

CREATE POLICY orders_tenant_isolation ON orders
  AS RESTRICTIVE
  TO app_rw
  USING (tenant_id = nullif(current_setting('app.tenant_id', true), ''))
  WITH CHECK (tenant_id = nullif(current_setting('app.tenant_id', true), ''));
```

每个事务内设置上下文，禁止 session 级设置：

```sql
BEGIN;
SET LOCAL app.tenant_id = 'tenant-a';
SELECT ... FROM orders;
COMMIT;
```

必须知道的坑（均来自 PostgreSQL 官方文档）：

1. **默认拒绝**：表启用 RLS 但没有任何策略时，普通访问看不到也改不了任何行。
2. **owner 绕过**：表 owner 通常不受 RLS 约束；需要 `FORCE ROW LEVEL SECURITY` 才会被策略约束。迁移用 owner，运行用 `app_rw`。
3. **超级用户与 `BYPASSRLS` 永远绕过**：运行角色不能带这个属性，审计 / 备份角色单独管理。
4. **permissive 用 OR，restrictive 用 AND**：租户隔离用 restrictive，避免未来新增一条 permissive 策略就把范围放大。但 **restrictive 不能单独存在**——只有 restrictive 时没有任何 permissive 放行，结果是默认全拒。必须先有一条 permissive 角色策略，再用 restrictive 收窄。Day 12 真实 RLS 复测第一次只写 restrictive，`tenant-a` 读到 0 行，就是这个问题。
5. **`USING` 管可见行，`WITH CHECK` 管写入行**：只写 `USING` 会出现「读不到但写得进」。
6. **`TRUNCATE`、`REFERENCES` 不受 RLS 约束**；外键与唯一约束检查也会绕过 RLS，可能形成 covert channel。
7. **连接池**：`SET LOCAL` 只在事务内有效；用 session 级 `SET` 会把租户上下文带给下一个请求。
8. **`current_setting(..., true)` 未设置时返回 NULL**，策略结果为 false，等价于拒绝；这是想要的行为，不要给它兜底默认租户。

## 7. 5 条越权用例

用例落在 `apps/api/fixtures/tenant_cases.json`，由 `apps/api/tenant_policy.py` 执行。每条攻击都对应一个必须拒绝的跳。

| ID | 攻击 | 期望 | 防线 |
|---|---|---|---|
| `db-cross-read` | tenant-a 查 tenant-b 的 orders | `DENY:TENANT_MISMATCH` | RLS + 应用 where |
| `request-forged-tenant` | 请求体把 tenant 改成 tenant-b | `DENY:TENANT_MISMATCH` | 只信 token |
| `vector-filter-dropped` | 向量检索不注入 tenant filter | `DENY:FILTER_MISSING` | 服务端强制 filter |
| `memory-cross-write` | 记忆写到别的租户分区 | `DENY:TENANT_MISMATCH` | 分区键双向校验 |
| `log-cross-query` | 按 tenant-b 查日志 / Trace | `DENY:TENANT_MISMATCH` | 查询作用域 |

另有一条对照组 `db-own-read`（tenant-a 读自己）必须 `ALLOW`，防止策略写成「一律拒绝」也算通过。

## 8. 验证

```bash
cd apps/api
/Users/zhuyonghui/miniconda3/envs/py311/bin/python -m pytest -q
/Users/zhuyonghui/miniconda3/envs/py311/bin/python tenant_policy.py
```

当前结果：`5 passed`；模拟器输出 `5 attacks denied, 1 control allowed`。

**真实 RLS 最小复测（Day 12，Postgres 16，临时库已删除）**：

| 动作 | 结果 |
|---|---|
| `app_rw` + `app.tenant_id='tenant-a'` 读 | 1 行（只有 tenant-a） |
| `app_rw` 插入自己的行 | 成功 |
| `app_rw` 未设置租户上下文读取 | 0 行（fail closed） |
| `app_rw` 跨租户插入 tenant-b | 被 `orders_tenant_isolation` 拒绝 |
| 超级用户读取 | 全部行（绕过 RLS，符合预期） |

第一次只写了 restrictive 策略，`tenant-a` 读到 0 行；补上 permissive 放行策略后才得到上表结果。这条已写进第 6 节第 4 个坑。

**本地业务库已接入（Day 13 补做）**：`dataagent` 库 / `app` schema 已按同一套策略建 9 张表（tenants / customers / products / orders / order_items / refunds / inventory_snapshots / shipments / sessions），运行角色 `app_rw` 非 owner、`NOBYPASSRLS`。`infra/db/verify.sh` 复测：tenant-a 看到 3 单、tenant-b 1 单、跨租户查询 0 行、无上下文 0 行、跨租户写入被 `orders_isolation` 拒绝、超级用户 4 单（绕过）、tenant-a GMV 480.00。

**仍未做**：连接池下的 `SET LOCAL` 行为、owner 绕过的单独复现、云端库迁移。接入新表时用同一组用例在目标表上再跑一遍，不以模拟器代替。

## 9. 迁移与退出条件

迁移顺序：

1. 业务表加 `tenant_id NOT NULL`，按现有数据回填，建 `(tenant_id, ...)` 索引；
2. 建 `app_rw` 运行角色（非 owner、`NOBYPASSRLS`），迁移继续用 owner；
3. 开 RLS + `FORCE` + restrictive 租户策略；
4. 应用改为每事务 `SET LOCAL app.tenant_id`；
5. 用 5 条用例 + 对照组在真实库上复测，再删掉任何临时绕过。

切到 schema / DB 隔离的触发条件：合规要求物理隔离、单租户数据量影响其他租户、需要按租户独立备份 / 迁移 / 扩缩。触发时新写 ADR，不直接改本文结论。

## 10. 自测

1. 为什么租户只能从 token 来，不能从请求体来？
2. RLS 写了策略却还被绕过，优先查哪三件事？
3. `USING` 和 `WITH CHECK` 各管什么？只写一个会出什么问题？
4. 向量库与记忆的隔离，为什么不能只靠「collection / 分区命名」？
5. 共享 schema + RLS 什么时候该升级？升级前需要准备什么？