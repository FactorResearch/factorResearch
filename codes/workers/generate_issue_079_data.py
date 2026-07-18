"""Generate deterministic ISSUE_079 data with known signal quality."""

from __future__ import annotations

import argparse
import csv
import random
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

from codes.engine.factor_backtest import _score_with_weights
from codes.engine.scorer import ENHANCED_WEIGHTS

SCENARIOS = ("strong", "null", "inverted", "risk-screen", "random-algorithm")
SYMBOLS = ("ALFA", "BETA", "GAMMA", "DELTA", "EPSI", "ZETA", "ETA", "THETA")


def _return_for(scenario: str, score: int, rng: random.Random) -> Decimal:
    noise_limit = 0.005 if scenario == "strong" else 0.025
    noise = Decimal(str(round(rng.uniform(-noise_limit, noise_limit), 4)))
    if scenario == "strong":
        return Decimal("0.02") + Decimal(score) / Decimal("100") * Decimal("0.18") + noise
    if scenario == "inverted":
        return Decimal("0.18") - Decimal(score) / Decimal("100") * Decimal("0.18") + noise
    if scenario == "risk-screen":
        return Decimal("0.06") if score >= 70 else Decimal("-0.14") + noise
    return Decimal("0.08") + noise


def generate(scenario: str, seed: int = 7901) -> list[dict[str, str]]:
    """Create 20 annual snapshots without future-data leakage.

    Scores are treated as historical algorithm outputs. Forward prices are
    generated separately so the runner evaluates, rather than creates, the
    relationship between scores and later outcomes.
    """

    if scenario not in SCENARIOS:
        raise ValueError(f"scenario must be one of {SCENARIOS}")
    rng = random.Random(seed)
    rows: list[dict[str, str]] = []
    for year in range(20):
        analysis = date(2005 + year, 1, 3)
        spy_return = Decimal("0.08") + Decimal(str(round(rng.uniform(-0.02, 0.02), 4)))
        symbols = SYMBOLS if scenario != "random-algorithm" else tuple(
            f"R{year:02d}{index:02d}" for index in range(50)
        )
        for index, symbol in enumerate(symbols):
            if scenario == "random-algorithm":
                analysis_result = {
                    "graham": {"total_score": rng.randint(0, 100), "total_max": 100},
                    "quality": {"total_score": rng.randint(0, 100), "total_max": 100},
                    "momentum": {"total_score": rng.randint(0, 100), "total_max": 100},
                    "risk": {"risk_score": rng.randint(0, 100), "risk_score_max": 100},
                    "altman": {"risk_score": rng.randint(0, 100)},
                    "earnings_revision": {"total_score": rng.randint(0, 100), "total_max": 100},
                    "profitability": {"profitability_score": rng.randint(0, 100)},
                    "fcf_quality": {"fcf_quality_score": rng.randint(0, 100)},
                    "capital_allocation": {"capital_allocation_score": rng.randint(0, 100)},
                    "growth_quality": {"growth_quality_score": rng.randint(0, 100)},
                }
                score = round(_score_with_weights(analysis_result, ENHANCED_WEIGHTS))
                forward_return = Decimal(str(round(max(-0.9, rng.gauss(0.08, 0.25)), 4)))
            else:
                score = 95 - index * 10
                forward_return = _return_for(scenario, score, rng)
            start_price = Decimal("80") + Decimal(index * 7 + year)
            rows.append({
                "symbol": symbol,
                "analysis_date": analysis.isoformat(),
                "available_at": (analysis - timedelta(days=3)).isoformat(),
                "execution_date": analysis.isoformat(),
                "score": str(score),
                "signal": "Attractive" if score >= 70 else "Neutral" if score >= 40 else "Avoid",
                "start_price": str(start_price),
                "end_price_1y": str((start_price * (Decimal("1") + forward_return)).quantize(Decimal("0.0001"))),
                "spy_start_price": "100",
                "spy_end_price_1y": str((Decimal("100") * (Decimal("1") + spy_return)).quantize(Decimal("0.0001"))),
                "sector": "technology" if index % 2 == 0 else "industrials",
                "market_cap_band": "large" if index < 3 else "mid",
                "regime": "synthetic",
                "survivor_status": "delisted" if symbol == "THETA" else "survivor",
                "model_quality": str(Decimal(score) / Decimal("10")),
                "model_value": str(Decimal(index + 1)),
            })
    return rows


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scenario", choices=SCENARIOS, required=True)
    parser.add_argument("--seed", type=int, default=7901)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    rows = generate(args.scenario, args.seed)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    print(f"generated {len(rows)} rows: scenario={args.scenario} seed={args.seed} output={args.output}")


if __name__ == "__main__":
    main()
