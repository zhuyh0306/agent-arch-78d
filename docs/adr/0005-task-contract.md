# 0005 · 任务契约与结构化输出方案

- Status: accepted
- Date: 2026-11-17
- Deciders: 项目负责人（单人维护）
- Supersedes: —

## Context

Day 7 把输出格式写在 system prompt 里，实测证明提示词只能约束形状的「意图」，不能保证形状正确：1.5B 模型三行结构、引用都守住了，但 `108/3600` 仍稳定算成 `2.8%`，信息不足组一度编造 `0%`。提示词是 PE 层，管不了「允许产出什么」；这一层必须由 Schema + 服务端二次校验兜住，属于 HE 层。

真实约束：

- 维护者 1 人，没有独立的契约代码生成流水线，也暂不引入 Buf / OpenAPI codegen 这类工具。
- 仓库是五层布局（ADR-0002），契约的唯一归属是 `packages/contracts/`，不是根目录 `contracts/`。
- Python 侧已有 Pydantic v2（conda `py311` 环境 2.13.4）；TS 侧由根 `pnpm-workspace.yaml` 管理，Node 24 可直接运行 `.ts`（类型擦除）。
- 当前 `apps/api` 仍是占位，没有真实调用链；今天的契约先以「可执行 fixture」形式存在，等 Day 15 接 API 时直接 import。
- 课程模板的 `enforce_constraints()` 把引用上限写死成 50，与 `TaskInput.max_results` 脱节；这是模板缺陷，不照抄。

## Decision

1. **Python 侧用 Pydantic v2，TS 侧用 Zod 3.23.8，不做代码生成。**
   - 两份 Schema 手写，但由同一份 `fixtures/cases.json` 驱动；
   - `check_consistency.py` 同时跑两侧，逐例比较判定与失败码，不一致即退出码 1。
2. **拒绝多余字段。** Python `ConfigDict(extra="forbid")`，Zod `.strict()`。模型塞进来的 `reasoning` 之类字段不得静默丢弃。
3. **失败码是稳定枚举，不是一个笼统错误。**
   - 课程四码：`PARSE_ERROR` / `MISSING_FIELD` / `ENUM_OUT_OF_RANGE` / `RETRY_EXHAUSTED`；
   - 本实现补三码：`UNKNOWN_FIELD`（多余字段）、`TYPE_ERROR`（类型错）、`CONSTRAINT_VIOLATION`（跨字段约束）；
   - 多错并发时按固定优先级取一个码：缺字段 > 枚举越界 > 多余字段 > 约束 > 类型，保证可测试、可断言。
4. **跨字段约束放在校验函数，不放在模型方法里。**
   `validate_task_output(raw, max_results, allowed_doc_ids)` 做三层：JSON 解析 → Schema 校验 → 引用数 / 来源真实性校验。`max_results` 来自入参，不写死。
5. **重试与 Trace 不在本模块实现。**
   本模块只回答「这条产出合法吗、失败码是什么」。重试次数、降级、`RETRY_EXHAUSTED` 由 Day 5 的循环层负责，原始 `raw` 随结果返回供 Trace 使用。
6. **契约先行。** 改字段时先改两侧 Schema 与 fixture，再改调用方；破坏性变更新写 ADR，不直接改本文件。

## Consequences

- 双份 Schema 存在漂移风险。缓解手段是 fixture + `check_consistency.py` 作为门禁；但它只能覆盖 fixture 里的用例，不能证明两份 Schema 完全等价。
- Zod 锁 3.23.8，避免 v4 错误码变化破坏失败码映射；升级需同步改 `mapIssues` 与 fixture。
- Node 直接跑 `.ts` 依赖类型擦除，不支持 `enum` 等需要运行时代码的语法；本仓库 TS 契约只用 `z.enum` 与类型别名，不受影响。若将来需要 `tsc` 构建，另写 ADR。
- 失败码优先级是人为约定，不是规范；新增错误类型时必须同时更新 Python 的 `_ERROR_PRIORITY` 与 TS 的 `mapIssues`，否则一致性检查会暴露。
- 契约描述会进入提示词并每轮计费（Day 4/8.2）；字段说明保持一句话，不写长段落。
- 尚未覆盖：数据契约的版本兼容、历史数据迁移、`RETRY_EXHAUSTED` 的真实重试链。前两项在 Day 8 自测追问里只给策略，落地留给后续天数。