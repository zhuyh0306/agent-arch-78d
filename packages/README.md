# packages · 跨应用复用

**放什么**：类型契约、OpenAPI 定义、客户端 SDK。
**不放什么**：业务逻辑、环境配置、任何 `apps/` 里的东西。

- `contracts/`：唯一真相源。`python/` 与 `ts/` 各一份 Schema，`fixtures/` 驱动双语言一致性门禁；先改契约与 fixture，再改调用方。
- `sdk/`：调用本服务的客户端，供 `apps/web` 或外部集成使用。

这一层最稳定，所以依赖方向只允许别的层指向它。
