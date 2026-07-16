#!/usr/bin/env python3
"""Fail release validation when controlled first-party UX budgets regress."""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BUDGET_PATH = ROOT / "config/ux_performance_budgets.json"
REPORT_PATH = Path("/tmp/ux-performance-budget-report.json")


def main() -> int:
    budgets = json.loads(BUDGET_PATH.read_text())
    asset_budgets = budgets["first_party_assets"]
    javascript = sorted((ROOT / "assets").glob("*.js"))
    js_sizes = {path.name: path.stat().st_size for path in javascript}
    style_size = (ROOT / "assets/style.css").stat().st_size
    measurements = {
        "style.css": style_size,
        "total_javascript_bytes": sum(js_sizes.values()),
        "largest_javascript_bytes": max(js_sizes.values(), default=0),
        "javascript_files": js_sizes,
    }
    checks = {
        key: {
            "measured": measurements[key],
            "budget": limit,
            "passing": measurements[key] <= limit,
        }
        for key, limit in asset_budgets.items()
    }
    report = {
        "budgets": budgets,
        "measurements": measurements,
        "checks": checks,
        "passing": all(check["passing"] for check in checks.values()),
    }
    REPORT_PATH.write_text(json.dumps(report, indent=2) + "\n")
    for name, check in checks.items():
        status = "PASS" if check["passing"] else "FAIL"
        print(f"{status} {name}: {check['measured']} <= {check['budget']} bytes")
    return 0 if report["passing"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
