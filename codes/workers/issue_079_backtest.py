"""Run ISSUE_079 offline validation without a market-data subscription."""

from __future__ import annotations

import argparse
import json
from dataclasses import replace
from decimal import Decimal
from pathlib import Path

from codes.engine.issue_079 import ValidationConfig, demo_rows, load_csv, run_validation


def _config(path: Path | None) -> ValidationConfig:
    if path is None:
        return ValidationConfig()
    values = json.loads(path.read_text(encoding="utf-8"))
    if "initial_capital" in values:
        values["initial_capital"] = Decimal(str(values["initial_capital"]))
    if "transaction_cost_bps" in values:
        values["transaction_cost_bps"] = Decimal(str(values["transaction_cost_bps"]))
    return replace(ValidationConfig(), **values)


def _markdown(result: dict) -> str:
    run = result["run"]
    lines = [
        "# ISSUE_079 Offline Validation Report",
        "",
        f"- Status: **{result['result_classification']}**",
        f"- Algorithm: `{run['algorithm_version']}`",
        f"- Data: `{run['data_version']}`",
        f"- Seed: `{run['random_seed']}`",
        f"- Configuration hash: `{run['configuration_hash']}`",
        "",
        "This report is a reproducibility harness result, not a production performance claim.",
        "",
        "## Synthetic signal diagnostic",
        "",
        f"- Diagnosis: **{result['diagnostic_assessment']['diagnosis']}**",
        f"- High-score minus low-score return spread: {result['diagnostic_assessment']['high_minus_low_spread_pct']:.2f}%",
        f"- Periods beating SPY: {result['diagnostic_assessment']['periods_beating_spy_pct']:.2f}%",
        "",
        "## $10,000 periods",
        "",
        "| Analysis date | Factor Research | SPY | Difference | Holdings |",
        "|---|---:|---:|---:|---|",
    ]
    for period in result["portfolio_periods"]:
        lines.append(
            f"| {period['analysis_date']} | ${period['factor_value']} | ${period['spy_value']} | ${period['difference']} | {', '.join(period['holdings'])} |"
        )
    lines.extend(["", "## Limitations", ""])
    lines.extend(f"- {limitation}" for limitation in result["limitations"])
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, help="Validated ISSUE_079 CSV input")
    parser.add_argument("--config", type=Path, help="JSON validation configuration")
    parser.add_argument("--output-dir", type=Path, default=Path("artifacts/issue-079"))
    parser.add_argument("--demo", action="store_true", help="Use deterministic offline demo rows")
    args = parser.parse_args()
    if args.input and args.demo:
        parser.error("choose --input or --demo, not both")
    if not args.input and not args.demo:
        args.demo = True
    config = _config(args.config)
    rows = load_csv(args.input) if args.input else demo_rows()
    result = run_validation(rows, config)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / "issue-079-result.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    (args.output_dir / "issue-079-report.md").write_text(_markdown(result), encoding="utf-8")
    print(json.dumps({"status": result["status"], "rows": result["run"]["sample_size"], "output_dir": str(args.output_dir)}, indent=2))


if __name__ == "__main__":
    main()
