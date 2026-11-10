"""Day 3: weight the selection matrix by column name so a weight change can be rerun."""

import csv
import sys
from pathlib import Path

W = {"cost": 0.20, "ops": 0.25, "eco": 0.20, "exit": 0.25, "fam": 0.10}
ROOT = Path(__file__).resolve().parents[2]


def score(row: dict) -> float:
    return sum(w * float(row[k]) for k, w in W.items())


def main(path: str | None = None) -> None:
    csv_path = Path(path) if path else ROOT / "docs" / "selection-matrix.csv"
    with csv_path.open(newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    for r in sorted(rows, key=score, reverse=True):
        print(f"{r['name']:14} {score(r):.2f}")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else None)
