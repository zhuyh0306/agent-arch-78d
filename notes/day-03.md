# Day 3｜技术选型对比与决策（120min）

日期：2026-11-10
用时：约 120 / 120
今日验收物：`docs/selection-matrix.csv` + `docs/adr/0004-storage-and-vector.md`（另有 `infra/scripts/score_matrix.py` 让结论可重算）

## 精读笔记（3 条，能复述才算）

1. **Qdrant 的 payload 不是附属字段，它参与过滤；要过滤的字段必须先建 payload index**
   - 出处：https://qdrant.tech/documentation/manage-data/points/ （「A point is a record consisting of a vector and an optional payload」）与 https://qdrant.tech/documentation/concepts/filtering/ （「For performant filtering, create payload indexes for the fields you plan to filter on. For best results, create payload indexes before ingesting data.」；must=AND、should=OR、可递归嵌套）
   - 落点：`skills/retrieval`。adapter 里把 tenant / doc_type 的过滤条件与 payload index 一起定义，而不是查询时临时加 WHERE。Collection → Point(id + vector + payload) 是三层包含关系，不是并列概念。

2. **Temporal 的 Workflow 必须确定性，副作用只能进 Activity；改命令顺序会让老实例重放失败**
   - 出处：https://docs.temporal.io/workflow-definition （「Deterministic constraints」「Intrinsic non-deterministic logic」「Code changes can cause non-deterministic behavior」；缓解手段是 Workflow Versioning / Patching）
   - 落点：`runtime`（Day 28 评估）。今天只记结论：多轮工具调用 + 人工确认确实需要持久化编排，但现在引入等于为不存在的需求付运维成本。重放靠 Event History 比对命令序列，所以 `now()` / `random()` / 网络调用都不能写在 Workflow 里。

3. **pgvector 带 WHERE 的 HNSW 是 post-filter，默认参数下会「少返回」；ef_search 是唯一不改索引就能调召回的旋钮**
   - 出处：pgvector README（v0.8.7，经 jsDelivr 取回）Filtering 一节：「With approximate indexes, filtering is applied *after* the index is scanned. If a condition matches 10% of rows, with HNSW and the default `hnsw.ef_search` of 40, only 4 rows will match on average.」；Index Options：`m`=16、`ef_construction`=64；Query Options：`ef_search`=40，`SET LOCAL` 可只作用于单条查询；索引维度上限 `vector` 2000 / `halfvec` 4000 / `bit` 64000。
   - 落点：`skills/retrieval`。查询封装里默认 `SET LOCAL hnsw.iterative_scan = relaxed_order`，并把「返回条数 < LIMIT」当成告警信号而不是正常结果。算子与 opclass 必须对齐（`<=>` ↔ `vector_cosine_ops`），否则索引建了也用不上。

## 扫读：模块归属

| 资料 | 归属模块 | 一句话判断依据 |
|------|---------|---------------|
| Qdrant 数据模型与过滤 | retrieval | 只决定召回与过滤，不参与鉴权和业务判定 |
| Temporal Workflow/Activity | runtime | 编排与恢复属于运行时，Day 28 再评估 |
| pgvector 索引与算子 | retrieval | 是 Postgres 的扩展，检索实现细节关在 adapter 里 |
| IVFFlat vs HNSW | retrieval | 数据基本不变且先有全量数据才考虑 IVFFlat（lists ≈ rows/1000，>1M 用 sqrt(rows)） |

## 产出

- `docs/selection-matrix.csv`：四候选 × 五维（cost/ops/eco/exit/fam），1–5 分。
- `infra/scripts/score_matrix.py`：按列名取值加权（不用位置 zip），权重写在文件顶部，可改一个数重跑；支持传入其它 CSV 路径。
- `docs/adr/0004-storage-and-vector.md`：五段式 + Alternatives，含切换阈值、退出路径、代价与待实测项。

## 验证

| 检查 | 命令 | 结果 |
|------|------|------|
| 加权总分 | `python3 infra/scripts/score_matrix.py` | SQLite 4.50 / Postgres 4.05 / PG+pgvector 3.75 / Qdrant 2.95 |
| 路径无关 | 在 `/tmp` 下用绝对路径跑同一脚本 | 输出一致（脚本按自身位置解析仓库根） |
| 权重敏感性 | 内存中把 ops 改 0.10、exit 改 0.40 后重跑 | 4.50 / 4.20 / 3.90 / 3.10，排序不变 → 结论不依赖某个权重假设 |
| 布局未漂移 | `bash infra/scripts/check_layout.sh` | `layout ok` |
| pgvector 是否随官方镜像提供 | pgvector README Installation | 需源码编译或单独安装（Docker/APT/Homebrew/PGXN），官方 `postgres:16-alpine` 不含 |
| 实验台运行态 | `podman machine list` / `podman ps` | VM 为新建（6 GiB），只跑着另一套 milvus/mongo 栈；Day-1 实验台容器未运行 |
| 本机 embedding 模型 | `curl :11434/api/tags` | 只有 `qwen2.5:0.5b`（chat），无 embedding 模型 |
| `CREATE EXTENSION vector` 实测 | — | **待实测**：实验台未运行，不假装测过；补做日不晚于 Day 16 |

