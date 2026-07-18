"""Offline-first validation primitives for ISSUE_079.

This module deliberately accepts a narrow, explicit row contract instead of
calling a market-data provider.  That makes the research procedure runnable
without FMP while keeping the boundary ready for a licensed point-in-time
dataset later.  Results from the bundled demo data are demonstrations only and
are always marked inconclusive.
"""

from __future__ import annotations

import csv
import hashlib
import json
import random
from collections.abc import Iterable
from dataclasses import asdict, dataclass
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from pathlib import Path

SCORE_BUCKETS: tuple[tuple[int, int], ...] = tuple(
    (upper, upper - 9) for upper in range(100, -1, -10)
)
REQUIRED_COLUMNS = {
    "symbol",
    "analysis_date",
    "available_at",
    "execution_date",
    "score",
    "signal",
    "start_price",
    "end_price_1y",
    "spy_start_price",
    "spy_end_price_1y",
}


class Issue079InputError(ValueError):
    """Raised when an input row violates the point-in-time contract."""


@dataclass(frozen=True, slots=True)
class ValidationConfig:
    """Versioned rules for one deterministic validation run.

    ``transaction_cost_bps`` is charged twice per one-year period as a simple
    entry/exit assumption.  This is a transparent demonstration assumption,
    not a claim that it models every real-world cost.
    """

    algorithm_version: str = "issue-079-demo-v1"
    data_version: str = "demo-v1"
    benchmark: str = "SPY"
    score_threshold: float = 70.0
    max_holdings: int = 3
    random_seed: int = 7901
    random_sample_size: int | None = None
    initial_capital: Decimal = Decimal("10000")
    transaction_cost_bps: Decimal = Decimal("10")


@dataclass(frozen=True, slots=True)
class Prediction:
    """One historical prediction and its isolated one-year forward outcome."""

    symbol: str
    analysis_date: date
    available_at: date
    execution_date: date
    score: Decimal
    signal: str
    start_price: Decimal
    end_price_1y: Decimal
    spy_start_price: Decimal
    spy_end_price_1y: Decimal
    sector: str = "unknown"
    market_cap_band: str = "unknown"
    regime: str = "unknown"
    survivor_status: str = "survivor"
    model_contributions: tuple[tuple[str, Decimal], ...] = ()

    @property
    def forward_return(self) -> Decimal:
        return self.end_price_1y / self.start_price - Decimal("1")

    @property
    def benchmark_return(self) -> Decimal:
        return self.spy_end_price_1y / self.spy_start_price - Decimal("1")

    @property
    def excess_return(self) -> Decimal:
        return self.forward_return - self.benchmark_return


def _decimal(value: str | Decimal, field: str, *, allow_zero: bool = False) -> Decimal:
    try:
        parsed = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise Issue079InputError(f"{field} must be numeric: {value!r}") from exc
    if not parsed.is_finite() or (parsed < 0 if allow_zero else parsed <= 0):
        qualifier = "non-negative" if allow_zero else "positive"
        raise Issue079InputError(f"{field} must be finite and {qualifier}: {value!r}")
    return parsed


def _date(value: str, field: str) -> date:
    try:
        return date.fromisoformat(value[:10])
    except (TypeError, ValueError) as exc:
        raise Issue079InputError(f"{field} must be an ISO date: {value!r}") from exc


def _validate_prediction(prediction: Prediction) -> None:
    if prediction.available_at > prediction.analysis_date:
        raise Issue079InputError(
            f"{prediction.symbol} uses data available after its analysis date "
            f"({prediction.available_at} > {prediction.analysis_date})"
        )
    if prediction.execution_date < prediction.analysis_date:
        raise Issue079InputError(f"{prediction.symbol} execution precedes analysis date")
    if prediction.end_price_1y <= 0 or prediction.spy_end_price_1y <= 0:
        raise Issue079InputError("forward prices must be positive")
    if not Decimal("0") <= prediction.score <= Decimal("100"):
        raise Issue079InputError(f"score must be between 0 and 100: {prediction.score}")


def load_csv(path: Path) -> list[Prediction]:
    """Load and validate the documented point-in-time CSV contract.

    The forward outcome columns are intentionally separate from the
    information-available columns.  A production adapter must produce these
    outcomes from a later, isolated evaluation dataset rather than joining
    future values into the signal-generation query.
    """

    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        columns = set(reader.fieldnames or ())
        missing = REQUIRED_COLUMNS - columns
        if missing:
            raise Issue079InputError(f"{path} is missing columns: {sorted(missing)}")
        predictions = [_prediction_from_row(row) for row in reader]
    if not predictions:
        raise Issue079InputError(f"{path} contains no predictions")
    return predictions


