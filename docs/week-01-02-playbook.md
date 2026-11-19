# 前两周实战手册

> 用法：按场景查，不从头读。命令都在本机验证过；路径按当前仓库写死，换机器先改 `ROOT`。
>
> ```bash
> ROOT=/Users/zhuyonghui/Documents/dev-learnning-code/agent-arch-78d
> PY=/Users/zhuyonghui/miniconda3/envs/py311/bin/python
> COST_PY=/Users/zhuyonghui/.venvs/agent-arch-cost/bin/python
> ```
>
> 记忆版结论见 [`week-01-02-memory.md`](week-01-02-memory.md)。

## 1. 新机器 30 分钟复现

### 1.1 先验工具（1 分钟）

```bash
podman --version
ollama --version
uv --version
zsh -lic 'node -v && pnpm -v'
/Users/zhuyonghui/miniconda3/envs/py311/bin/python -V
```

预期：podman 6.x、uv 0.13.x、Node 24.x、pnpm 11.x、Python 3.11.x。
任何一个缺失，先补工具，不要先拉容器。

### 1.2 起栈（约 5 分钟，镜像已在本机时 1 分钟）

```bash
podman machine list
podman machine start          # 已在运行会提示，无害
cd /Users/zhuyonghui/Documents/dev-learnning-code/agent-arch-78d/infra
cp .env.example .env          # 仅首次；填 LANGFUSE_ENCRYPTION_KEY 等
podman compose up -d
```

预期：9 个服务定义、8 个常驻容器；镜像已在本机时约 **17.7 s** 创建完成。

### 1.3 等健康，再验收

```bash
curl -sf http://localhost:3000/api/public/health
curl -sf http://localhost:4000/health/liveliness
cd /Users/zhuyonghui/Documents/dev-learnning-code/agent-arch-78d/infra
./scripts/env_check.sh
./scripts/smoke.sh
```

预期：约 **30–35 s** 后 `env_check.sh` 输出 `10 checks passed`、退出码 0；`smoke.sh` 输出 `smoke ok`，约 **8.5 s**。
**首跑红不是故障**：Langfuse / LiteLLM 还在启动，等两个健康端点都 200 再复跑。起栈前跑 `env_check` 应当全红，这是脚本自检。

## 2. 每日最小验收（5 分钟）

```bash
ROOT=/Users/zhuyonghui/Documents/dev-learnning-code/agent-arch-78d
PY=/Users/zhuyonghui/miniconda3/envs/py311/bin/python

bash "$ROOT/infra/scripts/check_layout.sh"

(cd "$ROOT/packages/contracts" && "$PY" -m pytest -q)

zsh -lic "cd $ROOT/packages/contracts && node ts/run_cases.ts && $PY check_consistency.py"

(cd "$ROOT/apps/api" && "$PY" -m pytest -q && "$PY" tenant_policy.py)
```

预期：

- `layout ok`
- contracts：`6 passed`；`contracts agree`
- tenant：`5 passed`；`5 attacks denied, 1 control allowed`

栈在跑时再加：

```bash
(cd "$ROOT/infra" && ./scripts/env_check.sh && ./scripts/smoke.sh)
```

## 3. 改提示词：标准流程

1. 改 `skills/prompts/system_v1.md`，不直接改用户输入里的约束。
2. 需要新场景时，先加 `skills/prompts/cases.json` 的用例（越权 / 信息不足 / 正常）。
3. 跑对照，**同一模型、同一上下文**分别跑 v0 与 v1：

```bash
cd /Users/zhuyonghui/Documents/dev-learnning-code/agent-arch-78d
/Users/zhuyonghui/.venvs/agent-arch-cost/bin/python skills/prompts/contrast_test.py
CONTRAST_MODEL=balanced /Users/zhuyonghui/.venvs/agent-arch-cost/bin/python skills/prompts/contrast_test.py
```

4. 打开 `skills/prompts/contrast-record.md`，把逐组判定写进 `contrast-conclusion.md`。
5. 算 token 增量：`system_v1` 每多 1 token，按 30,000 次/月就是多 30k token；461 token 约 13.83M/月，Flash 谷时命中约 $0.04/月、未命中约 $2.07/月。
6. **不允许**只说「感觉更好了」；没有对照记录不算改版。

红线：

- 算术错、缺数据、越权，不要靠改措辞硬修；先按「症状 → 层」定位。
- 加规则可能挤掉已有规则（1.5B 实测：加第 6 条后拒答退化）；一次只加一条，跑完再留。

## 4. 改契约：标准流程

顺序必须是：**两侧 Schema → fixture → 门禁 → 调用方**。

