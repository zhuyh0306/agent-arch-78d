# 前两周速记：能背下来才算掌握（Day 1–12）

> 用法：先背第 0 节十句；再背第 1 节地图；最后用第 5 节 12 问自测。答不出的，回到对应表格查证据。

## 0. 十句总纲（先背这十句）

1. 没有基线数字的优化都是猜测。
2. 验收 = 第三人能重放的命令 + 原样输出 + 口径。
3. 契约先行，模型后接；结构化只保证形状，不保证事实。
4. 提示词是接口，不是文案；改版必须有对照记录。
5. 成本按 token 计；中文约贵 2.8 倍；上下文是大头，但有门槛。
6. 分层不是为了好看，是为了让故障域可隔离。
7. 能纯代码或 workflow 解决，就不要上 Agent。
8. 多租户不是加字段，是 `tenant_id` 五跳贯穿；RLS 防的是写错与绕过。
9. 模型答错时，用户看「结论 + 依据 + 下一步」，内部留「原始产出 + 失败码 + 重试 + 成本」。
10. 卡住 15 分钟就换路；没验证的事写「待实测」，不写结论。

## 1. 十二天地图

| Day | 主题 | 一句话记住 | 证据 |
|---|---|---|---|
| 1 | 环境与工具链 | Langfuse v3 是 6 个进程，不是一个容器；completion 200 ≠ trace 通 | `infra/README.md`、Day 1 笔记 |
| 2 | 仓库与 ADR | ADR 记「为什么」；依赖只能指向更稳定的一端 | `docs/adr/0001–0003` |
| 3 | 技术选型 | 五维打分，退出成本优先；SQLite 分最高却被结构性排除 | `docs/selection-matrix.csv`、ADR-0004 |
| 4 | LLM 与成本 | token 计费；前缀缓存只吃稳定前缀；attention 是 O(n²·d) | `eval/cost/cost-model.csv` |
| 5 | Agent 范式 | 路径由代码定是 workflow，由模型定才是 agent | `docs/paradigm-decisions.md` |
| 6 | M0-1 验收 | 基线数分四类：环境 / 闭环 / 成本 / 资源 | `docs/m0-1-acceptance.md` |
| 7 | 提示工程五层 | 先定位层，再改措辞；提示词管形状，不管算术 | `skills/prompts/contrast-conclusion.md` |
| 8 | 结构化与契约 | 入参 / 出参 / 约束 / 失败码；双语言 fixture 是门禁 | `packages/contracts/` |
| 9 | AI-Native 产品 | 能力上限由异常路径决定；4 个 HITL 点位 | `docs/ai-native-product.md` |
| 10 | 全景架构 | 四层 + 两个网关；故障域决定能不能降级 | `docs/architecture.md` |
| 11 | 多租户 | 零信任：不因位置给信任；五跳都带 `tenant_id` | `docs/multi-tenancy.md` |
| 12 | 复盘与评审 | 挑最不满意的产出，找共性根因，再改制度 | `docs/week-02-review.md`、`docs/risk-register.md` |

## 2. 六张必背表

### 2.1 五层：PE / CE / HE / LE / GE

| 层 | 管什么 | 失效症状 | 本项目落点 |
|---|---|---|---|
| PE Prompt | 让模型做什么：角色、规则、格式、示例 | 答案类型错，信息是对的 | `skills/prompts/` |
| CE Context | 模型能看到什么：检索、结构、时效、窗口 | 信息错 / 缺 / 过时 | context builder（后续） |
| HE Harness | 模型被允许做什么：工具、权限、沙箱、限额 | 知道该做，但做不了 | 工具网关、契约 |
| LE Loop | 怎么迭代到完成：观察、规划、行动、停止 | 重复调用 / 过早放弃 / 停不下来 | Runtime / Harness 循环 |
| GE Graph | agent / 工具 / 人怎么协作 | 单 Agent 正常，交接与升级失败 | 多 Agent 编排（后续） |

**定位顺序**：先看信息对不对 → 再看权限够不够 → 再看循环停没停 → 最后才动措辞。

### 2.2 四层 + 两个网关

| 层 | 唯一职责 | 不可以 | 挂了会怎样 |
|---|---|---|---|
| Gateway（接入网关） | 认证、租户解析、限流、路由 | 拼 prompt、做 RAG、写业务数据 | 全链路停服 |
| Runtime | 任务状态、超时、重试、降级、恢复 | 做策略裁决、持有 provider key | 在途任务丢失，有 checkpoint 才能恢复 |
| Harness | 循环、工具白名单、步数 / 预算、停止条件 | 持有 key、决定租户权限 | agent 任务停；固定 workflow 不受影响 |
| 治理层 | 策略、RBAC、评测、发布门、审计、可观测 | 修改单次请求数据 | 只读可按 last-known 策略继续；高风险 fail closed |

