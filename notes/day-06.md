# Day 6｜复盘与 M0-1 基线验收（60min）

日期：2026-11-10
用时：约 60 / 60
今日验收物：`docs/m0-1-acceptance.md`（环境绿 + 闭环通 + 基线数）+ `docs/risk-register.md` v1

## 精读笔记（3 条，能复述才算）

1. **验收项必须写成「第三人能重放的命令 + 原样输出」，否则只是自述**
   - 依据：本周四份验收物的对比。Day 3 的验证表每条都有命令与结果，Day 4 的脚本连跑两次 `diff` 一致，Day 6 的 `env_check.sh` 用退出码 0 与 `10 checks passed` 做机器判定。反例是 Day 1 只记了「10 checks passed」、没记起栈耗时，今天才发现「先 up 再立刻 check」首跑必红。
   - 落点：`docs/m0-1-acceptance.md` 的复现段 + `infra/scripts/`。「可复现」不是文档形容词，是能粘贴执行的命令。

2. **「最不满意的产出物」往往指向共性根因：把资料成立当成环境成立**
   - 依据：本周两处没做透——Day 3 的 `CREATE EXTENSION vector` 只查到「官方镜像不含 pgvector」就停了，Day 1 的栈从 colima 迁到 podman 后一直没整体复跑。共同根因不是时间不够，而是验收标准只写「跑通过一次」，没写「在目标运行时跑通过」。
   - 落点：本次把两件一起补了：podman 下 10/10 全绿，stock Postgres 的 `pg_available_extensions` 中 `vector` 计数为 0、`CREATE EXTENSION` 报缺 `vector.control`，ADR-0004 的前提从「文档说」变成「本机验过」。风险登记册的 R1/R2 就是这条根因的制度化。

3. **基线数必须成对出现：指标 + 对照 + 口径；单个数不可比较**
   - 依据：2.571 s 只有与 Day 1 的 3.163 s 并列才有意义；$7.39/月必须带上「1,000 次/天 × 30 天、Flash 谷时命中缓存」；「10/10」必须带上「起栈约 35 秒后」。另外输入 token 两次都是 41，说明 smoke 的提示没漂移；输出 29 → 34 是采样差异，不是回归。
   - 落点：验收记录里每行都有「值 + 口径」两列；成本口径留在 `eval/cost`，环境口径留在 `infra`。

## 扫读：模块归属

| 本周产出 | 归属模块 | 一句话判断依据 |
|---------|---------|---------------|
| `docs/m0-1-acceptance.md` | docs | 是验收记录，不是运行时配置 |
| `env_check.sh` / `smoke.sh` | infra | 只验证环境与链路，不参与业务逻辑 |
| 成本基线（`eval/cost`） | eval | 是基线数据与测算脚本，不属于生产代码 |
| 风险登记册 | docs | 是决策与约束的记录 |
| 延迟 / token / 内存 | Langfuse + podman stats | 指标由可观测层与运行时提供，不手抄进代码 |

## 产出

- `docs/m0-1-acceptance.md`：三项验收、四类基线数、与 Day 1 的对照、本周结论、遗留与复现命令。
- `docs/risk-register.md`：8 条风险（podman 无自启、镜像源、无 GPU、文档 403、PAT、推送阻断、成本假设、VM 内存），含缓解动作与状态。
- `infra/README.md`：补「起栈约 30–40 秒、首跑红先等健康」的实测口径。
- `docs/README.md`：把矩阵、判定表、风险登记册纳入 docs 索引。

## 验证

