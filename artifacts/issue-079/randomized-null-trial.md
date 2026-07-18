# Null-market control: a transparent test of the evaluator

**Published status: no predictive signal detected in this control test.**

This is a reproducibility and honesty test, not a claim of investment
performance. We generated random factor inputs, passed them through the actual
composite re-scoring path, and generated future returns independently at
random. Because the future is independent of the score, a trustworthy
evaluator should find no stable advantage.

## Result at a glance

| Measure | Result |
|---|---:|
| Independent trials | 100 |
| Rows per trial | 1000 |
| Annual snapshots per trial | 20 |
| Mean high-score minus low-score spread | -0.085% |
| 95% confidence interval for spread | -1.234% to 1.064% |
| Mean periods beating SPY | 48.769% |

The confidence interval includes zero and the average SPY win rate is near
50%. That is the expected result when scores contain no information about
future returns.

## Lucky and failed runs are visible

Individual random trials sometimes looked positive or negative. We preserve
all diagnoses instead of selecting a favorable run:

| Diagnostic result | Number of trials |
|---|---:|
| Strong-synthetic-signal | 1 |
| Null-or-weak-synthetic-signal | 39 |
| Mixed-or-insufficient-signal | 55 |
| Inverted-synthetic-signal | 5 |

This is why one backtest, one start date, or one favorable period is not
credible evidence.

## What was tested

- Score path: `codes.engine.factor_backtest._score_with_weights`
- Future-return process: `independent seeded random draws`
- Seed range: `7901` through `8000`
- The benchmark and each stock used aligned dates and equal starting capital.
- The raw machine-readable result is retained alongside this report.

## What this does not prove

- It does not prove that the production algorithm predicts real markets.
- It does not replace point-in-time filings, delisted securities, corporate-action data, or realistic execution data.
- It does not establish a live or historical performance claim.
- It does show that our evaluator is capable of reporting a flat/no-signal result and exposing lucky false positives.

## Reproduce this report

```bash
PYTHONPATH=. python -m codes.workers.issue_079_randomized_trial \
  --count 100 \
  --first-seed 7901 \
  --output randomized-null-trial.json \
  --markdown-output randomized-null-trial.md
```

Interpretation rule: a null control passes when the average score/outcome
relationship is near zero and its confidence interval includes zero. A failure
of the null control would be investigated before publishing any positive
algorithm result.