**两个网关必须分开**：接入网关认人；LiteLLM 管模型路由与 provider key。合并后接入层会拿到不该拿的 key。

### 2.3 范式判定

三问，任意一个是就停在那层：

1. 规则能枚举成确定性逻辑？→ **纯代码**
2. 步骤固定、终止条件能写死？→ **workflow**
3. 下一步依赖上一步结果且事先不可知？→ **agent（必须有界）**

五个 workflow 模式：prompt chaining / routing / parallelization / orchestrator-workers / evaluator-optimizer。

agent 四条边界：**步数上限（8）、工具白名单、只读、预算**，外加人工确认点。缺一个就是失控。

### 2.4 契约与失败码

- 四件套：**入参 / 出参 / 约束 / 失败码**。
- 四主码：`PARSE_ERROR` / `MISSING_FIELD` / `ENUM_OUT_OF_RANGE` / `RETRY_EXHAUSTED`。
- 补三码：`UNKNOWN_FIELD` / `TYPE_ERROR` / `CONSTRAINT_VIOLATION`。
- 链路：解析 → Schema → 约束 → 重试（≤2）→ 降级 → 拒答 → Trace。
- 取码优先级：缺字段 > 枚举越界 > 多余字段 > 约束 > 类型。
- 边界：结构化输出管形状，**不管算术与事实**。

### 2.5 多租户

- 五跳：**请求 → DB → 向量库 → 日志 / Trace → 记忆**。
- 隔离三级：独立库 / 独立 schema / 共享 schema + RLS。
- 当前选择：共享 schema + RLS；运行角色**非 owner、无 `BYPASSRLS`**，表上 `FORCE ROW LEVEL SECURITY`，策略是**permissive 放行 + restrictive 收窄**。
- RLS 三绕过：**表 owner、超级用户、`BYPASSRLS`**。
- 只有 restrictive 会**默认全拒**（Day 12 真实 RLS 实测：tenant-a 读到 0 行）。
- 读写分开：`USING` 管可见行，`WITH CHECK` 管写入行。
- 5 条攻击：跨租户读 / 伪造 tenant / 向量 filter 丢失 / 记忆跨租户写 / 日志跨租户查；另加 1 条自读对照。

### 2.6 成本四段与关键数字

| 项 | 必背数字 |
|---|---|
| 单次输入 | system + 工具 schema + 检索上下文 + 历史 + 用户问题 |
| 中文 vs 英文 | 中文 1.50 字/token；英文 4.27 字符/token；同义内容中文约 **2.8×** token |
| 缓存前缀 | 稳定前缀占输入 **36%**，账单只降 **20%** |
| 峰谷 | 同一请求差 **2 倍** |
| 输入压过输出的门槛 | `in > 884 token`（Flash 谷时未命中） |
| 1M 上下文 | 按 Flash 未命中价约 **$0.15/次**，30,000 次/月 ≈ **$4,500** |
| 最便宜组合 | Flash 谷时命中：**$0.0002/次、$0.25/千次、$7.39/月** |
| 最贵组合 | V4-Pro 峰时未命中：**$0.0024/次、$2.42/千次、$72.55/月** |

## 3. 数字卡（按主题背）

**环境 / 闭环（Day 6 实测）**

- 起栈 `up -d`：**17.7 s**；约 **30–35 s** 后 10/10 全绿。
- smoke：**8.46 s**；trace 延迟 **2.571 s**；usage **41 / 34 / 75**。
- 资源：实际 **2.47 GiB**，上限合计 **5.4 GiB**。

**选型（Day 3）**

- 加权：SQLite **4.50** / Postgres **4.05** / PG+pgvector **3.75** / Qdrant **2.95**。
- 敏感性重跑（ops 0.10、exit 0.40）：**4.50 / 4.20 / 3.90 / 3.10**，排序不变。
- pgvector 默认 `hnsw.ef_search=40`，匹配 10% 行平均只回 **4 条**。

**提示词（Day 7）**

- v0 **10 token**；v1 **461 token**；3 个例子 + 5 条规则。
- 正常组结构 / 引用通过，算术 `108/3600` 稳定输出 **2.8%**（正确 **3.00%**）。
- 加第 6 条规则后，拒答退回归零、算术变 **2.4%** → 回退。

**架构 / 租户（Day 9–11）**

- HITL **4** 点：H1 发布 / H2 高后果动作 / H3 校验失败 / H4 抽样审计。
- Demo→产品 **5** 个必补项：身份租户 / 契约失败码 / Trace 证据 / 成本配额 / 评测发布门。
- 目标架构 **4** 层 + **2** 个网关；故障域表 **8** 个组件；`tenant_id` **5** 跳。
- 越权用例 **5** 条攻击 + **1** 条对照；RLS **8** 条坑。

## 4. 症状 → 层（先定位，再动手）

