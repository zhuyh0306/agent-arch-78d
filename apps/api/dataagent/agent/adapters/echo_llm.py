"""A deterministic stand-in model for the skeleton.

Why not a real model: Day 15's acceptance item is "api starts, healthz answers".
Wiring a paid provider now would make the first smoke test depend on a key and
a network, and would hide the fact that the *port* is what we are validating.

Why not a bare ``NotImplementedError``: an empty implementation cannot prove
the wiring. The echo adapter lets the composition root and the route exercise
a real call path end to end, so the seam is demonstrated rather than asserted.
It is obviously fake on purpose -- it does not pretend to reason.
"""

from __future__ import annotations

from dataagent.agent.ports.llm import LLMRequest, LLMResponse


class EchoLLM:
    """Satisfies LLMPort by deterministically echoing the request shape."""

    model = "echo-0"

    def __init__(self) -> None:
        self.calls: list[LLMRequest] = []

    def complete(self, request: LLMRequest) -> LLMResponse:
        self.calls.append(request)
        text = f"[echo] {request.user.strip()[:120]}"
        return LLMResponse(
            text=text,
            model=self.model,
            # Rough, but real enough that budget code has something to read.
            input_tokens=len(request.system.split()) + len(request.user.split()),
            output_tokens=len(text.split()),
        )