# Day 11｜多租户与权限模型（120min）

日期：2026-11-19
用时：约 105 / 120
今日验收物：`docs/multi-tenancy.md`（隔离选型 + `tenant_id` 五跳 + 5 条越权用例）+ 可运行的策略模拟器

## 精读笔记（3 条，能复述才算）

1. **零信任的第一句话是「不因位置给信任」，不是「上 mTLS」**
   - NIST SP 800-207 Abstract：不因物理 / 网络位置（内网 vs 互联网）或资产归属给予隐式信任；认证与授权是建立资源会话前的离散动作；保护对象是资源，不是网段。
   - 对本项目：租户只能从已验证 token / session 来；请求体、query、header 里的 tenant 都是不可信输入。内网调用同样要过 PEP。
   - 组件分工（课程与 must-master 口径）：Policy Engine 判断，Policy Administrator 下发，PEP 在 Gateway、工具网关、DB、向量检索、记忆、日志各拦一次。PEP 只执行，不做策略判断。
   - 落点：`docs/multi-tenancy.md` 第 3 节。

2. **RLS 的风险不在「能不能」，在「绕过与写错」**
   - 启用 RLS 但无策略 = 默认拒绝；但表 owner 通常绕过，超级用户与 `BYPASSRLS` 永远绕过；owner 要受约束必须 `FORCE ROW LEVEL SECURITY`。
   - permissive 策略之间用 OR，restrictive 用 AND；租户隔离应写成 restrictive，避免未来一条 permissive 把范围放大。
   - `USING` 管可见行，`WITH CHECK` 管写入行；只写 `USING` 会「读不到但写得进」。`TRUNCATE`、`REFERENCES` 不受 RLS 约束，外键 / 唯一约束检查也会绕过，可能形成 covert channel。
   - 连接池里 session 级 `SET` 会把租户上下文泄漏给下一个请求；必须 `SET LOCAL` 在事务内。
   - 落点：`docs/multi-tenancy.md` 第 6 节的 8 条坑。

3. **租户不是字段，是必须在五跳都出现的上下文**
   - 请求 → DB → 向量库 → 日志 / Trace → 记忆，缺任何一跳都是一类可复现的越权路径。
   - 共享 schema + RLS 的强度依赖策略与角色配置，所以要用「非 owner 运行角色 + FORCE + restrictive + 双保险 WHERE + 5 条用例」把它变成可验证的门禁，而不是口头约定。
   - 落点：`docs/multi-tenancy.md` 第 4–7 节；可执行用例在 `apps/api/tenant_policy.py`。

## 扫读：模块归属

| 产出 | 归属模块 | 一句话判断依据 |
|---|---|---|
| `docs/multi-tenancy.md` | docs | 隔离选型与威胁模型，是决策记录 |
| `apps/api/tenant_policy.py` | apps/api | 运行时租户边界检查的参考实现 |
| `apps/api/fixtures/tenant_cases.json` | apps/api | 5 条越权用例 + 1 条对照，随运行时测试走 |
| `apps/api/test_tenant_policy.py` | apps/api | 策略判定的回归测试 |
| RLS SQL 片段 | docs（后续 infra/db） | 目前是设计示意，接真实库时落到迁移脚本 |
| 向量 filter | skills/retrieval（Day 14） | 检索入口强制注入，客户端不可覆盖 |
| 记忆分区 | skills/retrieval / memory（Day 14） | 读写双向校验 |
| 日志作用域 | infra/observability | Trace 带 tenant 标签，查询按作用域过滤 |

## 产出

- `docs/multi-tenancy.md`：威胁模型、零信任底线、隔离三级对比与选型、`tenant_id` 五跳、RLS 示意 SQL 与 8 条坑、5 条用例、迁移顺序与退出条件。
- `apps/api/tenant_policy.py`：五跳策略模拟器，`authorize_hop()` 返回 `ALLOW` 或稳定拒绝原因。
- `apps/api/fixtures/tenant_cases.json`：5 条攻击 + 1 条对照。
- `apps/api/test_tenant_policy.py`：5 个测试。

## 验证

