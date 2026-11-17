#!/usr/bin/env python3
"""Run the Day-7 prompt contrast: same cases, same context, two system prompts.

Writes contrast-record.md next to this script. The record is evidence, so it
stores raw outputs rather than only pass/fail booleans.
"""
import json
import os
import re
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
ENV = REPO / "infra" / ".env"
URL = os.environ.get("CONTRAST_URL", "http://127.0.0.1:4000/v1/chat/completions")
MODEL = os.environ.get("CONTRAST_MODEL", "fast")
MAX_TOKENS = int(os.environ.get("CONTRAST_MAX_TOKENS", "320"))

REFUSAL = ("无法", "不能", "无权", "拒绝", "没有权限", "未授权", "升级", "人工")
INSUFFICIENT = ("信息不足", "无法确定", "缺少", "不知道", "没有.*记录", "转人工")


def env_value(name):
    value = ""
    for line in ENV.read_text(encoding="utf-8").splitlines():
        if line.startswith(name + "="):
            value = line.split("=", 1)[1].strip()
    if not value:
        raise SystemExit(f"{name} missing from {ENV}")
    return value


def count_tokens(text):
    try:
        import tiktoken
    except ImportError:
        return None
    return len(tiktoken.get_encoding("o200k_base").encode(text))


def chat(system, user):
    body = json.dumps({
        "model": MODEL,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "temperature": 0,
        "max_tokens": MAX_TOKENS,
    }).encode("utf-8")
    request = urllib.request.Request(
        URL,
        data=body,
        headers={
            "Authorization": f"Bearer {env_value('LITELLM_MASTER_KEY')}",
            "Content-Type": "application/json",
        },
    )
    with urllib.request.urlopen(request, timeout=180) as response:
        payload = json.load(response)
    return payload["choices"][0]["message"]["content"].strip(), payload.get("usage", {})


def signals(text):
    return {
        "refusal": any(word in text for word in REFUSAL),
        "insufficient": any(re.search(word, text) for word in INSUFFICIENT),
        "citation": bool(re.search(r"\[doc-[0-9]+\]", text)),
        "number": bool(re.search(r"\d", text)),
    }


def main():
    system_v0 = (HERE / "system_v0.md").read_text(encoding="utf-8").strip()
    system_v1 = (HERE / "system_v1.md").read_text(encoding="utf-8").strip()
    cases = json.loads((HERE / "cases.json").read_text(encoding="utf-8"))["cases"]

    lines = [
        "# Day 7 prompt contrast record",
        "",
        f"- run_at: {datetime.now(timezone.utc).isoformat(timespec='seconds')}",
        f"- model: `{MODEL}`",
        f"- temperature: 0, max_tokens: {MAX_TOKENS}",
        f"- system_v0 tokens: {count_tokens(system_v0)}",
        f"- system_v1 tokens: {count_tokens(system_v1)}",
        "",
        "## Raw results",
        "",
    ]

    for case in cases:
        user = f"上下文：\n{case['context']}\n\n问题：{case['question']}"
        out0, usage0 = chat(system_v0, user)
        out1, usage1 = chat(system_v1, user)
        s0, s1 = signals(out0), signals(out1)
        lines += [
            f"### {case['id']} · {case['group']}",
            "",
            "**输入**",
            "",
            "```text",
            user,
            "```",
            "",
            "**无约束 v0**",
            "",
            "```text",
            out0,
            "```",
            "",
            f"signals: `{s0}`, usage: `{usage0}`",
            "",
            "**五要素 v1**",
            "",
            "```text",
            out1,
            "```",
            "",
            f"signals: `{s1}`, usage: `{usage1}`",
            "",
        ]

    (HERE / "contrast-record.md").write_text("\n".join(lines), encoding="utf-8")
    print(f"wrote {HERE / 'contrast-record.md'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
