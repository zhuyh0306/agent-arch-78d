# Day 2 · 仓库结构与工程约定

日期：2026-11-10 ｜ 计划时长 90min

> 注：Day 3 起本机 Docker 被公司策略禁用，运行时改为 podman。下文验证表里的 `docker compose config -q` 记录的是当时的命令，现在等价于 `podman compose config -q`。

今日验收物：`repo 骨架` + `docs/adr/0001~0003`

## 三条笔记

1. **ADR 里不写就会被反复问的是 Context，不是 Decision**
   - 硬约束：Context 必须写“当时的约束、指标、前提”，不能写成对选项的评价。Day 2 的三篇里，Context 写的是本机实际条件（无云厂商 key、Node 缺失、Langfuse v3 需要 ClickHouse、单人名下），而不是“Python 更好用”。
   - 改它的代价：Decision 写错还能补新 ADR 并标 superseded；Context 写空，半年后没人知道当时为什么排除另一个方案，只能重新论证一遍。
   - 边界：ADR 只管“改起来要动半个仓库”的决定；命名、某个子目录叫什么不写。

2. **依赖倒置在代码层面倒置的不是控制流，是“稳定性方向”**
   - 硬约束：依赖必须指向更稳定的一端。`packages`（契约）最稳定，所以在最里面；`apps` 最易变，所以在最外面。
   - 改它的代价：`packages` 一旦 import `apps`，就出现反向依赖，单测和按层构建同时失效，改一个文件要动整个仓库。
   - 本项目落点：`apps/api` 可以依赖 `skills` 与 `packages`；`skills` 之间不互相调用；`infra` 不被任何代码 import。

3. **本项目最容易被反向依赖的是 `infra`**
   - 因为 Day 1 的 compose、`.env` 和脚本曾经和实验代码放在同一个扁平目录里，顺手从代码里读 `infra/.env` 或 import `infra/scripts` 的诱惑很大。
   - 判定线：业务代码需要某个配置值时，经环境变量注入，不读 `infra/` 下的文件；`infra/` 只被部署流程引用。
   - 这条线今天用目录 + README 声明，暂时没有 lint 强制；第 3 周接 CI 时再补规则。

## 产物

```
agent-arch-78d/
├─ apps/
│  ├─ api/              pyproject.toml（Python 3.11）+ uv.lock + main.py 占位
│  └─ web/              README 占位（Node 未装，暂不安装依赖）
├─ packages/
│  ├─ contracts/        .gitkeep
│  └─ sdk/              .gitkeep
├─ skills/
│  ├─ retrieval/        .gitkeep
│  └─ sql/              .gitkeep
├─ eval/
│  ├─ datasets/         .gitkeep
│  └─ scorers/          .gitkeep
├─ infra/
│  ├─ docker-compose.yml        ← Day 1 迁入（project name 仍是 agent-lab-day01）
│  ├─ litellm/config.yaml       ← Day 1 迁入
│  ├─ scripts/          env_check.sh、smoke.sh、minio_init.py、check_layout.sh
│  ├─ .env.example              ← Day 1 迁入
│  └─ README.md                 本层职责 + Day 1 基线运行说明
├─ docs/
│  ├─ README.md
│  └─ adr/0001-language-stack.md、0002-repo-layout.md、0003-gateway.md
├─ .gitignore           .env / .venv / node_modules / __pycache__
├─ pnpm-workspace.yaml  packages/* + apps/web
└─ plan.md、must-master.md、notes/、README.md（学习项目文档，留在根）
```

迁移时改了三处路径：compose 里 `./minio_init.py` → `./scripts/minio_init.py`；`env_check.sh` 与 `smoke.sh` 的 `cd` 从脚本目录改成上一级 `infra/`，因为 `.env` 在 `infra/`。

## 验证

| 检查 | 命令 | 结果 |
|---|---|---|
| 目录契约 | `./infra/scripts/check_layout.sh` | `layout ok` |
| compose 仍可解析 | `cd infra && docker compose config -q` | 退出 0 |
| `.env` 仍被忽略 | `git check-ignore -v infra/.env` | `.gitignore:1:.env` 命中 |
| Python 侧可建环境 | `uv sync --directory apps/api` | CPython 3.11.18，创建 `.venv` 成功 |
| TS 侧工具链 | `node -v` / `pnpm -v` | **失败**：PATH 上没有 node，pnpm 报 `env: node: No such file or directory` |

容器今天没有重新拉起：Day 2 的验收物是骨架与 ADR，不依赖栈在跑；compose 只做了静态校验。

## 三行 notes

```
卡点：pnpm 存在但本机没有 node，TypeScript 侧装不了依赖
绕过：今天只落目录与 pnpm-workspace.yaml，TS 依赖推迟到 web 真正开工前，并从 ADR-0001 记为已知限制
下次：环境基线里把 node/pnpm 也纳入 env_check.sh，别等要装依赖才发现缺
```

## 已知限制

- 本机未安装 Node，`apps/web` 目前只有 README；`pnpm-workspace.yaml` 未经 pnpm 实跑验证。
- `packages/`、`skills/`、`eval/` 是空壳，要到第 4–11 周才有真实内容；空目录靠 `.gitkeep` 保活。
- Day 1 的笔记里仍保留 `lab/day-01/...` 的原始路径，作为当天记录；当前路径以 `infra/README.md` 为准。
- 目录约束目前靠 `check_layout.sh` 手动跑，尚未接 CI。

## 自检清单

- [x] 五层目录职责能口述（`apps` 入口 / `packages` 契约 / `skills` 能力 / `eval` 评测 / `infra` 部署）
- [x] 依赖方向三条规则能写出来（`packages` 不依赖 `apps`；`skills` 不互调；`infra` 只被部署引用）
- [x] ADR 五段结构能默写（Title / Status / Context / Decision / Consequences）
- [x] repo 骨架已建，命令可复现（`check_layout.sh` + `uv sync`）
- [x] `adr/0001` 语言栈已写
- [x] `adr/0002` 目录结构已写
- [x] `adr/0003` 网关选型已写
- [x] 三行 notes 已记录并提交
