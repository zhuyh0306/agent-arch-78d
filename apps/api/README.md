# apps/api · DataAgent HTTP 入口

FastAPI 应用，负责接收请求、装配上下文、调用技能、返回答案与 trace 引用。

## 命令

```bash
uv sync --extra test        # 按 uv.lock 建/同步 .venv（含 pytest / httpx / mypy / ruff）
./run.sh                    # 起服务，默认 127.0.0.1:8000（PORT / HOST / LOG_LEVEL 可覆盖）
.venv/bin/uvicorn "dataagent.api.app:build_app" --factory --port 8000
uv run python main.py       # 同上，兼容入口

# 业务接口需要 API key（healthz 不需要）。
# 格式：key:tenant:principal，逗号分隔。未配置 = 全部拒绝（fail closed）。
export DATAAGENT_API_KEYS="dev-key-1:tenant-a:alice,dev-key-2:tenant-b:bob"
curl -s -H "X-API-Key: dev-key-1" localhost:8000/metrics/gmv
curl -s localhost:8000/healthz          # 探针，免鉴权

./check.sh                  # 门禁：ruff + mypy + pytest（48 个测试）
```

Python 版本锁在 `.python-version`（3.11）。

## 内部分层（ADR-0006）

```
apps/api/dataagent/
├── api/          FastAPI 外壳：路由 + 请求/响应翻译，不含业务规则
│   ├── deps.py       鉴权 + 租户解析（强制依赖）
│   └── routes/       health.py · metrics.py
├── domain/       业务概念，仅标准库
│   ├── health.py         探针语义、关键依赖判定
│   ├── tenant.py         TenantContext：已验证的租户，不可变
│   ├── tenant_policy.py  Day 11 五跳策略（原在 apps/api/ 包外）
│   └── auth.py           API key → TenantContext 的映射
├── agent/
│   ├── ports/    3 个端口：LLM / Tool / Repo（typing.Protocol）
│   ├── adapters/ 端口实现：EchoLLM / InMemoryTools / YamlMetricRepository
│   └── service.py 编排，只依赖 ports + domain
├── tools/        副作用边界：SandboxedToolExecutor（超时 → Day 14 失败码）
└── infra/        进程关注点 + 组合根：settings.py · container.py
```

依赖方向：`api → agent → ports → domain`；`infra` 是唯一点名具体适配器的地方。
方向由 `tests/test_layering.py` 用 AST 强制，不是靠 README 约定。

## 安全边界

- **租户只来自已验证的身份，不来自请求。** `X-Tenant-Id` 头与 `?tenant_id=` 参数都会被忽略；key 与租户一对一绑定。
- **未配置 `DATAAGENT_API_KEYS` 即全拒。** 没有「开发默认租户」这种兜底。
- `/healthz` 免鉴权（负载均衡器无 key），只返回依赖名与状态。
- 详细规则与验证结果见 [`docs/multi-tenancy.md` 第 9 节](../../docs/multi-tenancy.md)。

## 当前状态（Day 15）

- 三个端口都有实现，但**都是诚实的最小实现**：`EchoLLM` 回显、`YamlMetricRepository` 读 Day 13 字典、`InMemoryTools` 的 `metric_lookup` 调用即抛异常。
- `/healthz` 会真跑关键依赖，LLM 挂掉返回 503。
- 鉴权是**骨架级**：静态 key 表，无 OAuth/JWT/轮换/持久化。它是 `ApiKeyStore.authenticate()` 这个接缝，换真实 IdP 只改这一个适配器。
- 仍无数据库连接；`tenant_id` 已透传到路由层，但还没有任何 Repository 真正用它做行级过滤（那需要接业务库）。