def _prediction_from_row(row: dict[str, str]) -> Prediction:
    contributions = tuple(
        sorted(
            (key.removeprefix("model_"), _decimal(value, key))
            for key, value in row.items()
            if key.startswith("model_") and value not in (None, "")
        )
    )
    prediction = Prediction(
        symbol=row["symbol"].strip().upper(),
        analysis_date=_date(row["analysis_date"], "analysis_date"),
        available_at=_date(row["available_at"], "available_at"),
        execution_date=_date(row["execution_date"], "execution_date"),
        score=_decimal(row["score"], "score", allow_zero=True),
        signal=row["signal"].strip().title(),
        start_price=_decimal(row["start_price"], "start_price"),
        end_price_1y=_decimal(row["end_price_1y"], "end_price_1y"),
        spy_start_price=_decimal(row["spy_start_price"], "spy_start_price"),
        spy_end_price_1y=_decimal(row["spy_end_price_1y"], "spy_end_price_1y"),
        sector=row.get("sector", "unknown") or "unknown",
        market_cap_band=row.get("market_cap_band", "unknown") or "unknown",
        regime=row.get("regime", "unknown") or "unknown",
        survivor_status=row.get("survivor_status", "survivor") or "survivor",
        model_contributions=contributions,
    )
    _validate_prediction(prediction)
    return prediction