| 症状 | 先查哪层 | 第一动作 |
|---|---|---|
| 答案类型错，但信息是对的 | PE | 改格式、例子、拒答规则 |
| 信息错 / 缺 / 过时 | CE | 查检索、时效、上下文装配 |
| 知道该做什么但做不了 | HE | 查工具、权限、限额 |
| 重复调用 / 停不下来 / 过早放弃 | LE | 查终止条件、步数、预算 |
| 单 Agent 正常，交接失败 | GE | 查路由、上下文隔离、升级 |
| 格式对、算术错 | 工具层 | 把计算交给代码，不修措辞 |
| 跨租户能查到数据 | 租户执行层 | 查 token 来源、RLS、向量 filter |
| completion 200 但 trace 空 | 可观测层 | 查 Langfuse worker 与三个 `LANGFUSE_*` |
| 网关 401 | 接入层 | 查 `infra/.env` 的 key，不打印密钥 |
| 起栈首跑红 | 启动时序 | 等健康端点再复跑 `env_check.sh` |

## 5. 12 问自测（能答 10 个才算过关）

1. **换一台机器，怎么在 30 分钟内复现？** 起 podman VM → compose up → 等健康 → `env_check` → `smoke`，四步都有命令与预期输出。
2. **SQLite 分最高，为什么不用？** 库级写锁扛不住多进程，且无 RLS，租户隔离全压应用层；这是结构性不匹配，不参与加权。
3. **pgvector 带 WHERE 为什么少返回？** HNSW 是 post-filter，先扫索引再过滤；默认 `ef_search=40` 时匹配 10% 只剩约 4 条，要开 `iterative_scan`。
4. **中文为什么贵 2.8 倍？** BPE 按子词切，中文没有空格边界，同义内容中文 1.50 字/token，英文 4.27 字符/token。
5. **什么时候成本大头是上下文？** 输入 token 超过 `out × out_price / in_price`，Flash 谷时约为 884 token；短问答输出可能才是大头。
6. **workflow 与 agent 的分界？** 路径由代码定是 workflow，由模型动态定才是 agent；先证明不用 Agent 不够，再升级。
7. **Plan-and-Solve 是 agent 吗？** 不是，它是单次调用里的计划提示，没有环境反馈；ReAct 才有 action → observation 循环。
8. **ReAct 的 thought 会产生 observation 吗？** 不会；thought 只改上下文，只有 action 才改变环境并带回结果。
9. **怎么证明 v1 比 v0 好？** 同一模型、同一上下文跑 3 组对照，记录双方原文与信号位；有差异表，不靠主观感觉。
10. **结构化输出能保证什么？** 保证形状、必填、枚举与约束；不保证事实与算术，服务端二次校验不能省。
11. **哪层挂了还能用？** 治理层与可观测层可降级继续；Gateway、数据层、模型网关挂了必须停服；高风险动作在策略引擎不可用时 fail closed。
12. **向量库怎么保证 A 租户不进 B？** 服务端强制注入 `tenant_id` filter，客户端不能覆盖；检索入口与记忆读写双向校验，用越权用例回归。

## 6. 五个最容易被追问的坑

1. **把提示词当万能**：算术错、缺数据、越权，改措辞都救不回来；先定位层。
2. **把结构化输出当免校验**：模型仍会漏字段、填错枚举；契约要服务端校验。
3. **把所有动作都审批**：注意力耗尽后只会点通过，这是 human-in-the-loop theater。
4. **把有 `tenant_id` 当多租户**：五跳缺一跳就是一条越权路径；RLS 还会被 owner / `BYPASSRLS` 绕过。
5. **把「缓存省一半」当默认**：只有稳定前缀能命中；本项目实测前缀 36% → 账单降 20%。

## 7. 30 秒口述版

> 前两周做了三件事：把环境和成本基线冻结；把提示词、契约、产品与架构的分层讲清；把多租户的边界落到五跳和 5 条用例。核心判断是：先定位层再改措辞，先定契约再接模型，能不用 Agent 就不用。所有结论都有基线、命令或对照记录；没验证的写「待实测」。

## 8. 证据索引（被问「凭什么」时打开）

| 结论 | 打开 |
|---|---|
| 环境与起栈基线 | `infra/README.md`、`docs/m0-1-acceptance.md` |
| 选型与 ADR | `docs/selection-matrix.csv`、`docs/adr/0004-storage-and-vector.md` |
| 成本三档 | `eval/cost/cost-model.csv`、`eval/cost/cost_model.py` |
| 范式判定 | `docs/paradigm-decisions.md` |
| 提示词对照 | `skills/prompts/contrast-record.md`、`contrast-conclusion.md` |
| 契约与一致性 | `packages/contracts/` |
| 产品与 HITL | `docs/ai-native-product.md` |
| 架构与故障域 | `docs/architecture.md` |
| 多租户与越权用例 | `docs/multi-tenancy.md`、`apps/api/tenant_policy.py` |
| 第 2 周复盘与风险 | `docs/week-02-review.md`、`docs/risk-register.md` |