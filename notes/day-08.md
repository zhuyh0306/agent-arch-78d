# Day 8｜结构化输出与任务契约（120min）

日期：2026-11-17
用时：约 100 / 120
今日验收物：`packages/contracts/`（Python Pydantic + TS Zod + 一致性 fixture）+ `docs/adr/0005-task-contract.md`

## 精读笔记（3 条，能复述才算）

1. **Pydantic 的「validation」保证的是输出形状，不是输入真实性**
   - `model_validate()` 把不可信 dict 变成模型实例；失败抛一个 `ValidationError`，里面包含全部错误项（`exc.errors()`）。字段一旦通过，类型与约束就被保证。
   - 默认 `extra='ignore'` 会**静默丢掉**未声明字段，契约必须显式 `ConfigDict(extra="forbid")`，否则模型塞进来的 `reasoning` 之类字段会无声消失。
   - `Field(description=...)` 会进入 `model_json_schema()`，随 schema 一起发给模型，是「用契约提示模型」的入口。
   - 落点：`packages/contracts/python/task_contract.py`。

2. **JSON Schema 的默认值全是「宽松」：不写 required 就不必填，不写 additionalProperties 就允许多余字段**
   - `properties` 只声明形状，不声明必填；必填要单独写 `required`。
   - `additionalProperties` 默认是 true；要拒绝多余字段必须显式 `false`（Pydantic 的 `extra="forbid"`、Zod 的 `.strict()` 是同一件事的两种写法）。
   - `patternProperties` 的正则**不锚定**，`"p"` 会匹配 `"apple"`；要精确匹配得写 `^...$`。
   - Schema 是跨语言契约语言：Python 与 TS 都能表达同一份形状，这是双语言 fixture 的基础。
   - 落点：`fixtures/cases.json` + 两侧 Schema。

3. **结构化输出只约束形状，不保证事实与算术；服务端二次校验是最后一道**
   - 模型侧 schema 能减少自由文本解析，但仍可能漏字段、填错枚举；课程给出的失败链路是解析 → 校验 → 重试 → 降级 → 拒答 → Trace。
   - Day 7 的实测正好补上证据：提示词守住三行结构与引用，却没守住 `108/3600` 的算术。契约能挡住形状错误，挡不住「形状正确但数值错误」——后者要靠工具算，不靠 Schema。
   - 结构化会把 schema 与字段描述带进每轮输入 token，契约越细基线越高（接 Day 4）。
   - 落点：`validate_task_output()` 的三层顺序 + ADR-0005 的边界说明。

## 扫读：模块归属

| 产出 | 归属模块 | 一句话判断依据 |
|---|---|---|
| `python/task_contract.py` / `ts/task_contract.ts` | packages/contracts | 跨语言唯一形状源，不属于任何单个 app |
| `fixtures/cases.json` | packages/contracts | 契约的验收夹具，跟契约同版本管理 |
| `check_consistency.py` | packages/contracts | 双语言一致性门禁，改契约必须先过它 |
| `docs/adr/0005-task-contract.md` | docs/adr | 选型决策与风险，不写进代码注释 |
| 重试 / 降级 / Trace | 循环层（后续） | 契约只回答「合不合法」，重试属 Day 5 的 Loop |

## 四组用例（两侧实测一致）

| 用例 | 输入 | Python | TS | 预期 |
|---|---|---|---|---|
| 合法 | 完整 answer + 1 条引用 + `high` | PASS | PASS | 通过 |
| 缺字段 | 无 `answer` | `MISSING_FIELD` | `MISSING_FIELD` | 拒绝 |
| 枚举越界 | `confidence=very_high` | `ENUM_OUT_OF_RANGE` | `ENUM_OUT_OF_RANGE` | 拒绝 |
| 格式错乱 | 纯文本，不是 JSON | `PARSE_ERROR` | `PARSE_ERROR` | 拒绝 |

补充单测（Python 侧）：引用数超 `max_results`、`doc_id` 不在工具结果、多余字段、缺字段优先于枚举越界。

## 产出

- `packages/contracts/python/task_contract.py`：`TaskInput` / `TaskOutput` / `Citation` / `FailureCode`，`validate_task_output(raw, max_results, allowed_doc_ids)`。
- `packages/contracts/ts/task_contract.ts`：Zod 等价 Schema 与 `validateTaskOutput()`，错误码映射与 Python 对齐。
- `packages/contracts/fixtures/cases.json`：四组用例，两侧共用。
- `packages/contracts/check_consistency.py`：逐例比较两侧判定与预期，漂移退出码 1。
- `packages/contracts/python/test_task_contract.py`：6 个测试。
- `packages/contracts/{README.md,package.json,pyproject.toml}`、根 `pnpm-lock.yaml`。
- `docs/adr/0005-task-contract.md`：Pydantic + Zod 选型、扩展失败码、风险与未覆盖项。

