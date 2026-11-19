# Day 9｜AI-Native 产品思维（90min）

日期：2026-11-17
用时：约 85 / 90
今日验收物：`docs/ai-native-product.md`（控制面 / 数据面分层图 + 4 个人工点位表 + Demo→产品 5 个必补项）

## 精读笔记（3 条，能复述才算）

1. **workflow 与 agent 的区别不是「有没有工具」，而是「路径由谁定」**
   - workflow：LLMs 与工具由**预定义代码路径**编排；agent：LLM **动态决定**自己的流程与工具使用。五个 workflow 模式是 prompt chaining / routing / parallelization / orchestrator-workers / evaluator-optimizer。
   - 原文的总体建议是「find the simplest solution possible, and only increasing complexity when needed」；复杂化要用可观测的收益换，不是默认升级。
   - 产品含义：路径越由模型定，控制面与人工点位越不能省。今天的分层图把「允许什么」放在控制面，把「每次怎么跑」放在数据面。
   - 落点：`docs/ai-native-product.md` 第 1、2 节。

2. **技术雷达的四环是「证据强度」，不是「技术好坏」**
   - Adopt：可以认真考虑用；Trial：能用但未完全验证；Assess：值得看，未必适合现在；Caution：有负面经验，考虑替代或避开。
   - 本期（Vol 35，2026-11）与本项目直接相关的：agent sandboxing 在 Adopt；LiteLLM、Temporal、risk-tiered human oversight 在 Trial；**human-in-the-loop theater 在 Caution**。主题之一是 harness engineering at scale，正好对应我们正在搭的 Harness / 控制面。
   - 产品含义：人工点位要按风险分级，只拦高后果动作；全部审批会把注意力耗光，最后变成点通过，也就是 radar 警告的 theater。
   - 落点：`docs/ai-native-product.md` 第 3 节的三条反 theater 规则。

3. **AI 产品的能力上限由异常路径决定，不由顺利路径决定**
   - 顺利路径只证明模型「能答」；异常路径决定用户「敢不敢信」。控制面决定允许什么，数据面处理每次请求，HITL 是把控制面的策略落到数据面上的可执行点。
   - Day 7 的实测是直接证据：1.5B 守住三行结构与引用，却把 `108/3600` 稳定算成 `2.8%`。形状正确不等于事实正确；产品必须展示计算依据，并把算术下沉到工具，否则用户无法判断这个数字该不该信。
   - 落点：`docs/ai-native-product.md` 第 5 节的异常路径表：用户看到「结论 + 依据 + 下一步」，内部看到「原始产出 + 失败码 + 重试 + 成本」。

## 扫读：模块归属

| 产出 | 归属模块 | 一句话判断依据 |
|---|---|---|
| 控制面 / 数据面分层图 | docs | 是架构与职责边界，不是可运行代码 |
| 4 个人工点位表 | docs | 是产品与治理策略，后续在 Gateway / Runtime 落地 |
| 异常路径用户文案 | prompts + docs | 文案来源是 `system_v1.md`，策略判断在文档 |
| 失败码与重试 | packages/contracts | Day 8 已定义，H3 直接消费 |
| Trace / 审计 | infra/observability | Langfuse 提供数据，控制面消费 |
| 四层职责展开 | docs（Day 10） | 今天只给分层与点位，`architecture.md` 再展开 |

## 产出

- `docs/ai-native-product.md`：两张 Mermaid 图（分层图、HITL 门禁图）、层职责表、4 点位表、5 个必补项、6 类异常路径的用户可见行为。
- `docs/README.md`：索引补入新文档。
- 关键结论：控制面慢而可审批，数据面快而可观测；人工点位只拦高后果动作，且必须有上下文、真拒绝权、超时默认动作。

## 验证

| 检查 | 方法 | 结果 |
|---|---|---|
| 分层图可渲染 | 从 `docs/ai-native-product.md` 抽取 Mermaid 块，用本机 Chrome + 离线 mermaid bundle 渲染 | 13 个节点，`title=RENDERED` |
| HITL 图可渲染 | 同上 | 16 个节点，`title=RENDERED` |
| 4 个点位齐全 | 图与表中 H1–H4 | 发布审批 / 高后果动作 / 校验失败转人工 / 抽样审计 |
| 5 个必补项齐全 | 第 4 节表格 | 身份租户 / 契约失败码 / Trace 证据 / 成本配额 / 评测发布门 |
| 布局未漂移 | `bash infra/scripts/check_layout.sh` | `layout ok` |

渲染说明：本机 `mmdc` 未安装，npm 官方源与 npmmirror 均 DNS 不可达；改用本机备份中的 `mermaid.min.js` 离线渲染，临时 HTML 与截图只放在 `/tmp`，不入库。这一步验证的是语法与可渲染性，不是最终排版审美。

## 与课程文档的偏差（主动讲出来）

1. 下载目录里没有 Day 9 的独立课程文档（只有 Day 1–8）；今天按 `plan.md` 的验收物与指定阅读推进，不虚构原文。
2. 课程要求「一张架构分层图」；实际拆成两张：分层图讲职责，HITL 门禁图讲审批点。单图 19 节点、26 条边时反馈环把请求链拉成倒序，拆开后两张都可读。
3. 课程说「4 个人审点」，没有给具体位置；本文把它落成 H1 发布 / H2 高后果动作 / H3 校验失败 / H4 抽样审计，并补了超时默认动作。点位是设计选择，不是原文规定。
4. ThoughtWorks Radar 是 2026-11 的第 35 期；radar 的环会随版本变化，本文引用的是本期快照。
5. Day 7 的 2.8% 是 1.5B 本地模型的结果，不能外推到强模型；这里只用它证明「形状与事实要分开校验」，不宣称所有模型都算错。

## 三行收尾

- 卡点：单张分层图把控制面、数据面、重试、Trace 和 4 个点位塞在一起，Mermaid 自动布局被反馈环拉成倒序，节点文字也被挤成三行。
- 绕过：拆成「分层图 + HITL 门禁图」；分层图去掉 Trace→审计的回边，让请求链自上而下；反馈关系改由文字说明。
- 下次：画架构图先按「读者要回答的问题」拆图，不要按「系统里有多少组件」画；一张图只回答一个问题。

## 已知限制

- 分层图是概念设计，没有对应的部署验证；Gateway / Runtime / Harness 在 `apps/api` 里仍是占位。
- HITL 只定义了点位与默认动作，没有实现审批 UI、超时队列或审计查询。
- 异常路径文案是设计稿，没有做用户测试；「结论 + 依据 + 下一步」是否足够，需要真实用户验证。
- 控制面与数据面的边界在单机项目里偏理想化；实际部署时 Gateway 可能是单点（ADR-0003 已登记）。
- 未读 ThoughtWorks Radar 的完整 PDF，只用了首页四环定义与本期主题摘要。

## 验收

- [x] 五层与四层职责能对上：PE / CE / HE / LE / GE 分别落在 prompt、context、harness、loop、编排
- [x] 控制面 / 数据面分界画得出，且能说清各自不放什么
- [x] 4 个人工点位有触发条件、审批人视图、动作与超时默认
- [x] Demo→产品 5 个必补项各有验收信号
- [x] 「模型答错时用户看到什么」有 6 类异常路径的具体文案
- [x] 两张 Mermaid 图从文档本体渲染通过
- [x] 产物已入 `docs/`，索引可检索
- [x] 3 行 notes（卡点 / 绕过 / 下次）已写
- [ ] 口述自测（由本人完成）