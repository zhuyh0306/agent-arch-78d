# Day 13｜领域建模与指标字典（120min）

日期：2026-11-19
用时：约 105 / 120
今日验收物：`packages/contracts/metrics_dictionary.yaml`（20 条）+ 可跑的校验器

## 精读笔记（3 条，能复述才算）

1. **指标定义不是文档，是语义契约，要和 schema、lineage 放在同一层**
   - OpenMetadata 首页把它自己描述成「metadata、meaning、memory 三层合一的 context layer」：schema / 表 / 列 / 管道 / owner / lineage 是 metadata；glossary、指标定义、业务语义是 meaning；修正、决策、审批是 memory。它服务的不只是人，还有 AI agent。
   - 对本项目：指标字典不能散落在提示词或周报里。它要成为 Agent、SQL、评测共用的同一份定义，放在 `packages/contracts/`，改口径先改这里。
   - 落点：`packages/contracts/metrics_dictionary.yaml`。

2. **lineage 的最小单位是 dataset / job / run；没有 source，就没有根因**
   - OpenLineage 首页的定义：跟踪 datasets、jobs、runs 的元数据，通过标准 API 收集 lineage event，回答「问题从哪来、改这个会影响谁」。
   - 首页只把 dataset 作为三个原语之一点名，没有展开字段定义；精确的 facet / namespace 要到规范里看，本文不冒充读全。
   - 对本项目：每条指标必须写 `source`（表、字段、状态过滤）。没有 source 的指标，Agent 只能编；出了问题也无法沿 lineage 回查。
   - 落点：字典的 `source` 字段；后续接 OpenLineage 时把指标映射到 dataset。

3. **指标字典四件套：定义 / 公式 / 口径陷阱 / 数据源；顺序不能反**
   - 先定义「算的是什么」，再写公式；先写清陷阱，再写数据源。反过来会写出「公式很漂亮但业务不认」的指标。
   - 今天标了 3 个最容易算错的：
     - **GMV**：含税/不含税、含运费、退款与取消是否扣、按下单还是支付时间。
     - **毛利率**：分子分母含税口径不一致、成本是否含运费/分摊、退款是否冲减。
     - **动销率**：分母是期初有货还是期间任意有货、卖出 1 件就算动销、新品上架时间。
   - 面试题「销售额含税还是不含税」的正确答案不是「都行」，而是「口径写在字典里，全链路只认这一份」。
   - 落点：字典 20 条，`miscalculation_risk: high` 恰好 3 条。

## 扫读：模块归属

| 产出 | 归属模块 | 一句话判断依据 |
|---|---|---|
| `metrics_dictionary.yaml` | packages/contracts | Agent / SQL / 评测共用的语义契约 |
| `check_metrics.py` | packages/contracts | 字典的结构门禁，防止缺字段、重复 id、风险数漂移 |
| 指标定义与陷阱 | contracts + docs | 是业务语义，不是提示词文案 |
| `source` 字段 | contracts → 后续 lineage | 接 OpenLineage 时映射到 dataset |
| 指标取数 SQL | skills/sql（后续） | 只认字典里的口径，不另写一套 |
| 指标问答提示词 | skills/prompts（后续） | 从字典注入定义，不靠模型记忆 |

## 产出

- `packages/contracts/metrics_dictionary.yaml`：20 条零售指标，覆盖销售规模 / 销售效率 / 售后 / 价格 / 盈利 / 库存 / 流量 / 用户 / 履约；每条含定义、公式、单位、粒度、时间窗口、数据源、口径陷阱、算错风险。
- `packages/contracts/python/check_metrics.py`：校验 20 条、id 唯一、必填字段、陷阱非空、风险取值合法、`high` 恰好 3 条。
- 3 条高风险：`gmv`、`gross_margin`、`sell_through_rate`。

## 验证

| 检查 | 命令 | 结果 |
|---|---|---|
| 字典结构 | `py311 packages/contracts/python/check_metrics.py` | `metrics: 20`；`high-risk: ['gmv', 'gross_margin', 'sell_through_rate']`；`metrics dictionary ok` |
| 分类分布 | 同上 | 销售规模 3 / 销售效率 3 / 售后 2 / 价格 1 / 盈利 3 / 库存 5 / 流量 1 / 用户 1 / 履约 1 |
| 数据源状态 | 同上 | `source_status: local_created`（本地 `dataagent` 库已建） |
| 结构漂移会红 | 临时删 1 条重跑 | `FAIL expected 20 metrics, got 19`，退出码 1 |
| 业务表 | `cd infra/db && ./apply.sh` | 9 张表、RLS、种子数据创建成功；重跑 `INSERT 0 0`，幂等 |
| RLS 策略 / 角色 | psql 检查 | `tables=9`、`policies=18`、`app_rw super=false bypassrls=false` |
| 租户隔离 | `cd infra/db && ./verify.sh` | tenant-a 3 单 / tenant-b 1 单；跨租户 0 行；跨租户写入被拒；GMV 480.00 |
| 布局未漂移 | `bash infra/scripts/check_layout.sh` | `layout ok` |

