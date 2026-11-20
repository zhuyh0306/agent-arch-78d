# infra · 部署与配置

**放什么**：compose 编排、网关配置、宿主机检查脚本、镜像构建文件。
**不放什么**：任何业务代码、业务常量、评测数据。

这一层不被代码依赖，只被部署流程引用。

## Day 1 基线栈

Day 1 的验收物就在这里：`docker-compose.yml` + `scripts/env_check.sh`。

| 服务 | 镜像 | 宿主机端口 | 用途 |
|------|------|-----------|------|
| postgres | `postgres:16-alpine` | 5432 | Langfuse 元数据 |
| redis | `redis:7-alpine` | 6379 | Langfuse 队列/缓存 |
| qdrant | `qdrant/qdrant:v1.12.4` | 6333/6334 | 向量库 |
| clickhouse | `clickhouse/clickhouse-server:24.3-alpine` | 8123 | Langfuse 事件存储（v3 必需） |
| minio | `cgr.dev/chainguard/minio:latest` | 19000/19001 | Langfuse 事件对象存储（v3 必需） |
| langfuse-web | `langfuse/langfuse:3` | 3000 | 控制台与查询 API |
| langfuse-worker | `langfuse/langfuse-worker:3` | — | 异步消费事件 |
| litellm | `ghcr.io/berriai/litellm:main-stable` | 4000 | 模型网关 |

三个说明：

- 原文列了五个服务，但 Langfuse v3 自己还要 ClickHouse 和 S3，所以实际是 8 个容器。
- 本机 9000/9001 被一个 SSH 端口转发占用，MinIO 改到 19000/19001，不要去杀那个转发。
- `docker.io/minio/minio` 和 `quay.io/minio/minio` 在本机都拉不下来（mirror 403 / quay 401），所以用本机已有的 Chainguard 构建；`scripts/minio_init.py` 用 LiteLLM 镜像里的 boto3 建桶，替代官方 `mc`。

## 模型来源

本机没有云厂商 key，但装有 Ollama，所以网关路由到本机的 `qwen2.5:0.5b`：

```bash
ollama pull qwen2.5:0.5b
```

换成 OpenAI / DeepSeek 只需要改 `litellm/config.yaml` 的 `model` 与 `api_key`，compose 不用动。

## 运行时

本机 Docker Desktop 被公司策略禁用，统一用 podman：

- `podman 6.1.4` + `podman-compose 1.6.0`，`podman compose` 会调用这个外部 provider。
- VM 不会开机自启，先 `podman machine start`，用 `podman machine list` 确认 `Currently running`。
- compose 文件名仍叫 `docker-compose.yml`（podman-compose 直接读），不要重命名。
- 容器内访问宿主 Ollama 用 `host.docker.internal:11434`，podman 下它与 `host.containers.internal` 都解析到 VM 网关（192.168.127.254），实测 VM 内 `curl` 返回 200；Ollama 只绑宿主 `127.0.0.1:11434` 也能通，靠的是 podman 的转发，不需要改 Ollama 监听地址。
- 脚本里的容器列表会优先用 `podman compose`，没有 podman 时回退 `docker compose`。

## 运行

```bash
cp .env.example .env      # 首次；填好各项，尤其是 64 位 hex 的 LANGFUSE_ENCRYPTION_KEY
podman machine start      # VM 未运行时
./scripts/env_check.sh    # 起服务之前应当全红，用来确认脚本本身有效
podman compose up -d      # 在 infra/ 下执行；首次会拉镜像，超过 15 分钟按止损规则处理
./scripts/env_check.sh    # 期望全部通过（起栈约 30–40 秒后再跑，首跑红先等健康端点）
./scripts/smoke.sh        # completion + Langfuse trace
```

Day 6 实测（镜像已在本机）：`up -d` 17.7 秒创建完成，约 30–35 秒后 10/10 全绿。首跑常见 Langfuse / LiteLLM 返回 `000`，那是启动时序不是故障；等 `/api/public/health` 与 `/health/liveliness` 都回 200 再复跑。

打开 <http://localhost:3000>，用 `.env` 里的 `LANGFUSE_ADMIN_EMAIL` / `LANGFUSE_ADMIN_PASSWORD` 登录；trace 也可以在 `scripts/smoke.sh` 输出的链接直接打开。

停止与清理：

```bash
podman compose down          # 保留数据卷
podman compose down -v       # 连数据一起删，下次重新初始化 Langfuse 项目
```

## Day 13 业务库

指标字典需要 8 张源表，业务数据放在独立的 `dataagent` 库（不复用 Langfuse 的 `postgres` 库）：

```bash
cd infra
podman compose up -d postgres
cd db
./apply.sh    # 建库 + 001 schema + 002 seed
./verify.sh   # 9 张表、租户隔离、跨租户写入、fail closed、超级用户绕过
```

细节见 [`db/README.md`](db/README.md)。约定：所有租户表 `tenant_id NOT NULL` + `FORCE ROW LEVEL SECURITY`，运行角色 `app_rw` 非 owner、`NOBYPASSRLS`；新表漏掉这两项视为未完成。

## 止损

原文规则：任何一步卡住超过 15 分钟，停止死磕，改为查文档或换最小简化实现。本目录的两处简化就是这条规则的产物：用本机 Ollama 代替云端模型；如果 Langfuse 起不来，先只保留 postgres/redis/qdrant/litellm 四个服务，把 trace 留到问题定位后再补。
