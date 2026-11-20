# 0006 · API 内部分层与端口契约

- Status: accepted
- Date: 2026-11-20
- Deciders: 项目负责人（单人维护）
- Supersedes: —

## Context

Day 15 的验收物是「可启动 api + healthz + 分层目录」，计划给的分层词是 `api / domain / agent / tools / infra`。同日要「3 个端口空实现（LLM/Tool/Repo）」。

两件事需要先定清楚，否则目录建出来就是四个空壳：

**一、这套分层加在哪一层。** ADR-0002 已经把仓库分成五层（`apps / packages / skills / eval / infra`），并规定依赖方向 `apps → skills → packages`。计划里的五个词不是仓库层，是 **`apps/api` 内部**的分层。混为一谈会出现两种错误：把 `domain/` 提到仓库根（违反 ADR-0002 的「每层职责唯一」），或者在 `apps/api/` 下再建一个 `infra/`（与仓库级 `infra/` 同名不同义，新人必然搞混）。本 ADR 明确：这是**应用内**分层，落在 `apps/api/dataagent/` 下。

**二、端口用什么形式。** 三种可选：
- 方案 A：抽象基类（ABC）+ 继承；
- 方案 B：`typing.Protocol` 结构化子类型；
- 方案 C：不设端口，直接注入 SDK 客户端。

方案 C 是 Fowler 在 DIP in the Wild 里明确定义的反例：注入一个 JDBC 连接确实「解耦了实例化」，但依赖的抽象层级仍停在存储层，调用方还是被迫用库的词汇思考。方案 A 强制显式继承，多写一行 `class X(Base)` 就换来一个耦合点，且测试替身必须继承基类。方案 B 让「实现了这个端口」由**形状**决定而非声明：测试替身不需要知道端口类型存在，鸭子类型加静态检查已经足够。

本项目的真实约束：

- 维护者 1 人，没有代码生成流水线；接口改动只能靠测试兜住。
- 当前 `apps/api` 里已有 Day 11 的 `tenant_policy.py` 与 `test_tenant_policy.py`，位于**包外**（`apps/api/` 根），是 Day 11 的参考实现，不属于今天的迁移范围。
- 今天没有任何真实依赖：没有数据库连接、没有模型 key（Day 16 才接 LiteLLM）、没有工具实现。

## Decision

1. **应用内分五层，落在 `apps/api/dataagent/` 下**：`api / domain / agent / tools / infra`。
   - `domain`：业务概念，仅标准库。今天只有 `health`。
   - `agent`：编排，只依赖 `ports` 与 `domain`；`agent/ports` 放端口，`agent/adapters` 放实现。
   - `tools`：副作用边界，含带超时的执行器。
   - `api`：FastAPI 外壳，只做 HTTP ↔ domain 翻译。
   - `infra`：进程关注点与**组合根**；唯一允许点名具体适配器的地方。

2. **端口用 `typing.Protocol`**，每个端口按**业务词汇**写，不按库词汇写。
   - `LLMPort.complete(LLMRequest) -> LLMResponse`，不是 `chat_completion(messages)`——message list 是厂商词汇，会让 provider 细节渗进每个调用点。
   - `MetricRepositoryPort.get(metric_id) -> MetricDefinition`，**不做**通用 `query(sql)` 或 `get(table, id)`：通用仓储会把存储抽象直接交给 agent，正是方案 C 的错误。
   - `ToolPort.available() / invoke()`，`available()` 是工具白名单，从第一天就存在。

3. **依赖方向由测试强制，不靠约定。** `apps/api/tests/test_layering.py` 用 AST 解析每个 `import`：
   - `domain` 不得 import 任何第三方；
   - `agent` / `tools` / `api` 不得 import `adapters`；
   - 只有 `infra` 可以点名适配器。
   另有 `test_agent_layer_survives_without_adapters`：屏蔽适配器后 `domain / ports / service` 仍须 import 成功。

4. **三个端口今天都给「诚实的最小实现」**：
   - `EchoLLM`：确定性地回显，不是 `NotImplementedError`——空实现无法证明接线正确，而回显能让冒烟测试走完整条链路，同时它显然不是真模型。
   - `YamlMetricRepository`：直接读 Day 13 的 `metrics_dictionary.yaml`，把「YAML 在磁盘上」这个细节吸收在适配器里。
   - `InMemoryTools`：注册 `metric_lookup` 占位，调用即抛 `NotImplementedError`——**故意**报错而不返回假数据。

