# prompts · DataAgent 提示词

**放什么**：DataAgent 的 system prompt 版本、对照用例与测试脚本。提示词是生产资产，改一版留一版，和 ADR、契约同一套管理方式。
**不放什么**：检索实现、工具代码、应用启动逻辑。

## 文件

| 文件 | 作用 |
|---|---|
| `system_v0.md` | 无约束初版，只作为对照基线，不用于生产 |
| `system_v1.md` | 五要素齐全的当前版本：角色 / 边界 / 输出格式 / 拒答 / 引用 |
| `cases.json` | 3 组对照用例：越权、信息不足、正常提问 |
| `contrast_test.py` | 同一上下文分别跑 v0 与 v1，把原始输出写进 `contrast-record.md` |
| `contrast-record.md` | 机器生成的对照记录，含双方原文与信号位；重跑会被覆盖 |
| `contrast-conclusion.md` | 人工核对的结论、逐组判定与未达标项；不随脚本重跑覆盖 |

## 运行

```bash
# 实验台已起（infra/README.md），在仓库根执行
/Users/zhuyonghui/.venvs/agent-arch-cost/bin/python skills/prompts/contrast_test.py
```

脚本从 `infra/.env` 读 `LITELLM_MASTER_KEY`，不打印密钥；模型默认 `fast`，可用 `CONTRAST_MODEL` 覆盖。