| 检查 | 命令 | 结果 |
|------|------|------|
| 镜像就绪 | `podman images` | 7 个缺失镜像已拉齐（clickhouse / langfuse ×2 / litellm / postgres / redis / qdrant） |
| 起栈 | `time podman compose up -d` | 17.7 s，9 个容器创建完成 |
| 首跑环境检查 | `./scripts/env_check.sh` | 7 passed / 3 failed（Langfuse、LiteLLM 未就绪），启动时序 |
| 等健康 | 轮询 `/api/public/health` 与 `/health/liveliness` | 约 30 s 后两者均 200 |
| 复跑环境检查 | `./scripts/env_check.sh` | `10 checks passed`，退出码 0 |
| 闭环 | `time ./scripts/smoke.sh` | `smoke ok`，8.46 s |
| completion 内容 | smoke 输出 | 中文答案正常，`model=fast` |
| trace | Langfuse API | `2b3ba91ae1964fa1a6028428c5d61397`，延迟 2.571 s，usage 41/34/75，cost 0 |
| pgvector 可用性 | `pg_available_extensions` / `CREATE EXTENSION vector` | 计数 0；报缺 `vector.control`（stock 镜像） |
| 资源占用 | `podman stats --no-stream` | 实际 2.47 GiB，上限合计 5.4 GiB |
| 布局未漂移 | `bash infra/scripts/check_layout.sh` | `layout ok` |

## 与课程文档的偏差（主动讲出来）

1. 课程假设 Day 6 时环境已绿、60 分钟内能做完；本机是首次在 podman 下起栈，7 个镜像（约 5.2 GB）要先拉，按止损规则改成后台拉取、同时写笔记与风险登记册。
2. 课程把「基线数」说成一个数字；这里拆成环境 / 闭环 / 成本 / 资源四类，每类都带口径，避免拿不同前提的数字互相比较。
3. Day 1 的「10 checks passed」隐含了等待前提；今天首跑 7/10 证明脚本本身不等待。这是脚本的判定口径，不是故障，已在 README 写清「约 35 秒后再跑」。
4. 课程要求「更新风险登记册」，仓库此前没有；今天建 v1，并把 R5（远端内嵌 PAT）与 R6（推送阻断）记成真实待处理项，而不是只写技术风险。
5. pgvector 的待实测只关闭了一半：扩展不存在已本机验证；`hnsw.iterative_scan` 的返回条数差异仍要等换镜像，保留到 Day 16。
6. 单样本延迟 2.571 s 不能宣称「podman 比 colima 快 0.59 s」；只记录，不下结论。

## 三行收尾

- 卡点：7 个镜像本地全无（现有镜像属于另一套 milvus 栈），拉取占了当天大半时间；`env_check` 首跑必红，容易被误判成故障。
- 绕过：镜像改为后台拉取，同时写阅读笔记与风险登记册；首跑红后按健康端点等待再复跑，并把启动时序写进 README。
- 下次：把 `machine start → compose up → 等健康 → env_check → smoke` 写成一个脚本，让「约 35 秒全绿」成为可重放命令，而不是经验值。

## 已知限制

- 模型延迟只有单样本，没有 P95；不能用于容量规划。
- 起栈 17.7 s 是镜像已在本机时的数字；首次拉镜像约 5 分钟（未精确计时）。
- VM 与另一套 milvus 栈共享 6 GiB，未做并发或压测；内存上限合计 5.4 GiB 已接近 VM 上限。
- smoke 只发一次 completion、验一条 trace，不是回归集。
- 云端月成本仍是 Day 4 的模拟场景（30,000 次/月），不是真实流量。
- 复述自测（合上资料讲 3 条笔记）由本人完成，本文只保证笔记与出处齐全。

## 验收

- [x] 环境绿：`env_check.sh` 10/10，退出码 0
- [x] 闭环通：一次 completion + 一条可在 `/trace/<id>` 打开的 trace
- [x] 基线数：环境 / 闭环 / 成本 / 资源四类均有值与口径
- [x] 与 Day 1 的基线对照已记录，单样本不下结论
- [x] 阻塞项清零；遗留项已登记并写明补做日
- [x] 风险登记册 v1 已建立，含下周前置依赖
- [x] 三行 notes 已记录
- [ ] 口述自测（由本人完成）