def _bucket(score: Decimal) -> str:
    if score >= Decimal("90"):
        return "90-100"
    lower = max(0, int(score // 10) * 10)
    upper = lower + 9
    return f"{lower}-{upper}"


def _money(value: Decimal) -> str:
    return str(value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def _pct(value: Decimal) -> float:
    return float((value * 100).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def _mean(values: Iterable[Decimal]) -> Decimal | None:
    items = list(values)
    return sum(items, Decimal("0")) / len(items) if items else None


def _median(values: Iterable[Decimal]) -> Decimal | None:
    items = sorted(values)
    if not items:
        return None
    midpoint = len(items) // 2
    if len(items) % 2:
        return items[midpoint]
    return (items[midpoint - 1] + items[midpoint]) / 2


def _sample(rows: list[Prediction], config: ValidationConfig) -> list[Prediction]:
    ordered = sorted(rows, key=lambda row: (row.analysis_date, row.symbol))
    if config.random_sample_size is None or config.random_sample_size >= len(ordered):
        return ordered
    if config.random_sample_size < 1:
        raise Issue079InputError("random_sample_size must be positive")
    generator = random.Random(config.random_seed)
    return sorted(generator.sample(ordered, config.random_sample_size), key=lambda row: (row.analysis_date, row.symbol))


def _diagnostic_assessment(sampled: list[Prediction], periods: list[dict]) -> dict:
    """Describe whether supplied scores have an expected synthetic signal.

    This is a pipeline diagnostic, not an investment recommendation. Simple
    thresholds make known synthetic scenarios useful regression fixtures.
    """

    high = [row.forward_return for row in sampled if row.score >= Decimal("70")]
    low = [row.forward_return for row in sampled if row.score < Decimal("40")]
    spread = (_mean(high) or Decimal("0")) - (_mean(low) or Decimal("0"))
    bucket_means = []
    for lower in range(0, 100, 10):
        label = "90-100" if lower == 90 else f"{lower}-{lower + 9}"
        values = [row.forward_return for row in sampled if _bucket(row.score) == label]
        if values:
            bucket_means.append(_mean(values) or Decimal("0"))
    monotonic = all(left <= right for left, right in zip(bucket_means, bucket_means[1:], strict=False))
    beat_rate = (
        Decimal(sum(Decimal(period["difference"]) > 0 for period in periods)) / len(periods)
        if periods else Decimal("0")
    )
    if spread >= Decimal("0.08") and monotonic and beat_rate >= Decimal("0.60"):
        diagnosis = "strong-synthetic-signal"
    elif spread <= Decimal("-0.10"):
        diagnosis = "inverted-synthetic-signal"
    elif abs(spread) < Decimal("0.03"):
        diagnosis = "null-or-weak-synthetic-signal"
    else:
        diagnosis = "mixed-or-insufficient-signal"
    return {
        "diagnosis": diagnosis,
        "high_score_mean_return_pct": _pct(_mean(high) or Decimal("0")),
        "low_score_mean_return_pct": _pct(_mean(low) or Decimal("0")),
        "high_minus_low_spread_pct": _pct(spread),
        "score_bucket_means_monotonic": monotonic,
        "periods_beating_spy_pct": _pct(beat_rate),
        "interpretation": "Synthetic pipeline diagnostic only; not evidence about the production algorithm.",
    }


def run_validation(rows: list[Prediction], config: ValidationConfig | None = None) -> dict:
    """Run deterministic score, outcome, and $10,000 comparison diagnostics.

    The output is machine-readable and contains the algorithm/data versions,
    seed, assumptions, and an explicit inconclusive status for offline/demo
    inputs.  It does not persist data or publish claims; callers may persist
    the returned object in an immutable run record after review.
    """

    config = config or ValidationConfig()
    sampled = _sample(rows, config)
    for row in sampled:
        _validate_prediction(row)
    if config.max_holdings < 1:
        raise Issue079InputError("max_holdings must be positive")

    bucket_report: dict[str, dict] = {}
    for lower in range(0, 100, 10):
        label = f"{lower}-{lower + 9}"
        bucket_rows = [row for row in sampled if _bucket(row.score) == label]
        returns = [row.forward_return for row in bucket_rows]
        bucket_report[label] = {
            "sample_size": len(bucket_rows),
            "average_forward_return_pct": _pct(_mean(returns) or Decimal("0")),
            "median_forward_return_pct": _pct(_median(returns) or Decimal("0")),
            "average_excess_return_pct": _pct(_mean(row.excess_return for row in bucket_rows) or Decimal("0")),
            "loss_rate_pct": _pct(Decimal(sum(row.forward_return < 0 for row in bucket_rows)) / len(bucket_rows)) if bucket_rows else None,
            "symbols": [row.symbol for row in bucket_rows],
        }

    cost_factor = Decimal("1") - (Decimal("2") * config.transaction_cost_bps / Decimal("10000"))
    periods = []
    for analysis_date in sorted({row.analysis_date for row in sampled}):
        period_rows = [row for row in sampled if row.analysis_date == analysis_date]
        eligible = sorted(
            (row for row in period_rows if row.score >= Decimal(str(config.score_threshold))),
            key=lambda row: (-row.score, row.symbol),
        )[: config.max_holdings]
        if not eligible:
            continue
        strategy_return = _mean(row.forward_return for row in eligible) or Decimal("0")
        benchmark_returns = {row.benchmark_return for row in eligible}
        if len(benchmark_returns) != 1:
            raise Issue079InputError(f"benchmark prices disagree for {analysis_date}")
        benchmark_return = next(iter(benchmark_returns))
        factor_value = config.initial_capital * (Decimal("1") + strategy_return) * cost_factor
        spy_value = config.initial_capital * (Decimal("1") + benchmark_return) * cost_factor
        periods.append({
            "analysis_date": analysis_date.isoformat(),
            "factor_value": _money(factor_value),
            "spy_value": _money(spy_value),
            "difference": _money(factor_value - spy_value),
            "factor_return_pct": _pct(strategy_return),
            "spy_return_pct": _pct(benchmark_return),
            "holdings": [row.symbol for row in eligible],
        })

    contributions: dict[str, list[Decimal]] = {}
    for row in sampled:
        for name, value in row.model_contributions:
            contributions.setdefault(name, []).append(value)
    contribution_report = {
        name: {"sample_size": len(values), "average_points": float(_mean(values) or Decimal("0"))}
        for name, values in sorted(contributions.items())
    }
    diagnostic = _diagnostic_assessment(sampled, periods)
    payload = {
        "status": "inconclusive",
        "result_classification": "Inconclusive",
        "limitations": [
            "Offline/demo or user-supplied CSV data is not evidence of production validation.",
            "This first slice evaluates one-year forward outcomes; rolling 5-year/10-year evaluation requires those isolated outcome columns.",
            "Confidence intervals, complete historical universes, delisted coverage, corporate-action reconciliation, and database persistence are follow-up phases.",
        ],
        "run": {
            "algorithm_version": config.algorithm_version,
            "data_version": config.data_version,
            "benchmark": config.benchmark,
            "random_seed": config.random_seed,
            "sample_size": len(sampled),
            "initial_capital": _money(config.initial_capital),
            "transaction_cost_bps_round_trip": str(config.transaction_cost_bps * 2),
            "configuration_hash": hashlib.sha256(json.dumps(asdict(config), default=str, sort_keys=True).encode()).hexdigest(),
        },
        "score_buckets": bucket_report,
        "portfolio_periods": periods,
        "model_contributions": contribution_report,
        "diagnostic_assessment": diagnostic,
        "forward_outcome_disclosure": {
            "source_columns": ["end_price_1y", "spy_end_price_1y"],
            "isolated_from_signal_inputs": True,
        },
    }
    return payload


def demo_rows() -> list[Prediction]:
    """Return deterministic offline rows for a smoke run, not validation evidence."""

    rows: list[Prediction] = []
    start = date(2005, 1, 3)
    profiles = (
        ("ALFA", 88, "technology", Decimal("1.18"), "survivor"),
        ("BETA", 74, "industrials", Decimal("1.08"), "survivor"),
        ("GAMMA", 52, "healthcare", Decimal("0.94"), "delisted"),
        ("DELTA", 28, "financials", Decimal("0.86"), "failed"),
    )
    for year in range(20):
        analysis = start.replace(year=start.year + year)
        for symbol, score, sector, multiple, status in profiles:
            base = Decimal(100 + year * 2 + score)
            spy_start = Decimal(100 + year * 3)
            rows.append(
                Prediction(
                    symbol=symbol,
                    analysis_date=analysis,
                    available_at=analysis - timedelta(days=3),
                    execution_date=analysis,
                    score=Decimal(score),
                    signal="Attractive" if score >= 70 else "Neutral" if score >= 40 else "Avoid",
                    start_price=base,
                    end_price_1y=base * multiple,
                    spy_start_price=spy_start,
                    spy_end_price_1y=spy_start * Decimal("1.06"),
                    sector=sector,
                    market_cap_band="large" if score >= 70 else "mid",
                    regime="synthetic",
                    survivor_status=status,
                    model_contributions=(("quality", Decimal(score) / 10), ("value", Decimal(10 if score >= 70 else 4)),),
                )
            )
    return rows
