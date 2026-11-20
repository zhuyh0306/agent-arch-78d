"""Backward-compatible entrypoint.

Day 2 shipped this file as a placeholder printer. It now launches the real
server so ``python main.py`` does what a reader expects; ``run.sh`` and
``uvicorn dataagent.api.app:build_app --factory`` are the documented paths.
"""

from __future__ import annotations

import uvicorn


def main() -> None:
    uvicorn.run("dataagent.api.app:build_app", factory=True, host="127.0.0.1", port=8000)


if __name__ == "__main__":
    main()