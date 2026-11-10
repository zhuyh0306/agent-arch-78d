# apps/api · DataAgent HTTP 入口

FastAPI 应用，负责接收请求、装配上下文、调用技能、返回答案与 trace 引用。

## 命令

```bash
uv sync                 # 按 uv.lock 建/同步 .venv
uv add fastapi uvicorn  # 生产依赖
uv add --dev pytest ruff
uv run python main.py   # Day 2 只是个占位入口，Day 15 才真正起服务
```

Python 版本锁在 `.python-version`（3.11）。
