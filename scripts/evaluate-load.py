"""Evaluate Locust aggregate CSV against an explicit performance contract."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path


def evaluate(stats_path: Path, *, max_p95_ms: float, max_failure_rate: float) -> dict:
    with stats_path.open(newline="") as source:
        aggregate = next(row for row in csv.DictReader(source) if row["Name"] == "Aggregated")
    requests = int(aggregate["Request Count"])
    failures = int(aggregate["Failure Count"])
    p95 = float(aggregate["95%"])
    failure_rate = failures / requests if requests else 1.0
    checks = {
        "requests_recorded": requests > 0,
        "p95_ms": p95 <= max_p95_ms,
        "failure_rate": failure_rate <= max_failure_rate,
    }
    return {
        "passed": all(checks.values()),
        "checks": checks,
        "observed": {"requests": requests, "failures": failures, "failure_rate": round(failure_rate, 6), "p95_ms": p95},
        "thresholds": {"max_p95_ms": max_p95_ms, "max_failure_rate": max_failure_rate},
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("stats", type=Path, help="Locust *_stats.csv file")
    parser.add_argument("--max-p95-ms", type=float, required=True)
    parser.add_argument("--max-failure-rate", type=float, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = evaluate(args.stats, max_p95_ms=args.max_p95_ms, max_failure_rate=args.max_failure_rate)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))
    raise SystemExit(0 if result["passed"] else 1)


if __name__ == "__main__":
    main()
