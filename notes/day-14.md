# Day 14｜TaskContract 与 EvalContract（120min）

日期：2026-11-20
用时：约 110 / 120
今日验收物：`contracts/` 5 份 + 失败码表

## 精读笔记（3 条，能复述才算）

1. **`properties` 只描述形状，`required` 才描述必填；两者写漏一个，契约就形同虚设**
   - JSON Schema 里 `properties` 定义的是「出现了该字段应该长什么样」，不出现也合法——必填必须另写 `required`。
   - `additionalProperties` 默认是 `true`，多余字段直接放行；要拒绝得显式写 `false`。
   - 所以一份「看起来完整」的 object schema，实际可能既不要求字段、也不拒绝多余字段，等于什么都没约束。
   - 对本项目：五份契约每个 `type: object` 都同时写 `required` 与 `additionalProperties: false`，把 Day 8 的决策 2（拒绝多余字段）从 TaskContract 推广到全部五类。
   - 落点：`packages/contracts/specs/*.schema.json`。

2. **JSON Schema 会说「字段之间是什么关系」吗——不能，这是它和代码的分界线**
   - Draft 2020-12 的关键字都是「针对当前实例位置」的：`const`、`enum`、`minimum`、`pattern` 都只能看它自己。没有任何关键字能写「`delta.absolute` 必须等于 `left.value - right.value`」。
   - `if/then`、`dependentRequired`、`$data` 这类结构化思路能表达一部分条件，但一旦要比较两个数值字段的大小，就超出语言能力了。
   - 结论：契约必须分两层——schema 管形状与取值域，代码管跨字段关系。把关系硬塞进 schema（比如用 `pattern` 校验数字）只会产生假通过。
   - 对本项目：`python/contract_rules.py` 专门放规则，`run_contract_cases.py` 的 `verdict()` 先 schema 后 rules，两层各自可测、失败码不同。
   - 落点：`contract_rules.py` + `check_cross_field()`。

3. **「任务 = 输入 + 约束 + 验收标准」里的验收标准，必须是可枚举的失败码，不是一句形容词**
   - Anthropic 那篇讲 agent 时反复强调：要从中拿到 ground truth 才能判断进展，并且要实现停止条件（最大轮次）。ground truth 的前提是「什么算成功、什么算失败」有明确定义。
   - 落到契约上：`verdict` 里写「结论准确」「归因合理」这类词无法被程序判断，也无法写测试；能写测试的只有失败码。
   - 失败码还要带**归谁修**（shape / semantic / control 三轴）与**能不能重试**（recoverable / terminal）：形状错可以重试，时窗错重试一万次也不会对，这个区分直接决定 Day 5 循环层的策略。
   - 对本项目：`failure_codes.yaml` 19 条，每条写 `axis`、`severity`、`http`、`when`、`action`。
   - 落点：`packages/contracts/failure_codes.yaml`。

## 扫读：模块归属

| 产出 | 归属模块 | 一句话判断依据 |
|---|---|---|
| `specs/*.schema.json` | packages/contracts | 五类任务的形状契约，跨语言共享 |
| `failure_codes.yaml` | packages/contracts | 「什么算失败」的唯一口径表 |
| `common.schema.json` 的 `FailureCodeName` | packages/contracts | 码表的机器真源，YAML 是给人读的 |
| `contract_rules.py` | packages/contracts | 跨字段规则，schema 表达不了的那部分 |
| 重试 / 降级 / 停止条件 | 循环层（后续） | 契约只给 `severity`，怎么重试是 Loop 的事 |
| 失败码落到 HTTP 响应 | Api 层（Day 15+） | `http` 字段只是建议值，真正映射在接口层 |

## 产出

- `specs/`：`common.schema.json` + 5 份任务契约（compare / attribution / trend / anomaly / forecast），Draft 2020-12。
- `specs/*.failure_codes.json`：每类任务认领的失败码子集（11 / 13 / 12 / 14 / 14 条）。
- `failure_codes.yaml`：19 条码，3 条轴（shape 6 / semantic 9 / control 4），recoverable 9 条、terminal 10 条。
- `python/contract_rules.py`：5 组跨字段规则。
- `check_specs.py`：文件层门禁。`run_contract_cases.py`：29 个正反用例。
- `python/test_contract_specs.py`：接入现有 pytest，与 Day 8 的 TaskContract 测试同跑。

## 验证

