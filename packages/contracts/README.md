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

## 运行

```bash
# Python（本机 conda py311 已有 pydantic 2.13 / pytest）
cd packages/contracts
/Users/zhuyonghui/miniconda3/envs/py311/bin/python -m pytest -q

# TS（node 在登录 shell 的 fnm PATH 里）
zsh -lic 'cd packages/contracts && node ts/run_cases.ts'

# 一致性门禁
zsh -lic 'cd packages/contracts && /Users/zhuyonghui/miniconda3/envs/py311/bin/python check_consistency.py'

# 指标字典
/Users/zhuyonghui/miniconda3/envs/py311/bin/python packages/contracts/python/check_metrics.py
```

## 规则

- 改字段先改两侧 Schema 与 `fixtures/cases.json`，再改调用方。
- 失败码只增不改；新增码要同时更新 Python `_ERROR_PRIORITY` 与 TS `mapIssues`。
- `max_results` 由入参传入，不在校验函数里写死。
- 原始 `raw` 随结果返回，供 Trace 使用；重试与 `RETRY_EXHAUSTED` 不在本模块。

选型理由与风险见 [`docs/adr/0005-task-contract.md`](../../docs/adr/0005-task-contract.md)。