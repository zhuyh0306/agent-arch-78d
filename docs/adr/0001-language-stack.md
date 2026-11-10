# 0001 · 语言栈：Python + TypeScript 双栈

- Status: accepted
- Date: 2026-11-10
- Deciders: 项目负责人

## Context

Agent 的编排、检索与评测需要 Python 生态：litellm、langfuse、qdrant-client 的可用实现都在 Python，且本项目 Day 1 已经在用 LiteLLM 与 Langfuse。

调试面板与对外类型契约需要 TypeScript。但本机当前状态是：uv 0.13.7 可用、Python 3.11 已装；PATH 上没有 node，`pnpm` 存在但无法启动（`env: node: No such file or directory`，Day 2 实测）。因此 TS 侧现在只能落目录与 workspace 声明，不能安装依赖或跑构建。

全用 TypeScript：Agent 编排和观测生态要自己造轮子。
全用 Python：调试面板要么用服务端模板，要么另起一套前端组件，维护成本落到一个人头上。

## Decision

Python 负责 `runtime` / `skills` / `eval`（`apps/api`、`skills/`、`eval/`）；
TypeScript 负责 `contracts` / `apps/web`。
契约以 `packages/contracts` 下的 OpenAPI 为唯一真相源，两端类型由生成器产出，不手写第二份。

Python 版本锁 3.11（`apps/api/.python-version`），与 Day 1 基线一致。

## Consequences

+ 每种职责用各自生态里最成熟的工具，不互相将就
+ 调试面板可以直接用 React 生态，不和 Python 的模板方案纠缠
- 开工前必须先补 Node（≥20）：否则 `apps/web` 只有目录，`pnpm-workspace.yaml` 也跑不起来
- CI 要同时跑 uv 与 pnpm 两套工具链
- 契约变更多一道生成步骤，生成物要入库并做一致性校验
- 单人维护两套语言，切换成本真实存在；不写代码的层（contracts）会增加讨论成本

## Superseded by

—