```bash
cd /Users/zhuyonghui/Documents/dev-learnning-code/agent-arch-78d

# 1) 改 Python 与 TS
#    packages/contracts/python/task_contract.py
#    packages/contracts/ts/task_contract.ts

# 2) 改用例与期望失败码
#    packages/contracts/fixtures/cases.json

# 3) 两侧分别跑
(cd packages/contracts && /Users/zhuyonghui/miniconda3/envs/py311/bin/python -m pytest -q)
zsh -lic 'cd /Users/zhuyonghui/Documents/dev-learnning-code/agent-arch-78d/packages/contracts && node ts/run_cases.ts'

# 4) 一致性门禁
zsh -lic 'cd /Users/zhuyonghui/Documents/dev-learnning-code/agent-arch-78d/packages/contracts && /Users/zhuyonghui/miniconda3/envs/py311/bin/python check_consistency.py'
```

预期：`contracts agree`，退出码 0；漂移时退出码 1，先修 Schema，不改期望值来「凑绿」。

新增失败码时，两处必须同步：

- Python `_ERROR_PRIORITY`
- TS `mapIssues`

## 5. 加一条租户越权用例

1. 在 `apps/api/fixtures/tenant_cases.json` 加一条，字段：`id` / `attack` / `hop` / `auth_tenant` / `target_tenant` / 可选 `tenant_in_filter` / `expect`。
2. `expect` 用稳定值：`DENY:TENANT_MISMATCH`、`DENY:FILTER_MISSING`、`DENY:TENANT_MISSING` 或 `ALLOW`。
3. 跑：

```bash
cd /Users/zhuyonghui/Documents/dev-learnning-code/agent-arch-78d/apps/api
/Users/zhuyonghui/miniconda3/envs/py311/bin/python -m pytest -q
/Users/zhuyonghui/miniconda3/envs/py311/bin/python tenant_policy.py
```

4. 只加拒绝用例不够：保留至少一条 `db-own-read` 对照，防止「一律拒绝」假通过。

5. 模拟器只证明逻辑；真实 RLS 要单独跑。Day 12 的最小复测流程与结果见 [`week-02-review.md`](week-02-review.md) 第 6 节。关键写法：

```sql
-- 先 permissive 放行，再 restrictive 收窄；只写 restrictive 会默认全拒
CREATE POLICY orders_app_rw ON orders AS PERMISSIVE TO app_rw
  USING (true) WITH CHECK (true);
CREATE POLICY orders_tenant_isolation ON orders AS RESTRICTIVE TO app_rw
  USING (tenant_id = nullif(current_setting('app.tenant_id', true), ''))
  WITH CHECK (tenant_id = nullif(current_setting('app.tenant_id', true), ''));
```

预期：设定 tenant-a 后只读到 tenant-a；不设上下文读到 0 行；跨租户写入被拒；超级用户绕过。

## 6. 重算成本

```bash
cd /Users/zhuyonghui/Documents/dev-learnning-code/agent-arch-78d/eval/cost
/Users/zhuyonghui/.venvs/agent-arch-cost/bin/python cost_model.py
```

改价只改 `prices.csv`，改场景只改 `scenario.json`；脚本不应写死价格与 token 数。
复现检查：连跑两次，输出应逐字节一致。

看数时先问三句：

- 输入 / 输出各多少 token？
- 缓存命中按哪个前缀算？稳定前缀占输入多少？
- 月成本按多少次假设？这里默认 1,000 次/天 × 30 天。

## 7. 画 / 改架构图

