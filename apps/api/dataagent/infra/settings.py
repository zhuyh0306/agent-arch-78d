"""Process settings, read from the environment with explicit defaults.

Every default here is a decision, not a shrug:

* ``metrics_dictionary`` points at the repo-relative contract file so a fresh
  checkout works without configuration; deployments override it.
* ``tool_timeout_seconds`` is bounded at startup -- a bad value fails the
  process rather than surfacing as a hung request later.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

# apps/api/dataagent/infra/settings.py -> repo root is four levels up.
_REPO_ROOT = Path(__file__).resolve().parents[4]


def _default_dictionary() -> Path:
    return _REPO_ROOT / "packages" / "contracts" / "metrics_dictionary.yaml"


@dataclass(frozen=True, slots=True)
class Settings:
    app_name: str = "dataagent-api"
    version: str = "0.1.0"
    metrics_dictionary: Path = field(default_factory=_default_dictionary)
    tool_timeout_seconds: float = 5.0
    llm_provider: str = "echo"

    def __post_init__(self) -> None:
        if self.tool_timeout_seconds <= 0:
            raise ValueError("tool_timeout_seconds must be positive")
        if self.llm_provider != "echo":
            # Be explicit now rather than failing at the first call.
            raise ValueError(f"unknown llm provider {self.llm_provider!r}; only 'echo' is wired on Day 15")

    @classmethod
    def from_env(cls, env: dict[str, str] | None = None) -> Settings:
        env = dict(os.environ if env is None else env)
        dictionary = env.get("DATAAGENT_METRICS_DICTIONARY")
        return cls(
            app_name=env.get("DATAAGENT_APP_NAME", "dataagent-api"),
            version=env.get("DATAAGENT_VERSION", "0.1.0"),
            metrics_dictionary=Path(dictionary) if dictionary else _default_dictionary(),
            tool_timeout_seconds=float(env.get("DATAAGENT_TOOL_TIMEOUT", "5.0")),
            llm_provider=env.get("DATAAGENT_LLM_PROVIDER", "echo"),
        )