| 检查 | 命令 | 结果 |
|---|---|---|
| 策略测试 | `cd apps/api && py311 -m pytest -q` | `5 passed` |
| 当场演示 | `py311 tenant_policy.py` | 5 条攻击全部 DENY，1 条对照 ALLOW，退出码 0 |
| 用例齐全 | fixture | `db-cross-read` / `request-forged-tenant` / `vector-filter-dropped` / `memory-cross-write` / `log-cross-query` + 对照 |
| 判定稳定 | 代码审查 | 拒绝原因用枚举，不返回自由文本 |
| 布局未漂移 | `bash infra/scripts/check_layout.sh` | `layout ok` |

**未验证**：真实 Postgres RLS。业务表没有 `tenant_id`，也没有 `app_rw` 运行角色；目前验证的是策略判定逻辑，不是数据库执行结果。这条必须在接真实库时用同一组用例复测。

## 与课程文档的偏差（主动讲出来）

1. 最新计划只要求读 NIST Abstract；本文的 PEP / Policy Engine / Policy Administrator 分工来自课程与 `must-master.md`，没有冒充 Abstract 原文。
2. 计划要求「5 条越权用例」；这里额外加了一条 tenant-a 读自己的对照组。只有拒绝用例时，「一律拒绝」也能全绿，对照组用于防止这种假通过。
3. 计划没要求选隔离级别；本文把三级对比与当前选择写清楚，并给出升级触发条件，避免以后「默认共享 schema」变成没人负责的历史包袱。
4. RLS 策略用了 `AS RESTRICTIVE` + `FORCE ROW LEVEL SECURITY` + 非 owner 运行角色，比课程示例更严格；依据是 PostgreSQL 官方文档对 owner / `BYPASSRLS` 绕过行为的说明。
5. 没有真实建表、建角色、跑 RLS：当前仓库还没有业务表，贸然在 Langfuse 共用的 Postgres 里建演示 schema 会增加清理成本。改为纯策略模拟器，限制写明。
6. 用例落在 `apps/api` 而不是 `sandbox` 目录：仓库五层骨架没有 sandbox 层，租户校验属于 API 入口与运行时，先放在 `apps/api`，后续接工具网关时再下沉。

## 三行收尾

- 卡点：RLS 的「默认拒绝」只在启用后无策略时成立；owner、超级用户、`BYPASSRLS` 都能绕过，单看「我写了 policy」会误以为已经安全。
- 绕过：把运行角色与迁移角色分开，运行角色非 owner + `NOBYPASSRLS`，表上 `FORCE`，租户策略写成 restrictive；同时保留应用层 `WHERE` 作第二道。
- 下次：租户校验先问「这条路径的 tenant 从哪来、要带到哪去」，再写策略；不要先写 SQL 再补入口校验。

## 已知限制

- 策略模拟器只覆盖五跳的等值租户判断，没有覆盖角色提权、审计员跨租户只读、缓存 key 缺租户等场景。
- 真实 RLS 未执行；策略语法、角色权限、连接池行为都要在真实 Postgres 上复测。
- 向量库与记忆的 tenant 过滤尚未实现，当前只有接口位置的约定。
- 隔离级别选择基于单人维护与当前数据量，没有压测；租户数或合规要求变化时需要重开 ADR。
- 日志 / Trace 的租户作用域没有实现，Langfuse 里还没有 `tenant_id` 字段。

## 验收

- [x] 零信任的「不因位置给信任」讲得清，并能落到租户来源
- [x] 隔离三级（独立库 / schema / RLS）的取舍说得清
- [x] `tenant_id` 五跳齐全，缺一跳的后果说得出
- [x] 5 条越权用例在模拟器中全部拒绝，且有对照组
- [x] RLS 的 owner / `BYPASSRLS` / restrictive / `USING` vs `WITH CHECK` 坑已记录
- [x] 产物已入 `docs/` 与 `apps/api/`，命名可检索
- [x] 3 行 notes（卡点 / 绕过 / 下次）已写
- [ ] 真实 Postgres RLS 复测（接库时补做）
- [ ] 口述自测（由本人完成）