5. **`/healthz` 是诚实探针**：实际跑关键依赖（读一条指标、调一次模型适配器），关键依赖失败返回 **503**，非关键依赖（tools）失败只降级不失败。不用 `200` 常量。

6. **组合根只构造，不做全局注册表。** `build_container(settings)` 返回一个普通 dataclass，没有 lazy resolution，也没有 service locator。

## Consequences

+ 换实现只改 `infra/container.py` 一个文件：Day 16 接 LiteLLM 时只替换 `EchoLLM` 那一行。
+ `domain` 与 `agent` 可以在没有服务、没有数据库、没有网络的情况下测完。
+ 依赖方向从「README 里的图」变成「会失败的测试」；违规当场红。
+ `/healthz` 真的会红：LLM 挂掉返回 503，避免探针变成摆设。
- 端口抽象有成本：多一层 `Protocol` 与 DTO，简单调用也要绕一次。当前仅 3 个端口可接受；端口数量增长后需重新评估。
- `Protocol` 是结构化子类型，不检查「是否实现了它」，只检查「形状是否匹配」；漏实现一个方法要到调用时才暴露。缓解：已接入 mypy（`dataagent/` 28 个文件零错误）；实测把 `EchoLLM.complete` 的返回类型改成 `str`，mypy 在 `container.py` 报 `Expected: -> LLMResponse / Got: -> str`。mypy 已进 `apps/api/check.sh` 门禁，但该门禁尚未接 CI 平台。
- `EchoLLM` 的 token 数用空格切分估算，不是真实计费口径；Day 16 接网关后必须换成真实用量。
- `InMemoryTools` 里的 `metric_lookup` 是个会抛异常的占位；任何误把它当真实工具的调用线都会在运行期炸，而不是给出一个看似合理的数。
- Day 11 的 `tenant_policy.py` **已迁移**到 `dataagent/domain/tenant_policy.py`（纯策略、无框架无 I/O，属 domain 层）；fixture 保留在 `apps/api/fixtures/`。文档引用已同步。
- 应用内 `infra/` 与仓库级 `infra/` 同名不同义，是本决定的已知混淆点；`dataagent/` 这一层前缀是缓解手段。

## Amendment (2026-11-20) · 补齐计划未覆盖的缺口

核对后续 78 天计划后确认，以下三项**不在任何后续天的覆盖范围内**，故在 Day 15 现场补齐，不推迟：

| 缺口 | 计划状态 | 本次补齐 |
|---|---|---|
| 请求跳的租户解析 | Day 41/46/53 覆盖 db/vector/log/记忆，但**都假设 tenant 已在手上**；78 天无「请求如何拿到并验证 tenant」 | `domain/tenant.py` + `api/deps.py`，强制依赖，不可自报 |
| 鉴权 | Day 15 之后全文无「鉴权/认证/JWT」条目 | `domain/auth.py` 的 `ApiKeyStore`，key↔租户绑定、常量时间比较、fail closed |
| 质量门禁 | Day 65 的 CI Gate 只覆盖「50 条评测 + 准确率阈值」，不含 lint/类型 | `apps/api/check.sh`：ruff + mypy + pytest |

补充决定：

7. **鉴权落在 `domain/auth.py` 而非单独一层**：它是「凭据 → 租户」的纯映射，不含 I/O，符合 domain 的定义。真实 IdP 接入时替换的是这一个适配器，路由不动。
8. **`/healthz` 有意免鉴权**：负载均衡器没有 key，探针不可调用等于没有探针。响应仅含依赖名与状态。
9. **不设默认租户**：`DATAAGENT_API_KEYS` 为空即全拒。任何「开发默认租户」都会在忘记配置的环境里静默变成跨租户泄漏。

## Confirmation

- `apps/api/tests/test_layering.py`：4 个守卫测试，其中 2 个用 AST 检查 import 方向，1 个用 meta_path 屏蔽适配器验证 agent 层自足。
- 反向实验：在 `agent/service.py` 顶部加 `from dataagent.agent.adapters.echo_llm import EchoLLM`，守卫报 `agent/service.py (agent) imports dataagent.agent.adapters.echo_llm`；在 `domain/health.py` 加 `from fastapi import APIRouter`，报 `health.py imports fastapi`。两处违规均被捕获。
- `infra/scripts/check_layout.sh` 增加 `apps/api/dataagent/*` 五个目录的存在性检查。
- `uvicorn dataagent.api.app:build_app --factory` 起服务后 `GET /healthz` 返回 200 与逐依赖状态。
- `mypy dataagent/` 零错误；故意改坏端口实现签名后 mypy 报错，证明端口形状被真正检查。