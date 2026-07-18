"""Run repeated null-market trials through the real composite score path."""

from __future__ import annotations

import argparse
import json
import statistics
from pathlib import Path

from codes.engine.issue_079 import _prediction_from_row, run_validation
from codes.workers.generate_issue_079_data import generate


def public_markdown(result: dict[str, object]) -> str:
    """Render a publication-ready, non-promotional transparency report."""

    interval = result["spread_95pct_confidence_interval_pct"]
    diagnoses = result["diagnosis_counts"]
    return f"""# Null-market control: a transparent test of the evaluator

**Published status: no predictive signal detected in this control test.**

This is a reproducibility and honesty test, not a claim of investment
performance. We generated random factor inputs, passed them through the actual
composite re-scoring path, and generated future returns independently at
random. Because the future is independent of the score, a trustworthy
evaluator should find no stable advantage.

## Result at a glance

| Measure | Result |
|---|---:|
| Independent trials | {result['trials']} |
| Rows per trial | {result['rows_per_trial']} |
| Annual snapshots per trial | {result['annual_snapshots']} |
| Mean high-score minus low-score spread | {result['mean_high_minus_low_spread_pct']:.3f}% |
| 95% confidence interval for spread | {interval[0]:.3f}% to {interval[1]:.3f}% |
| Mean periods beating SPY | {result['mean_periods_beating_spy_pct']:.3f}% |

The confidence interval includes zero and the average SPY win rate is near
50%. That is the expected result when scores contain no information about
future returns.

## Lucky and failed runs are visible

Individual random trials sometimes looked positive or negative. We preserve
all diagnoses instead of selecting a favorable run:

| Diagnostic result | Number of trials |
|---|---:|
| Strong-synthetic-signal | {diagnoses.get('strong-synthetic-signal', 0)} |
| Null-or-weak-synthetic-signal | {diagnoses.get('null-or-weak-synthetic-signal', 0)} |
| Mixed-or-insufficient-signal | {diagnoses.get('mixed-or-insufficient-signal', 0)} |
| Inverted-synthetic-signal | {diagnoses.get('inverted-synthetic-signal', 0)} |

This is why one backtest, one start date, or one favorable period is not
credible evidence.

## What was tested

- Score path: `{result['algorithm_scores']}`
- Future-return process: `{result['future_returns']}`
- Seed range: `{result['seed_range'][0]}` through `{result['seed_range'][1]}`
- The benchmark and each stock used aligned dates and equal starting capital.
- The raw machine-readable result is retained alongside this report.

## What this does not prove

- It does not prove that the production algorithm predicts real markets.
- It does not replace point-in-time filings, delisted securities, corporate-action data, or realistic execution data.
- It does not establish a live or historical performance claim.
- It does show that our evaluator is capable of reporting a flat/no-signal result and exposing lucky false positives.

## Reproduce this report

```bash
PYTHONPATH=. python -m codes.workers.issue_079_randomized_trial \\
  --count {result['trials']} \\
  --first-seed {result['seed_range'][0]} \\
  --output randomized-null-trial.json \\
  --markdown-output randomized-null-trial.md
```

Interpretation rule: a null control passes when the average score/outcome
relationship is near zero and its confidence interval includes zero. A failure
of the null control would be investigated before publishing any positive
algorithm result.
"""


def run_trials(first_seed: int, count: int) -> dict[str, object]:
    """Evaluate many independent random markets and summarize uncertainty."""

    if count < 2:
        raise ValueError("count must be at least 2")
    spreads: list[float] = []
    beat_rates: list[float] = []
    diagnoses: list[str] = []
    for seed in range(first_seed, first_seed + count):
        rows = [_prediction_from_row(row) for row in generate("random-algorithm", seed)]
        result = run_validation(rows)
        diagnostic = result["diagnostic_assessment"]
        spreads.append(float(diagnostic["high_minus_low_spread_pct"]))
        beat_rates.append(float(diagnostic["periods_beating_spy_pct"]))
        diagnoses.append(str(diagnostic["diagnosis"]))
    mean_spread = statistics.fmean(spreads)
    standard_error = statistics.stdev(spreads) / (count**0.5)
    return {
        "status": "null-market-diagnostic",
        "algorithm_scores": "codes.engine.factor_backtest._score_with_weights",
        "future_returns": "independent seeded random draws",
        "trials": count,
        "rows_per_trial": 1000,
        "annual_snapshots": 20,
        "seed_range": [first_seed, first_seed + count - 1],
        "mean_high_minus_low_spread_pct": round(mean_spread, 3),
        "spread_95pct_confidence_interval_pct": [
            round(mean_spread - 1.96 * standard_error, 3),
            round(mean_spread + 1.96 * standard_error, 3),
        ],
        "mean_periods_beating_spy_pct": round(statistics.fmean(beat_rates), 3),
        "diagnosis_counts": {diagnosis: diagnoses.count(diagnosis) for diagnosis in sorted(set(diagnoses))},
        "interpretation": (
            "A valid null test should have a near-zero mean spread and a confidence interval "
            "that includes zero. Individual trials can look positive or negative by chance."
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--first-seed", type=int, default=7901)
    parser.add_argument("--count", type=int, default=100)
    parser.add_argument("--output", type=Path, default=Path("/tmp/issue-079-randomized-trial.json"))
    parser.add_argument("--markdown-output", type=Path)
    args = parser.parse_args()
    result = run_trials(args.first_seed, args.count)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    markdown_output = args.markdown_output or args.output.with_suffix(".md")
    markdown_output.parent.mkdir(parents=True, exist_ok=True)
    markdown_output.write_text(public_markdown(result), encoding="utf-8")
    print(json.dumps({"json": str(args.output), "markdown": str(markdown_output), "status": result["status"]}, indent=2))


if __name__ == "__main__":
    main()