| 检查 | 命令 | 结果 |
|---|---|---|
| 契约文件门禁 | `py311 check_specs.py` | `contracts: [anomaly, attribution, compare, forecast, trend]`；`failure codes: 19 (19 in table)`；`contract specs ok`；退出码 0 |
| 正反用例 | `py311 run_contract_cases.py` | `29/29 cases behave as expected`；`contracts behave`；退出码 0 |
| 全量 pytest | `py311 -m pytest -q` | `38 passed`（Day 8 的 9 条 + Day 14 的 29 条） |
| 漂移①码表少一条 | 从 YAML 删 `DATA_NOT_CACHED` | `FAIL failure code drift: enum-only=['DATA_NOT_CACHED']`，退出码 1 |
| 漂移②删一份契约 | 移走 `trend.schema.json` | `FAIL compare: missing specs/trend.schema.json` + `FAIL codes claimed by no contract: ['TYPE_ERROR']` |
| 漂移③悬空引用 | 把 `$defs.MetricId` 改成 `NoSuchThing` | `FAIL compare$.properties.metric: $ref ... does not resolve` |
| 漂移④子集吞全表 | 让 anomaly 认领 19 条 | `FAIL anomaly: failure_codes must be a proper subset` |

## 与课程文档的偏差（主动讲出来）

1. 计划写「contracts/ 5 份」，没说是 JSON Schema 还是别的格式。用 JSON Schema Draft 2020-12，因为它是跨语言契约语言，跟 Day 8 的 Pydantic/Zod 双份实现能对齐；没有引入代码生成。
2. **踩到一个真坑并改掉了**：一开始把失败码子集写成 payload 字段 `failure_codes` 并用 `const` 固定。结果所有合法负载全被拒——因为 schema 是 `additionalProperties: false`，模型要是真返回这个字段反而是错的。子集属于「契约文件的元数据」而不是「数据的字段」，已移到旁挂 `specs/{task}.failure_codes.json`，并在门禁里加了一条断言：`failure_codes` 一旦出现在 payload properties 里就报错。
3. 计划只要求「建失败码表」，没要求它和契约联动。本文加了机械联动：YAML ↔ `FailureCodeName.enum` 逐项相等、每份契约子集必须是真子集、五份合起来必须覆盖全表——否则新加的码会谁也认领不到。
4. 计划没提 EvalContract 的形状，但标题是「TaskContract 与 EvalContract」。本文把验收标准落在失败码 + `constraints` 段（如 `closure_tolerance`、`max_backtest_mape`），没有单独再造一个 EvalContract 文件，避免和 Day 14 之后的评测集重复。
5. Anthropic 原文首段带修订说明，指出工具生态已变；本文只取「ground truth / 停止条件 / 可枚举判据」三点，不引用它的具体框架推荐。

## 三行收尾

- 卡点：以为 JSON Schema 能表达「A 必须等于 B 减 C」这种关系，写到 `allOf` 才发现语言里没有引用其他实例位置的动词；把规则硬写进 schema 会产出「永远通过」的假约束。
- 绕过：契约拆成两层——schema 管形状、`contract_rules.py` 管关系；再用 29 个正反用例证明每一层都能独立拒绝，而不是只测「合法能过」。
- 下次：写任何 schema 先问三件事——这个 object 有没有 `required`、有没有 `additionalProperties: false`、有没有哪条约束需要跨字段比较；第三条如果答案是「有」，直接去写规则函数，别在 schema 里绕。

## 已知限制

- 五份契约只有 schema 与规则，**没有任何代码在真正产出失败码**：`parse → schema → rules` 的校验入口与重试循环分别属 Api 层与 Loop 层，尚未实现。码表现在是口径，不是行为证据。
- TS 侧没有对应的五类契约（Day 8 的 TaskContract 才有双语言实现），跨语言一致性只覆盖 TaskContract。
- `contract_rules.py` 的容差是写死的 `1e-6`（`_close`），货币指标按分比较时可能需要不同容差。
- `metric` 只校验 id 形状，**不校验它是否真在 `metrics_dictionary.yaml` 里**——那需要运行时加载字典，属工具层。当前只在 `examples` 层做了检查（且今天还没放 examples 文件）。
- 失败码 `SUBTASK_TIMEOUT` 依赖编排，而编排还没做，属前瞻性定义。
- 归因的 `method` 只允许三种，shapley 需要采样设定，契约里没有 `sample_size`。
- 没有版本迁移机制：改字段是直接改，破坏性变更要人肉判断。

## 验收

- [x] 对比 / 归因 / 趋势 / 异常 / 预测 五类各一份契约
- [x] 失败码表 19 条，带轴 / 严重度 / HTTP / 处理动作
- [x] 码表与契约机械联动（枚举一致、真子集、全覆盖）
- [x] 门禁可运行，四种结构漂移都退出码 1
- [x] 29 个正反用例全部符合预期
- [x] 产物入 `packages/contracts/`，命名可检索
- [x] 3 行 notes（卡点 / 绕过 / 下次）已写
- [ ] 口述自测（由本人完成）