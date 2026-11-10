# apps · 可运行入口

**放什么**：可以单独启动的进程入口——HTTP 服务、调试面板、CLI。编排、路由、拼装都在这里。
**不放什么**：可复用的业务逻辑、类型契约、基础设施配置。

- `api/`：FastAPI 服务，对外 HTTP。Python 依赖在 `apps/api/pyproject.toml`，**不在仓库根**。
- `web/`：TypeScript 调试面板，由根 `pnpm-workspace.yaml` 管理。

依赖方向：`apps → skills → packages`，不许反向。
