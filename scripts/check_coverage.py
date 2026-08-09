"""Enforce the separately stated core line and branch coverage thresholds."""

from __future__ import annotations

import json
from pathlib import Path


def percentage(covered: int, total: int) -> float:
    return 100.0 if total == 0 else covered / total * 100


def main() -> None:
    payload = json.loads(Path("coverage.json").read_text(encoding="utf-8"))
    totals = payload["totals"]
    line = percentage(totals["covered_lines"], totals["num_statements"])
    branch = percentage(totals["covered_branches"], totals["num_branches"])
    print(f"Python coverage: lines={line:.2f}% branches={branch:.2f}%")
    failures = []
    if line < 85:
        failures.append(f"line coverage {line:.2f}% is below 85%")
    if branch < 75:
        failures.append(f"branch coverage {branch:.2f}% is below 75%")
    if failures:
        raise SystemExit("; ".join(failures))


if __name__ == "__main__":
    main()
