# contracts · TaskContract

DataAgent 单次任务的唯一形状：入参、出参、约束、失败码。Python 与 TS 各一份，由同一组 fixture 驱动一致性检查。

## 文件

| 文件 | 作用 |
|---|---|
| `python/task_contract.py` | Pydantic v2 模型 + `validate_task_output()` |
| `python/test_task_contract.py` | 4 组用例 + 约束 / 多余字段 / 优先级 |
| `ts/task_contract.ts` | Zod 等价 Schema + `validateTaskOutput()` |
| `ts/run_cases.ts` | 跑 fixture，输出每例判定 |
| `fixtures/cases.json` | 合法 / 缺字段 / 枚举越界 / 格式错乱 |
| `check_consistency.py` | 两侧逐例比较，漂移即退出码 1 |
| `metrics_dictionary.yaml` | 20 条零售指标：定义 / 公式 / 口径陷阱 / 数据源 |
| `python/check_metrics.py` | 指标字典结构门禁：20 条、id 唯一、3 条高风险 |

### Day 14 · 五类任务契约

| 文件 | 作用 |
|---|---|
| `specs/common.schema.json` | 共用形状：`metric` / `window` / `evidence` / 失败码枚举 |
| `specs/{compare,attribution,trend,anomaly,forecast}.schema.json` | 五类任务各一份 JSON Schema（Draft 2020-12） |
| `specs/{task}.failure_codes.json` | 该类任务会产出的失败码子集（契约元数据，**不是**产出字段） |
| `failure_codes.yaml` | 19 条失败码：轴 / 严重度 / HTTP / 触发条件 / 处理动作 |
| `python/contract_rules.py` | JSON Schema 表达不了的跨字段规则（残差闭合、区间包住点估计等） |
| `check_specs.py` | 契约文件门禁：schema 合法、五类齐全、码表与枚举对齐、子集覆盖全表 |
| `run_contract_cases.py` | 29 个正反用例：合法负载通过，违规负载按码拒绝 |

**两层校验，不能混**：`schema` 管形状与取值域（Draft 2020-12），`rules` 管字段之间的关系。
JSON Schema 没有「引用另一个字段值」的动作，所以 `delta = left - right`、`|residual| <= tolerance`
这类规则只能在 `contract_rules.py` 里，由 `verdict()` 先跑 schema 再跑 rules。

## 运行

```bash
# Python（本机 conda py311 已有 pydantic 2.13 / pytest / jsonschema）
cd packages/contracts
/Users/zhuyonghui/miniconda3/envs/py311/bin/python -m pytest -q

# TS（node 在登录 shell 的 fnm PATH 里）
zsh -lic 'cd packages/contracts && node ts/run_cases.ts'

# 一致性门禁
zsh -lic 'cd packages/contracts && /Users/zhuyonghui/miniconda3/envs/py311/bin/python check_consistency.py'

# 指标字典
/Users/zhuyonghui/miniconda3/envs/py311/bin/python packages/contracts/python/check_metrics.py

# Day 14 契约：文件门禁 + 正反用例
/Users/zhuyonghui/miniconda3/envs/py311/bin/python packages/contracts/check_specs.py
/Users/zhuyonghui/miniconda3/envs/py311/bin/python packages/contracts/run_contract_cases.py
```

## 规则

- 改字段先改两侧 Schema 与 `fixtures/cases.json`，再改调用方。
- 失败码只增不改；新增码要同时更新 Python `_ERROR_PRIORITY` 与 TS `mapIssues`。
- `max_results` 由入参传入，不在校验函数里写死。
- 原始 `raw` 随结果返回，供 Trace 使用；重试与 `RETRY_EXHAUSTED` 不在本模块。
- **五类任务契约**：新增失败码时，`failure_codes.yaml` 与 `common.schema.json#/$defs/FailureCodeName`
  必须同时改，且至少有一份 `specs/*.failure_codes.json` 认领它，否则 `check_specs.py` 退出码 1。
- **`failure_codes` 不进出参负载**：payload schema 是 `additionalProperties: false`，
  把码子集写进 payload 会让所有合法输出被拒。它是契约文件层的元数据，只存在于旁挂 JSON 里。
- 跨字段约束只写在 `contract_rules.py`，不要在提示词、SQL 或前端里再算一遍。

选型理由与风险见 [`docs/adr/0005-task-contract.md`](../../docs/adr/0005-task-contract.md)。