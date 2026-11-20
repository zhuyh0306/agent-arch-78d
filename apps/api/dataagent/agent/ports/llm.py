"""The model port: what the agent needs to say something.

Deliberately narrow. There is no ``chat_completion(messages)`` because a raw
message list is the vendor's vocabulary, not the agent's -- it lets provider
quirks leak into every call site. The agent asks for a completion given a
system instruction and a user question; routing, retries, token accounting and
provider selection belong to the adapter (and later the gateway, Day 16).
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable


@dataclass(frozen=True, slots=True)
class LLMRequest:
    system: str
    user: str
    # Free-form knobs the caller must not have to understand per provider.
    # The adapter is responsible for translating or ignoring them.
    temperature: float = 0.0
    max_tokens: int = 1024
    metadata: Mapping[str, str] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class LLMResponse:
    text: str
    model: str
    # Kept so the gateway can enforce a budget later without re-running the call.
    input_tokens: int = 0
    output_tokens: int = 0


@runtime_checkable
class LLMPort(Protocol):
    """What every LLM adapter must provide, no more and no less."""

    def complete(self, request: LLMRequest) -> LLMResponse:
        """Return one completion. Raise rather than return a sentinel on failure."""
        ...