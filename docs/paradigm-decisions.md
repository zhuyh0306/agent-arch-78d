# 范式决策表（Day 5）

判定顺序固定为 **纯代码 → workflow → agent**：先用最便宜的形态证明不够，再升级。三个问题依次问，任意一个「是」就停在那层：

| # | 问题 | 是 → |
|---|------|------|
| 1 | 判断规则能否枚举成确定性逻辑？ | 纯代码 |
| 2 | 步骤是否固定、终止条件能否写死？ | workflow（路径由代码定） |
| 3 | 下一步是否依赖上一步结果、且事先不可知？ | agent（必须加边界） |

三个都否，先回需求，不要用「上 Agent」掩盖问题没想清。

## 三个场景

| 场景 | 判定 | 关键依据 | 反例（何时该换） |
|------|------|---------|-----------------|
| A. 每日 06:00 数据质量校验：行数波动、主键唯一、金额非负、分区齐全 | **纯代码** | 四条规则都能写成 SQL/断言，通过与否是确定的；失败处理固定为告警 | 若要求「自动解释异常并写周报」，校验判定仍是代码，只把解释环节加成 workflow |
| B. 指标问答：检索口径 → 生成 SQL → 执行 → 校验 → 至多重试一次 → 组织答案 | **workflow** | 步骤与终止条件固定，路径由代码编排；模型只负责生成 SQL 与措辞 | 若问题变成「为什么退款率涨了」、需自行决定查哪些表、查几轮，就跨到 agent；若只是固定报表取数，可退化为 routing + 模板 SQL |
| C. 退款率异常根因分析：「为什么涨了 0.7 个点？给三条建议」 | **agent（有界）** | 假设（品类/渠道/支付方式）与验证顺序依赖中间结果，事先不可知 | 若根因清单固定为三个维度，退回 parallelization/workflow 逐维跑固定 SQL；若只能读给定材料、无工具可调，则 plan-and-solve 提示即可，不需要 agent |

## 逐场景展开

### A. 数据质量校验 → 纯代码

- 输入：昨日分区，四张固定表。
- 规则：`昨天行数 / 前 7 天均值` 在 0.7–1.3；主键重复数 = 0；`amount >= 0`；分区日期齐全。
- 为什么不是 workflow：没有任何一步需要生成式判断，LLM 只会增加延迟、成本和不确定性。
- 演示：一条 SQL + exit code，失败即告警。

### B. 指标问答 → workflow

- 路径：`routing`（取数 / 口径解释 / 对比）→ `prompt chaining`（检索口径 → 生成 SQL → 执行 → 组织答案），中间加两道程序化 gate：SQL 只读且不含 `SELECT *`、结果非空且行数 ≤ 200。
- 有界循环：执行失败或结果校验不过时，把错误原文回灌，重写一次（`evaluator-optimizer` 的一次迭代）；第二次失败直接报错。
- 为什么不是 agent：走哪条分支、重试几次、何时停，全部由代码决定；模型只做「生成」这一件事。
- 边界：单次调用输入约 1,200 token（Day 4 基线），重试一次最多翻倍。

### C. 根因分析 → agent（有界）

- 循环：ReAct 式 `Thought → Action → Observation`，模型自行决定下一个查询；每步只读。
- 为什么必须给边界：
  - 工具白名单：`describe_table` / `run_sql`（只读）/ `search_docs`，不开放写入与外部网络。
  - 步数上限 8；超限停止并交回人工，不「再试一次」。
  - 预算上限：按 Day 4 价目粗估，8 步、每步 ≤2k 输入 token ≈ 16k token，Flash 谷时未命中约 **$0.0024/次**（上限假设，未实测）。
  - 人工确认点：任何跨租户、跨库或超过 200 行的查询直接拒绝，不做自动放宽。
- 为什么不用 orchestrator-workers：当前只有一个分析维度在推进，拆 worker 只会增加编排与汇总成本；等出现「多维度并行排查」再升级。

## 常见误判

1. **把 Plan-and-Solve 当 agent**：它只是单次调用内的计划提示（先拆子任务再逐步做），没有环境反馈，也没有「下一步看结果再决定」。它属于 `skills/prompts`，不是 `runtime`。
2. **把 orchestrator-workers 当 agent**：子任务由 orchestrator 动态拆，但外层仍是代码定义的 workflow；Anthropic 把它归在 workflow 一类。
3. **用 agent 做固定报表**：路径本来就能写死，换来的是更贵、更慢、更难回归。
4. **有 agent 没边界**：步数、工具、预算、人工确认四样缺一个，就不是「范式选择」而是失控。

## 出处

- Anthropic, *Building Effective Agents*：workflow 是「LLMs and tools are orchestrated through predefined code paths」，agent 是「LLMs dynamically direct their own processes and tool usage」；五个 workflow 模式与各自适用条件；总体建议是「find the simplest solution possible, and only increasing complexity when needed」。
- Wang et al., *Plan-and-Solve Prompting*（arXiv:2305.04091）：zero-shot CoT 的三类错误（calculation 7% / missing step 12% / semantic misunderstanding 27%，46 道错题）；PS 把「Let's think step by step」换成「先理解问题并制定计划，再按计划逐步执行」。
- Yao et al., *ReAct*（arXiv:2210.03629）2.1：thought 是语言空间里的动作，不改变环境、不产生 observation；只有 action 才产生环境反馈；循环提升可解释性，并缓解 CoT 的幻觉与错误传播。
