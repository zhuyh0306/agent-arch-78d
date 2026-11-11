# Day 5｜Agent 范式全景与选型（90min）

日期：2026-11-10
用时：约 90 / 90
今日验收物：`docs/paradigm-decisions.md`（3 场景判定表 + 判定依据 + 反例）

## 精读笔记（3 条，能复述才算）

1. **workflow 与 agent 的分界是「路径由谁定」：代码定路径是 workflow，模型定路径才是 agent**
   - 出处：Anthropic《Building Effective Agents》原文：「Workflows are systems where LLMs and tools are orchestrated through predefined code paths. Agents, on the other hand, are systems where LLMs dynamically direct their own processes and tool usage, maintaining control over how they accomplish tasks.」同一页的总体建议：「we recommend finding the simplest solution possible, and only increasing complexity when needed.」五个 workflow 模式：prompt chaining、routing、parallelization（sectioning / voting）、orchestrator-workers、evaluator-optimizer。
   - 落点：`apps/api` 的编排层（后续 `runtime`）。先按代码路径把问答流程写死，只有「下一步依赖上一步结果且事先不可知」时才把控制权交给模型。

2. **Plan-and-Solve 是提示法，不是 agent：它把计划放进一次调用里，没有环境反馈**
   - 出处：Wang et al., arXiv:2305.04091。zero-shot CoT 的三类错误来自 46 道 GSM8K 错题：calculation 7%、missing step 12%、semantic misunderstanding 27%。PS 的做法是把「Let's think step by step」替换成「Let's first understand the problem and devise a plan to solve the problem. Then, let's carry out the plan and solve the problem step by step」。
   - 落点：`skills/prompts` 的规划提示，不是 `runtime`。它改善单次推理的完整性，但不会因为查询失败去改计划——那需要 ReAct 式循环。

3. **ReAct 的关键是 thought 不产生 observation：只有 action 才改变环境并把结果带回上下文**
   - 出处：Yao et al., arXiv:2210.03629 第 2 节：语言空间里的动作「does not affect the external environment, thus leading to no observation feedback」；论文摘要称 ReAct 通过调用 Wikipedia API「overcomes prevalent issues of hallucination and error propagation in chain-of-thought reasoning」，并提升可解释性。
   - 落点：`runtime/harness` 的循环与终止条件。thought 只是上下文里的推理，不能当「已查询」；每步必须落成真实工具调用，且终止条件（步数、预算、人工确认）由外层代码强制。

## 扫读：模块归属

| 资料 | 归属模块 | 一句话判断依据 |
|------|---------|---------------|
| workflow 五模式 | apps/api 编排层 | 路径由代码定义，属于应用编排而不是模型能力 |
| Plan-and-Solve | skills/prompts | 单次调用内的计划提示，无工具循环 |
| ReAct 循环 | runtime/harness | 控制「何时继续、何时停」属于运行时 |
| 场景判定与反例 | docs（本页与决策表） | 是设计决策记录，不产生运行时行为 |
| 步数/工具白名单/预算 | packages/contracts + runtime | 约束要写成契约字段并被执行层强制 |

## 产出

- `docs/paradigm-decisions.md`：判定三问（规则可枚举 → 纯代码；步骤/终止固定 → workflow；下一步依赖结果且不可知 → agent），3 个真实场景的判定、依据、反例，以及 agent 的四条边界（步数 8 / 工具白名单 / 只读 / 预算 + 人工确认）。
- 场景来自本项目：每日数据质量校验（纯代码）、指标问答（workflow）、退款率异常根因分析（agent）。

## 验证

| 检查 | 命令 | 结果 |
|------|------|------|
| 决策表存在且含 3 场景 | `grep -c '^| [ABC]\.' docs/paradigm-decisions.md` | 3 |
| 每个场景都有反例 | 同上人工核对 | A/B/C 三行「反例」列均有内容 |
| 判定顺序可复述 | 文档「三个问题」表 | 3 行，问法与去向一一对应 |
| agent 边界四条 | 文档 C 场景 | 步数 8、工具白名单、只读、预算，另有人工确认点 |
| agent 成本上限 | Day 4 价目手算 | 8 步 × ≤2k token ≈ 16k 输入 × $0.15/M ≈ $0.0024/次（上限假设） |
| 布局未漂移 | `bash infra/scripts/check_layout.sh` | `layout ok` |
| 资料可达 | `curl -o /dev/null -w '%{http_code}'` | Anthropic 页面与 ar5iv 均 200，正文可抽取 |
| 三形态实测对照 | — | **未实测**：网关未接模型、无真实流量，判定基于结构而非 benchmark |

## 与课程文档的偏差（主动讲出来）

1. 课程给的是通用场景，本表换成项目内三个真实场景（质量校验 / 指标问答 / 根因分析），否则只是复述教材。
2. 课程把 Plan-and-Solve 与 ReAct 并列为「范式」，实际前者是 prompt 方法（无环境反馈），后者才是循环范式；已在模块归属里拆开，避免把提示词当架构。
3. Anthropic 把 orchestrator-workers 归在 workflow 一类，容易被读成 agent；本表按原文归类，并说明当前不做 orchestrator-workers 的理由。
4. 课程只提「agent 要加限制」，本表落成可执行的四件套，并给了成本上限；步数 8 是暂定值，不是实测出来的最优值。
5. 「有界重试算不算 workflow」课程没讲：本表把 evaluator-optimizer 的一次迭代归 workflow，因为重试次数与分支仍由代码写死。
6. 本机没有真实流量与已接通的大模型，三形态的成功率/延迟差异无法实测；判定只基于结构证据，不编造 benchmark 数字。

## 三行收尾

- 卡点：Anthropic 页面与论文正文用 WebFetch 只拿到一两句摘要，模式定义拿不全；判定表最容易写成「背分类」，反例反而更难写。
- 绕过：直接 curl 抓 HTML 再抽正文，拿到五个模式的原文定义；把场景换成本项目真实的三件事，并给每个判定强制配一条「何时该升级/退化」。
- 下次：等网关接上模型后，用同一个问题分别跑 workflow 与 agent，把成功率、P95 延迟、单次成本三列回填这张表，替换现在的结构判断。

## 已知限制

- 三种形态没有实测对照，判定依据是结构与资料，不是本项目 benchmark。
- agent 的步数上限 8 与成本上限 $0.0024/次都是假设，需用真实任务标定。
- 场景 C 所需的根因分析数据与工具链在项目里还没有，判定是前瞻性的。
- 场景 B 的 1,200 token 输入来自 Day 4 的模拟场景，不是真实流量。
- 复述自测（合上资料讲 3 条笔记）由本人完成，本文只保证笔记与出处齐全。

## 验收

- [x] 能说清 workflow 与 agent 的分界是「路径由谁定」，并列出五个 workflow 模式
- [x] 3 个场景各自判定为纯代码 / workflow / agent，且有依据与反例
- [x] 能讲清 Plan-and-Solve 为什么不是 agent（无环境反馈）
- [x] 能讲清 ReAct 的 thought 与 action 的差别（是否产生 observation）
- [x] agent 的四条边界（步数、工具、只读、预算）已写成可执行约束
- [x] 能指出 orchestrator-workers 属于 workflow 而非 agent
- [x] 三行 notes 已记录
- [ ] 口述自测（由本人完成）
