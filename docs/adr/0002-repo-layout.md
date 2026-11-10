# 0002 · 目录结构：按职责分，不按文件类型分

- Status: accepted
- Date: 2026-11-10
- Deciders: 项目负责人

## Context

仓库是 monorepo，同时含 Python 与 TypeScript。Day 1 的产物（compose、LiteLLM 配置、env_check/smoke 脚本）原先放在 `lab/day-01/` 扁平目录里，那是一次性实验的位置，不适合长期承接后续 77 天的产出。

两种分法：

方案 A 按文件类型分：`models/`、`utils/`、`services/`、`tests/`。
方案 B 按职责分：`apps/`、`packages/`、`skills/`、`eval/`、`infra/`。

方案 A 的问题：一个模块的代码会散落在 4–5 个顶层目录，依赖方向无法在目录层面表达，也没法按层做 lint 约束。
方案 B 的代价：新人要先理解五层职责才能找到文件；层建早了会出现空目录。

## Decision

采用方案 B。五层为 `apps / packages / skills / eval / infra`，外加 `docs/adr` 作为决策记录层。

- 依赖方向固定单向：`apps → skills → packages`；`infra` 独立，不被代码依赖。
- 目录层级最多四层。
- Day 1 的实验产物归入 `infra/`：`infra/docker-compose.yml`、`infra/litellm/`、`infra/scripts/`；`lab/` 不再保留。
- 每个顶层目录必须有一份 README，写清「放什么、不放什么」。
- `pyproject.toml` 放在 `apps/api/`，**不放仓库根**；根只放 `pnpm-workspace.yaml` 与 `.gitignore`。

## Consequences

+ 依赖方向以后可以用 lint 规则强制，而不是靠人记
+ 删除或替换某一层时，影响范围可枚举
+ 可以按层跑测试与 CI
+ Day 1 的产物有了长期位置，compose 挂载路径随之调整（`./scripts/minio_init.py`）
- 新人上手要先读这份 ADR，前几天找文件会慢
- 跨层共享逻辑必须下沉到 `packages/`，不能就近放
- 当前 `packages/`、`skills/`、`eval/` 还是空壳，要靠第 4–11 周填满；空目录用 `.gitkeep` 占位
- Day 1 笔记里的 `lab/day-01/...` 路径成为历史记录，需以 `infra/README.md` 为准

## Superseded by

—
