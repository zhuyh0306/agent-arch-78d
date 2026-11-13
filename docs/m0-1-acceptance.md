# M0-1 基线验收记录

日期：2026-11-10 ｜ 运行时：podman 6.1.4（VM `podman-machine-default`，4C / 6 GiB）
结论：**通过**。环境 10/10，闭环完成一次 completion + 一条 Langfuse trace，四类基线数已记录；无阻塞项，遗留 4 项见文末。

## 三项验收

| 项 | 判定标准 | 证据 | 结果 |
|----|---------|------|------|
| 环境绿 | `infra/scripts/env_check.sh` 退出码 0 | `10 checks passed` | 通过 |
| 闭环通 | `infra/scripts/smoke.sh` 输出 `smoke ok` | completion 返回中文答案；trace `2b3ba91ae1964fa1a6028428c5d61397` | 通过 |
| 基线数 | 环境 / 闭环 / 成本 / 资源四类都有数字与口径 | 见下表 | 通过 |

## 基线数

| 类别 | 指标 | 值 | 口径 |
|------|------|----|------|
| 环境 | 9 个容器从 `up -d` 到创建完成 | 17.7 s | `/usr/bin/time -p podman compose up -d`（镜像已在本地） |
| 环境 | 从起栈到 10/10 全绿 | 约 30–35 s | 起栈 20 s 时首跑为 7/10（Langfuse、LiteLLM 未就绪），等健康端点后复跑 |
| 闭环 | smoke 端到端耗时 | 8.46 s | `/usr/bin/time -p ./scripts/smoke.sh`（含最多 60 s 的 trace 轮询，实际很快命中） |
| 闭环 | 模型调用延迟 | 2.571 s | Langfuse observation `latency` |
| 闭环 | token 用量 | 输入 41 / 输出 34 / 合计 75 | Langfuse observation `usage` |
| 闭环 | 成本 | 0 | 本地 Ollama，`calculatedTotalCost=0` |
| 成本 | 云端月成本（模拟场景） | $7.39 / 月 | Day 4：Flash 谷时命中缓存，1,000 次/天 × 30 天 |
| 成本 | 云端最贵对照 | $72.55 / 月 | Day 4：V4-Pro 峰时未命中，同流量 |
| 资源 | 8 个常驻容器实际内存 | 2.47 GiB | `podman stats --no-stream` 求和 |
| 资源 | compose 内存上限合计 | 5.4 GiB | 各服务 `mem_limit` 求和，VM 共 6 GiB |
| 资源 | 模型上下文窗口 | 32,768 | Ollama `qwen2.5:0.5b` 的 `context_length` |

## 与 Day 1（colima）的对照

| 指标 | Day 1 · colima | Day 6 · podman | 说明 |
|------|---------------|----------------|------|
| env_check | 10 checks passed | 10 checks passed | 持平 |
| trace | `85d6cf3cd912496ab9b82160cd701e17` | `2b3ba91ae1964fa1a6028428c5d61397` | 均能在 `/trace/<id>` 打开 |
| 模型延迟 | 3.163 s | 2.571 s | 单样本，不据此下结论 |
| token 用量 | 41 / 29 / 70 | 41 / 34 / 75 | 输入一致说明提示未漂移，输出随采样变化 |
| 起栈耗时 | 未记录 | 17.7 s + 约 30–35 s 全绿 | 本次补测 |
| 运行时 | colima（约 5.7 GiB） | podman VM（6 GiB） | Docker Desktop 被公司策略禁用后的迁移 |

## 本周结论

1. 运行时迁移完成：Day-1 的 8 个常驻容器在 podman 下整体跑通，Day 3/4 挂着的「未在 podman 下复跑」关闭。
2. pgvector 待实测关闭：stock `postgres:16-alpine` 的 `pg_available_extensions` 中 `vector` 计数为 0，`CREATE EXTENSION vector` 报缺 `vector.control`——ADR-0004 里「复用 Postgres 需先换镜像」的前提已被直接验证。`hnsw.iterative_scan` 的返回条数差异仍要等 pgvector 镜像，补做日不晚于 Day 16。
3. 成本基线可用：本地路由成本 0；云端模拟场景 $7.39–$72.55/月，差异主要来自模型、峰谷与缓存命中。
4. 资源是硬约束：上限合计 5.4 GiB 对 6 GiB 的 VM，同时还在跑另一套 milvus 栈；扩展实验前先看 `podman stats`。
5. 范式判定与风险登记册已落库：`docs/paradigm-decisions.md`、`docs/risk-register.md`。

## 阻塞项与遗留

- 阻塞项：无。首跑 7/10 是启动时序，不是故障；等健康端点后 10/10。
- 遗留 1：`hnsw.iterative_scan` 行数差异未测（缺 pgvector 镜像），不晚于 Day 16。
- 遗留 2：本地 `main` 领先远端 3 个提交未推送（GitHub IP 阻断）。
- 遗留 3：远端 URL 内嵌明文 PAT，待轮换（风险 R5）。
- 遗留 4：Day 4/5/6 的「口述自测」由本人完成。

## 复现

```bash
cd infra
podman machine start          # VM 不会开机自启
podman compose up -d
# Langfuse / LiteLLM 约需 30–40 秒；等健康后复跑，首跑红不代表故障
./scripts/env_check.sh        # 期望 10 checks passed
./scripts/smoke.sh            # 期望 smoke ok，并打印 trace 链接
```
