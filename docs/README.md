# docs · 决策记录

**放什么**：ADR（架构决策记录），以及支撑决策的矩阵、判定表与风险登记册。
**不放什么**：需求文档、教程、随手笔记。

- `adr/`：一篇一页，只增不改。改主意写新 ADR，并把旧的改成 `superseded`，不要覆盖原文。
- `selection-matrix.csv`：选型打分，权重可重算。
- `paradigm-decisions.md`：纯代码 / workflow / agent 的场景判定与反例。
- `ai-native-product.md`：控制面 / 数据面分层、4 个人工点位、异常路径的用户可见行为。
- `architecture.md`：企业级目标架构、四层职责边界、故障域与 `tenant_id` 贯穿。
- `multi-tenancy.md`：隔离三级选型、RLS 落地要点、5 条越权用例与迁移条件。
- `week-02-review.md`：第 2 周复盘、架构蓝图自评、RLS 阻塞项修复记录。
- `week-01-02-memory.md`：前两周速记，十句话 + 六张表 + 12 问自测。
- `week-01-02-playbook.md`：前两周实战手册，起栈、验收、改提示词 / 契约 / 租户用例、故障速查。
- `risk-register.md`：M0-1 风险与下周前置依赖。