## 验证

| 检查 | 命令 | 结果 |
|---|---|---|
| Python 测试 | `py311 -m pytest -q` | `6 passed` |
| TS 用例 | `node ts/run_cases.ts` | 四例 `PASS / MISSING_FIELD / ENUM_OUT_OF_RANGE / PARSE_ERROR` |
| 一致性门禁 | `py311 check_consistency.py` | 四例 `ok`，输出 `contracts agree`，退出码 0 |
| 门禁会红 | 临时把 expected 改错再跑 | 该例 `MISMATCH`，退出码 1；临时文件未入库 |
| 依赖版本 | `pnpm-lock.yaml` / `pydantic.__version__` | zod 3.23.8；pydantic 2.13.4 |
| 布局未漂移 | `bash infra/scripts/check_layout.sh` | `layout ok` |

## 与课程文档的偏差（主动讲出来）

1. 课程路径写 `contracts/task_contract.py`；仓库是五层布局，契约落在 `packages/contracts/`，Python 与 TS 分目录。
2. 课程模板的 `enforce_constraints()` 把引用上限写死 50，和 `TaskInput.max_results` 脱节；本实现把 `max_results` 作为参数传入，另加 `allowed_doc_ids` 校验来源真实性。
3. 课程只列四类失败码；本实现补 `UNKNOWN_FIELD` / `TYPE_ERROR` / `CONSTRAINT_VIOLATION`，并定义多错并发时的取码优先级，否则多余字段和类型错误没有稳定码可断言。
4. 课程要求 Python 与 TS 各实现一份；本机没有安装 pydantic 的独立 venv，直接用 conda `py311`（已有 2.13.4 + pytest 9.2.0），没有为今天再建一套环境。
5. PyPI 清华镜像在本机 DNS 不可达（`nodename nor servname`）；本次未需安装。后续若要新建环境，改用 `pypi.org` 或阿里云镜像。
6. OpenAI Structured Outputs 文档返回 403，未能读到原文；第三条笔记依据课程摘要与 Pydantic 文档，不冒充原文结论。
7. 课程要求的重试、降级、Trace 未实现：本模块只产失败码与 `raw`，重试属循环层，避免把「校验」和「恢复」混在一个函数里。
8. Node 不在非登录 shell 的 PATH 里（fnm）；所有命令在 README 里写成 `zsh -lic` 形式，避免「本机能跑、换 shell 就报 node not found」。

## 三行收尾

- 卡点：双份 Schema 的错误码语义不同——Pydantic 用 `missing` / `literal_error` / `extra_forbidden`，Zod 用 `invalid_type` + `received: "undefined"` / `invalid_enum_value` / `unrecognized_keys`，需要一层映射才能比对。
- 绕过：把「判定」统一成 `PASS` 或七个稳定失败码，先映射再比较；fixture 只断言判定，不断言底层错误文本。
- 下次：给 `check_consistency.py` 加一个「Schema 指纹」步骤（两侧 `model_json_schema()` 与 Zod 转 JSON Schema 后比对字段集合），覆盖 fixture 之外的漂移。

## 已知限制

- fixture 只有 4 条，覆盖四类主路径，不覆盖嵌套错误、多错并发组合、超长字段。
- 一致性检查能发现「同一用例判定不同」，不能证明两份 Schema 在所有输入上等价。
- 尚未接真实模型调用；`apps/api` 仍是占位，`RETRY_EXHAUSTED` 没有真实重试链可测。
- TS 侧依赖 Node 24 的类型擦除直接运行，没有 `tsc` 类型检查；类型层错误不会被 CI 拦住。
- 契约版本化与历史数据迁移只在 ADR 里给策略，未实现新旧版本并存读取。
- 失败码优先级是约定，不是标准；新增错误类型必须手工同步两侧。

## 验收

- [x] 结构化输出 / 任务契约 / 数据契约三者分得清
- [x] TaskContract 四件套齐全（入参 / 出参 / 约束 / 失败码）
- [x] Python 与 TS 两份 Schema 字段、枚举一致
- [x] 四组用例在两侧都跑通并有记录
- [x] 校验失败链路含重试、降级、拒答、Trace 的边界说明（本模块只产码，恢复留给循环层）
- [x] ADR 记录了 Pydantic 选型理由、风险与代价
- [x] 产物已入 `packages/contracts/`，命名可检索
- [x] 3 行 notes（卡点 / 绕过 / 下次）已写
- [ ] 口述自测（由本人完成）