## 六个争议格的证据

| 格位 | 分 | 一句话证据 |
|------|---|-----------|
| SQLite · 运维 | 5 | 单文件、无服务进程；备份=复制，回滚=换回旧文件 |
| SQLite · 生态 | 3 | 无 RLS、写锁库级；周边工具围绕单机与移动端 |
| Postgres · 成本 | 4 | 它本来就必须为 Langfuse 运行，业务复用不新增服务；但 VM 重建后镜像要重拉，「增量≈0」仅指服务数量 |
| Postgres · 运维 | 3 | 备份、连接池、慢查询监控都要自己盯，没有托管就等于自己值班 |
| PG+pgvector · 退出 | 4 | SQL 层可换索引类型，但 embedding 维度一变就要全量重灌 |
| Qdrant · 运维 | 2 | 独立备份/升级/磁盘水位；本机 VM 仅 6 GiB 且已被其他栈占用 |

## 与课程文档的偏差（主动讲出来）

1. 脚本位置：文档写 `scripts/score_matrix.py`，本仓按 ADR-0002 放 `infra/scripts/`，并改成按自身位置解析仓库根。
2. `vector(1536)` 不适用：那是 OpenAI 维度；本机还没有 embedding 模型，维度待选定后写进 contracts，ADR 不写死。
3. 「团队 5 人」改为单人维护；「已有 api + worker 多进程写入」改为规划中（apps/api 仍是占位），SQLite 的排除是前瞻判断。
4. 「Postgres 已部署、增量≈0」要加限定：官方镜像不含 pgvector，复用实例需换镜像，是一次性迁移成本。
5. 「Qdrant 多一个服务」在本仓是「compose 已定义但当前未运行」；它留着当实验基线，业务不依赖，避免绕过阈值顺手就用。
6. 过滤机理以 pgvector README 为准（post-filter + iterative_scan）；课程说 Qdrant「pre-filter 更强」，本次读到的 filtering 页只强调 payload index，未下该结论，标为待核实。

## 三行收尾

- 卡点：本机 Docker 被公司策略禁用（运行时是 podman），podman VM 又是新建的，实验台容器与镜像都不在，没法实测 `CREATE EXTENSION vector`；WebFetch 限流、GitHub raw 超时，资料一度取不到。
- 绕过：改用 `podman` 查运行态；pgvector README 走 jsDelivr CDN、Qdrant 页面直接 curl 后抽正文；把无法实测的项登记为「待实测 + 补做日」，而不是填一个看起来合理的结论。
- 下次：起栈前先 `podman machine list` + `podman ps` 确认 VM 与容器还在；取官方文档先试 CDN 镜像再试原站；凡是「已部署所以成本低」的判断，先确认它现在真的在跑。

## 已知限制

- `CREATE EXTENSION vector` 与「开/关 iterative_scan 的返回条数差异」未实测，补做日不晚于 Day 16。
- 500 万向量阈值、10 GB 内存账是公开资料量级判断，不是本项目压测结果；上线前需用 10 万 / 100 万两级压测确认。
- 本机另有 milvus 栈占用 VM 内存，做向量压测前要先停掉无关容器或扩 VM。
- 运行时已从 Docker 切到 podman：`podman compose config -q` 通过、VM 内访问宿主 Ollama 实测 200，但 Day-1 的 8 个容器尚未在 podman 下整体复跑，补做日与 `CREATE EXTENSION vector` 合并。
- 复述自测（合上资料讲 3 条笔记）由本人完成，本文只保证笔记与出处齐全。

## 验收

- [x] 四候选问题域能说清（含 SQLite 与 Temporal 被排除/暂缓的理由）
- [x] 五维各有可复查口径，争议格有一句话证据
- [x] `docs/selection-matrix.csv` 已落库，改权重可重算（敏感性检查已跑）
- [x] Postgres 胜出理由能讲成两句话，且能解释 SQLite 分更高为何被否
- [x] pgvector 与 Qdrant 分界线含 500 万阈值与过滤复杂度/扩缩诉求
- [x] HNSW 三参数各管什么，ef_search 是不改索引就能调的那个
- [x] 退出成本四项分清：重灌数据与重跑基线省不掉，adapter 与双写过渡能靠设计省
- [x] ADR-0004 含阈值、退出路径、代价与待实测项
- [x] 三行 notes 已记录
