# 0004 · 存储与向量检索选型

- Status: accepted
- Date: 2026-11-10
- Deciders: 项目负责人（单人维护）
- Supersedes: —

## Context

项目需要两类能力：关系数据（事务、按用户隔离）与向量检索（语义召回）。

真实约束（与课程模板不同处逐条标注，避免把别人的前提当成自己的）：

- 维护者 1 人，无独立向量库运维经验。课程模板写「团队 5 人」，不适用。
- 向量量级预估 < 100 万，过滤以等值条件（tenant / doc_type）为主。
- Day-1 的 `infra/docker-compose.yml` 已定义 `postgres:16-alpine` 与 `qdrant v1.12.4`。但当前 podman VM 是新建的，实验台容器未运行、镜像不在本机，两者都要重新拉取。所以「Postgres 增量成本≈0」只在一个意义上成立：它本来就必须为 Langfuse 运行，业务复用它不新增服务。
- **官方 postgres 镜像不含 pgvector。** pgvector README 的 Installation 一节要求源码编译或单独安装（Docker 镜像 `pgvector/pgvector`、APT、Homebrew、PGXN 等）。复用现有实例意味着换镜像，这是一次性迁移成本，不是 0。本机尚未实测 `CREATE EXTENSION vector`，登记为待办（见 Consequences）。
- 本机 Ollama 只有 `qwen2.5:0.5b`（chat 模型），还没有 embedding 模型。课程里的 `vector(1536)` 是 OpenAI 口径，不适用本地模型；维度必须等模型选定后写进 `packages/contracts`，本文不写死。
- 规划中的 api + worker + eval 多进程写入尚未实现（`apps/api` 仍是占位）。排除 SQLite 是前瞻判断，不是已观测到的瓶颈。
- Langfuse v3 的 trace 明细在 ClickHouse，Postgres 只存元数据。「Postgres 承载 Langfuse 落库」这句话要这么说才准确。

选型依据落在 `docs/selection-matrix.csv`，权重与算法在 `infra/scripts/score_matrix.py`（成本 0.20 / 运维 0.25 / 生态 0.20 / 退出成本 0.25 / 熟悉度 0.10）。加权结果：SQLite 4.50、Postgres 4.05、PG+pgvector 3.75、Qdrant 2.95。把运维权重降到 0.10、退出成本升到 0.40 重跑，排序不变。

**SQLite 分最高却被排除**：矩阵打分衡量的是「通用好不好」，排除理由是结构性不匹配——库级写锁扛不住多进程写入，且没有 RLS，租户隔离全压在应用层。这两条是硬约束，不参与加权。SQLite 仍允许用于 `eval/` 的本地快照与单机测试。

## Decision

1. 主库使用 Postgres：业务数据 + Langfuse 元数据。trace 明细留在 ClickHouse，不混为一谈。
2. 向量检索先用 pgvector，寄生在同一 Postgres 实例。**前置条件**：把镜像换成带扩展的版本（如 `pgvector/pgvector:pg16`）并实测 `CREATE EXTENSION vector` 成功；该实测完成前不写业务检索代码。
3. 检索一律经 `skills/retrieval` 的统一接口（adapter）。业务代码不得直接持有向量库 client；向量维度、距离度量、payload 字段写入 `packages/contracts`，作为跨语言契约的一部分。
4. embedding 模型与维度在 contracts 里 pin 死。换模型 = 换维度 = 全量重灌，必须新写 ADR，不能顺手改。
5. 触发下列任一条件时切 Qdrant，并新写 ADR-0005（不改本文）：
   - 向量数 > 500 万
   - payload 过滤出现范围 / 数组 / 多字段组合
   - 需要按租户独立扩缩
6. Qdrant 保留在 compose 里作为实验基线，但业务检索不依赖它，避免「反正已经起了就顺手用」绕过阈值。
7. Temporal 暂缓，Day 28 再评估。长任务确实需要持久化编排，但现在引入等于为还不存在的需求付运维成本。

## Consequences

+ 只运维一个业务数据库；向量查询与业务查询可在同一事务内完成
+ 退出路径清晰：差异被关在一个 adapter 里，换库只改一处
+ 评测基线与业务数据同库，回归成本低
+ 100 万 × 1536 维 float32 约 6.1 GB 原始向量、含 HNSW 图约需预留 10 GB；这笔内存与 Postgres buffer 池共享预算，不用为新服务单独做容量规划（本地模型维度更低，实际更小）
- 换镜像是一次性迁移，涉及 Langfuse 元数据，需要先做备份/恢复演练
- HNSW 建索引慢且吃 `maintenance_work_mem`，写入高峰要错峰，或先批量灌数据再建索引
- 带 `WHERE` 的 HNSW 是 **post-filter**：pgvector README 明确「过滤在索引扫描之后生效」，默认 `hnsw.ef_search=40` 下匹配 10% 的行平均只返回 4 条。必须开 `hnsw.iterative_scan`（0.8+）或加大 `ef_search`，否则会出现「明明有 10 条却只回 3 条」
- 超过阈值后仍要面对一次真实迁移：数据重灌与评测基线重跑省不掉，本 ADR 只是推迟，不是消除
- 待实测：`CREATE EXTENSION vector` 是否成功、带 tenant 过滤的查询在开/关 iterative_scan 下的返回条数差异。补做日：下次拉起实验台时（不晚于 Day 16）

## Alternatives considered

- SQLite：单机零运维、矩阵分最高，但多进程写锁 + 无 RLS 结构性不匹配；限定在 eval 快照与单机测试。
- 直接上 Qdrant：已部署不等于该用。当前量级与等值过滤用不上它的强项（复杂 payload 过滤、独立扩缩），却要多养一个有状态服务的备份、升级与磁盘水位；本机 VM 仅 6 GiB 且已被其他栈占用。
- Temporal：持久化编排是真需求，但属于 Day 28 的评估项，今天只记结论。

## Superseded by

—