Mermaid 源直接写在 Markdown 的 ` ```mermaid ` 块里。

- **日常预览**：GitHub、GitLab 或编辑器的 Mermaid 插件。
- **离线渲染**：本机没有 `mmdc`，npm 源也不稳定；已验证的方式是用本机 Chrome + 本地 `mermaid.min.js` 渲染（步骤见 Day 9 / Day 10 笔记）。临时文件只放 `/tmp`，不入库。
- **提交前检查**：`subgraph` 与 `end` 成对；节点 ID 先定义后引用；标签里有括号、斜杠时加引号。

图超过 20 节点或 25 条边时，先按「读者要回答的问题」拆成两张；别用一张图同时回答「谁负责什么」和「数据怎么走」。

## 8. 故障速查

| 现象 | 先查 | 处理 |
|---|---|---|
| `env_check` 7/10，Langfuse / LiteLLM 返回 `000` | 启动时序 | 等 `/api/public/health`、`/health/liveliness` 都 200，再复跑 |
| completion 200 但 trace 为空 | `podman ps` 是否有 worker；三个 `LANGFUSE_*` | 起 worker；密钥缺失只报错不打印 |
| `/v1/models` 看不到 `balanced` | 网关是否重载配置 | `podman compose up -d --force-recreate litellm` 后再查 |
| `podman compose up` 报依赖容器状态异常 | 依赖服务是否在重启 | `podman compose ps` + 看对应日志，别先删卷 |
| `node: command not found` | 当前不是登录 shell | 用 `zsh -lic 'node -v'`；命令统一放登录 shell 里跑 |
| `No module named pydantic` | 用了 `apps/api/.venv` | 改用 conda `py311` 的 Python |
| PyPI 清华源 DNS 失败 | 镜像可达性 | 换 `pypi.org` 或阿里云；别在 DNS 上耗超过 15 分钟 |
| npm / pnpm 源 DNS 失败 | 本地 store 是否已有包 | 先用已有 `node_modules`；装不了就换离线方案，不硬扛 |
| `CREATE EXTENSION vector` 报缺 `vector.control` | 镜像是否带 pgvector | stock `postgres:16-alpine` 不含；换 `pgvector/pgvector` 镜像（待做） |
| 宿主 9000 / 9001 起不来 | 是否被 SSH 转发占用 | MinIO 已改 19000/19001；不要杀那个转发 |
| Langfuse heap limit | 容器内存上限 | 已提到 web 1536m / worker 1024m；仍崩就看日志与 VM 内存 |
| 网关 401 | `infra/.env` 的 key 是否与请求一致 | 用 `sed` 在命令内取值，禁止 `echo` 密钥 |

## 9. 提交前检查

```bash
cd /Users/zhuyonghui/Documents/dev-learnning-code/agent-arch-78d
git status --short
git diff --stat
```

先只暂存要提交的具体文件，再扫描**暂存差异**。不要用 `grep` 扫整个工作树，否则 `infra/.env` 里的真实 key 会被打印出来。

```bash
git add <具体文件>          # 不用 git add -A
git diff --cached | grep -nIE "gh[p]_[A-Za-z0-9]{20,}|AK[I]A[0-9A-Z]{16}|s[k]-[A-Za-z0-9_-]{20,}|_aut[h]Token=|-----BEGIN [A-Z ]*PRIV[A]TE KEY-----" \
  || echo "no secret patterns"
```

提交规则：

- 只 `git add` 具体文件，不用 `git add -A`。
- 不提交 `.env`、密钥、`.venv`、`node_modules`。
- 用 Conventional Commits：`feat(scope): ...` / `docs(scope): ...` / `fix(scope): ...`。
- 用户没让提交就不提交；用户没让推送就不推送。

## 10. 验收证据模板

每条验收都写成四列，别只写「通过」：

| 检查 | 命令 | 结果 | 口径 |
|---|---|---|---|
| 环境 | `./scripts/env_check.sh` | `10 checks passed`，退出 0 | 起栈约 35 s 后 |
| 闭环 | `./scripts/smoke.sh` | `smoke ok`，trace 可打开 | 单次 completion，非回归集 |
| 契约 | `check_consistency.py` | `contracts agree` | 4 组 fixture |
| 租户 | `tenant_policy.py` | 5 attacks denied, 1 control allowed | 策略模拟，非真实 RLS |

「结果」必须能原样粘贴；「口径」写清前提，避免拿不同条件的数字互相比较。

## 11. 每周复盘 30 分钟

1. 从本周产出里挑**最不满意的一项**，写下当时为什么没做透。
2. 找共性根因：是时间不够、资料不可达，还是验收标准写成了「跑通过一次」？
3. 把根因转成制度：命令、门禁、风险登记册条目，而不是「下次注意」。
4. 更新 `notes/day-XX.md` 的三行收尾与「已知限制」。
5. 只有能重放的命令与原样输出，才算闭环。

## 12. 本机坑速查

- Docker Desktop 被公司策略反复卸载；统一用 podman，VM 不自启，先 `podman machine start`。
- compose 文件名仍是 `docker-compose.yml`，不要改。
- 容器访问宿主 Ollama 用 `host.docker.internal:11434` 或 `host.containers.internal:11434`。
- MinIO 映射在 19000/19001；容器内仍走 9000。
- Node 在 fnm 的登录 shell PATH 里，非登录 shell 找不到。
- Python 有两个环境：conda `py311` 跑测试与 lint；`agent-arch-cost` 跑 `tiktoken` 成本脚本。
- GitHub 按 IP 阻断，推送失败先换网络，不要反复重试；PAT 在 remote URL 里的风险已登记，不要外传。
- HuggingFace 直连超时，下载前设 `HF_ENDPOINT=https://hf-mirror.com`。
- brew 自动更新会卡，装包前设 `HOMEBREW_NO_AUTO_UPDATE=1`。