## 补做：本地业务库已建（同日）

指标字典的 `source` 不再停留在「建议口径」，已在本地独立库落地：

- 数据库 `dataagent`，schema `app`，共 9 张表：`tenants` / `customers` / `products` / `orders` / `order_items` / `refunds` / `inventory_snapshots` / `shipments` / `sessions`。
- 每张表 `tenant_id NOT NULL`，`ENABLE` + `FORCE ROW LEVEL SECURITY`，permissive 放行 + restrictive 租户策略；运行角色 `app_rw` 非 owner、`NOBYPASSRLS`。
- 迁移与种子可重复执行：`infra/db/apply.sh`；隔离证据：`infra/db/verify.sh`。
- 复测结果：tenant-a 3 单、tenant-b 1 单、跨租户查询 0 行、跨租户写入被 `orders_isolation` 拒绝、无上下文 0 行、超级用户 4 单（绕过）、tenant-a GMV 480.00。
- 未使用 Langfuse 的 `postgres` 库；业务数据在独立 `dataagent` 库。

## 与课程文档的偏差（主动讲出来）

1. 计划只写文件名 `metrics_dictionary.yaml`，没给目录；本文放在 `packages/contracts/`，因为它要被 Agent、SQL、评测共同引用，属于契约而不是文档。
2. OpenMetadata 首页是 2.1 的产品介绍，信息偏营销；本文只取「metadata / meaning / memory」与 schema-first 两条，不引用未验证的功能清单。
3. OpenLineage 首页只点名 datasets / jobs / runs，没有展开 dataset 的字段定义；笔记明确标了「精确字段看规范」，没有把首页当规范。
4. 20 条指标是覆盖零售核心链路的选择，不是行业标准全集；`source` 里的表与字段已在本地 `dataagent/app` 落地（见补做），云端库仍以契约为准再迁移。
5. 只标了 3 条 high：GMV、毛利率、动销率。库存周转率同样容易算错，但按计划只留 3 条 high，其余用详细 pitfalls 兜住。
6. 没有真实数据，公式只做口径表达，没有用 SQL 跑过；这是设计稿，不是已验证的数仓实现。

## 三行收尾

- 卡点：指标最容易写成「公式 + 一句解释」，但真正会出错的是分母口径、时间窗口、含税/含运费与退款处理；这些不写清，公式再对也没用。
- 绕过：把每条指标强制拆成定义 / 公式 / 单位 / 粒度 / 时间窗口 / 数据源 / 陷阱七段，再用校验器保证 20 条与 3 条 high 不漂移。
- 下次：写指标先问「谁用它、在哪个时间窗口、分母是什么、退款怎么处理」，四个答案没有就不写公式。

## 已知限制

- 本地 `dataagent` 库已建 9 张表并对齐字典；云端 / 生产库尚未建，部署时需重放迁移。
- 公式没有在真实数据上跑过；分母为 0、退款跨期、部分退款等边界未做数据测试。
- 未定义每个指标的业务 owner 与复核周期；字典目前只有单一维护者。
- 动销率的「动销」阈值暂定为「卖出至少 1 件」，未与业务确认。
- 未接 OpenMetadata / OpenLineage；`source` 只是字符串，不是真正的 dataset 引用。
- 分类与命名是当前设计，后续接指标平台时可能需要映射。

## 验收

- [x] 20 条指标齐全，字段完整
- [x] 每条都有定义 / 公式 / 口径陷阱 / 数据源
- [x] 标出 3 个最容易算错的指标
- [x] 校验器可运行，结构漂移会退出码 1
- [x] 产物入 `packages/contracts/`，命名可检索
- [x] 3 行 notes（卡点 / 绕过 / 下次）已写
- [x] 本地表结构已按字典建立（`dataagent/app`）
- [ ] 云端库迁移（部署时）
- [ ] 口述自测（由本人完成）