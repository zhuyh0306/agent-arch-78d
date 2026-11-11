"""Day 4: count one DataAgent turn's tokens and price it at single/1k/monthly."""
import csv
import json
import sys
from pathlib import Path

import tiktoken

HERE = Path(__file__).resolve().parent
TIERS = (("single", 1), ("1000", 1_000), ("month", None))


def load_scenario(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def load_prices(path):
    with open(path, newline="", encoding="utf-8") as f:
        return [
            {
                "model": row["model"],
                "tariff": row["tariff"],
                "hit_usd": float(row["hit_usd"]),
                "miss_usd": float(row["miss_usd"]),
                "out_usd": float(row["out_usd"]),
            }
            for row in csv.DictReader(f)
        ]


def count_parts(enc, scenario):
    tools_json = json.dumps(scenario["tools"], ensure_ascii=False)
    history = "\n".join(f"{turn['role']}: {turn['content']}" for turn in scenario.get("history", []))
    return {
        "system": len(enc.encode(scenario["system"])),
        "tools": len(enc.encode(tools_json)),
        "history": len(enc.encode(history)),
        "context": len(enc.encode("\n\n".join(scenario["context"]))),
        "question": len(enc.encode(scenario["question"])),
        "output": len(enc.encode(scenario["output"])),
    }


def input_cost(tokens, price, cached):
    prefix = tokens["system"] + tokens["tools"]
    hit = prefix if cached else 0
    miss = sum(tokens[k] for k in ("system", "tools", "history", "context", "question")) - hit
    return (hit * price["hit_usd"] + miss * price["miss_usd"]) / 1_000_000


def session_cost(tokens, price, cached):
    return input_cost(tokens, price, cached) + tokens["output"] * price["out_usd"] / 1_000_000


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    scenario_path = Path(argv[0]) if argv else HERE / "scenario.json"
    scenario = load_scenario(scenario_path)
    enc = tiktoken.get_encoding(scenario.get("encoding", "o200k_base"))
    tokens = count_parts(enc, scenario)
    volume = scenario.get("month_volume", 30_000)
    prices = load_prices(HERE / "prices.csv")

    input_keys = ("system", "tools", "history", "context", "question")
    tokens_in = sum(tokens[k] for k in input_keys)
    prefix = tokens["system"] + tokens["tools"]
    print(f"encoding {scenario.get('encoding', 'o200k_base')}")
    print(
        "tokens  "
        + "  ".join(f"{k}={v}" for k, v in tokens.items())
        + f"  | in={tokens_in} out={tokens['output']}"
    )
    print(f"prefix cacheable {prefix}/{tokens_in} = {prefix / tokens_in:.0%} (system + tool schemas)")

    rates = {}
    for kind, text in (("zh", scenario["system"]), ("en", scenario["system_en"])):
        n = len(enc.encode(text))
        rates[kind] = len(text) / n
        print(f"system[{kind}] {len(text)} chars -> {n} tokens ({rates[kind]:.2f} chars/token)")
    print(f"same meaning, zh needs {rates['en'] / rates['zh']:.1f}x the tokens of en")

    rows = []
    print()
    print(f"{'model':16}{'tariff':9}{'cache':7}{'in%':>5}{'single':>10}{'1k':>9}{'month':>9}  usd")
    for price in prices:
        for cached in (True, False):
            single = session_cost(tokens, price, cached)
            share = input_cost(tokens, price, cached) / single
            for tier, factor in TIERS:
                usd = single * (volume if factor is None else factor)
                rows.append(
                    {
                        "model": price["model"],
                        "tariff": price["tariff"],
                        "cache": "hit" if cached else "miss",
                        "tier": tier,
                        "usd": round(usd, 4),
                        "input_share": round(share, 4),
                    }
                )
            print(
                f"{price['model']:16}{price['tariff']:9}{'hit' if cached else 'miss':7}"
                f"{share:4.0%}{single:10.4f}{single * 1000:9.2f}{single * volume:9.2f}"
            )

    out = HERE / "cost-model.csv"
    with open(out, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f, fieldnames=["model", "tariff", "cache", "tier", "usd", "input_share"]
        )
        writer.writeheader()
        writer.writerows(rows)
    print(f"\nwrote {out.relative_to(HERE.parents[1])} ({len(rows)} rows)")

    print()
    for price in (p for p in prices if p["tariff"] == "offpeak"):
        cross = tokens["output"] * price["out_usd"] / price["miss_usd"]
        print(
            f"crossover {price['model']}: input > {cross:.0f} tokens at miss price "
            "-> input starts to dominate output"
        )

    worst = next(p for p in prices if p["model"] == "deepseek-v4-pro" and p["tariff"] == "offpeak")
    best = next(p for p in prices if p["model"] == "deepseek-flash" and p["tariff"] == "offpeak")
    room = session_cost(tokens, worst, True) - session_cost(tokens, best, True)
    print(f"model switch v4-pro -> flash saves {room / session_cost(tokens, worst, True):.0%} per turn, off-peak")


if __name__ == "__main__":
    main()
