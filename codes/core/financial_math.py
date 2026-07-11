"""Shared financial math primitives for analysis engines.

The functions in this module are deliberately provider-agnostic and operate on
plain numeric sequences. Callers are responsible for normalizing vendor data
before using these helpers.
"""

from __future__ import annotations

import math
from collections.abc import Iterable, Sequence

import numpy as np

TRADING_DAYS_PER_YEAR = 252
MONTHS_PER_YEAR = 12


def _finite_float(value: object) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def clean_numeric(values: Iterable[object], *, positive: bool = False) -> list[float]:
    """Return finite floats, optionally filtering non-positive values."""
    if values is None:
        return []
    cleaned = []
    for value in values:
        number = _finite_float(value)
        if number is None:
            continue
        if positive and number <= 0:
            continue
        cleaned.append(number)
    return cleaned


def simple_returns(values: Sequence[object]) -> list[float]:
    """Return simple period returns from a positive price/value series."""
    series = clean_numeric(values, positive=True)
    if len(series) < 2:
        return []
    return [
        (series[index] / series[index - 1]) - 1.0
        for index in range(1, len(series))
        if series[index - 1] > 0
    ]


def log_returns(values: Sequence[object]) -> list[float]:
    """Return log period returns from a positive price/value series."""
    series = clean_numeric(values, positive=True)
    if len(series) < 2:
        return []
    return [
        math.log(series[index] / series[index - 1])
        for index in range(1, len(series))
        if series[index - 1] > 0
    ]


def cagr(start_value: object, end_value: object, years: object) -> float | None:
    """Compound annual growth rate as a decimal."""
    start = _finite_float(start_value)
    end = _finite_float(end_value)
    period_years = _finite_float(years)
    if start is None or end is None or period_years is None:
        return None
    if start <= 0 or end < 0 or period_years <= 0:
        return None
    return (end / start) ** (1.0 / period_years) - 1.0


def volatility(returns: Sequence[object], *, periods_per_year: int = MONTHS_PER_YEAR) -> float | None:
    """Annualized sample volatility of returns."""
    values = clean_numeric(returns)
    if len(values) < 2 or periods_per_year <= 0:
        return None
    std = float(np.std(values, ddof=1))
    return std * math.sqrt(periods_per_year)


def sharpe_ratio(
    returns: Sequence[object],
    *,
    risk_free_rate: float = 0.0,
    periods_per_year: int = MONTHS_PER_YEAR,
) -> float | None:
    """Annualized Sharpe ratio using excess period returns."""
    values = clean_numeric(returns)
    if len(values) < 2 or periods_per_year <= 0:
        return None
    rf_period = risk_free_rate / periods_per_year
    excess = np.array(values, dtype=float) - rf_period
    std = float(np.std(excess, ddof=1))
    if std <= 0:
        return None
    return float(np.mean(excess) / std * math.sqrt(periods_per_year))


def sortino_ratio(
    returns: Sequence[object],
    *,
    annual_return: float | None = None,
    risk_free_rate: float = 0.0,
    periods_per_year: int = MONTHS_PER_YEAR,
) -> float | None:
    """Annualized Sortino ratio with downside deviation divided by total N."""
    values = clean_numeric(returns)
    if not values or periods_per_year <= 0:
        return None
    rf_period = risk_free_rate / periods_per_year
    arr = np.array(values, dtype=float)
    downside_sq = np.minimum(arr - rf_period, 0.0) ** 2
    down_var = float(np.sum(downside_sq) / len(arr))
    if down_var <= 0:
        return None
    down_std = math.sqrt(down_var) * math.sqrt(periods_per_year)
    if annual_return is None:
        annual_return = float(np.mean(arr) * periods_per_year)
    return (annual_return - risk_free_rate) / down_std


def drawdown_series(values: Sequence[object]) -> list[float]:
    """Return period drawdowns as decimals from a positive equity curve."""
    series = clean_numeric(values, positive=True)
    if not series:
        return []
    peaks = np.maximum.accumulate(np.array(series, dtype=float))
    with np.errstate(divide="ignore", invalid="ignore"):
        drawdowns = np.where(peaks > 0, (np.array(series, dtype=float) - peaks) / peaks, 0.0)
    return [float(value) for value in drawdowns]


def max_drawdown(values: Sequence[object]) -> float | None:
    """Worst peak-to-trough drawdown as a negative decimal."""
    drawdowns = drawdown_series(values)
    return min(drawdowns) if drawdowns else None


def calmar_ratio(annual_return: object, max_drawdown_value: object) -> float | None:
    """Annual return divided by absolute max drawdown."""
    ret = _finite_float(annual_return)
    drawdown = _finite_float(max_drawdown_value)
    if ret is None or drawdown is None or drawdown >= -0.001:
        return None
    return ret / abs(drawdown)


def covariance(x_values: Sequence[object], y_values: Sequence[object]) -> float | None:
    """Sample covariance between two same-length numeric series."""
    x = clean_numeric(x_values)
    y = clean_numeric(y_values)
    if len(x) != len(y) or len(x) < 2:
        return None
    return float(np.cov(np.array(x, dtype=float), np.array(y, dtype=float))[0, 1])


def covariance_matrix(rows: Sequence[Sequence[object]]) -> np.ndarray | None:
    """Sample covariance matrix for columns in a rectangular return table."""
    if rows is None:
        return None
    matrix = np.array(rows, dtype=float)
    if matrix.ndim != 2 or matrix.shape[0] < 2 or matrix.shape[1] < 1:
        return None
    if not np.isfinite(matrix).all():
        return None
    return np.cov(matrix, rowvar=False)


def correlation(x_values: Sequence[object], y_values: Sequence[object]) -> float | None:
    """Pearson correlation between two same-length numeric series."""
    x = clean_numeric(x_values)
    y = clean_numeric(y_values)
    if len(x) != len(y) or len(x) < 2:
        return None
    x_std = float(np.std(x, ddof=1))
    y_std = float(np.std(y, ddof=1))
    if x_std <= 0 or y_std <= 0:
        return None
    return float(np.corrcoef(np.array(x, dtype=float), np.array(y, dtype=float))[0, 1])


def correlation_matrix(rows: Sequence[Sequence[object]]) -> np.ndarray | None:
    """Correlation matrix for columns in a rectangular return table."""
    if rows is None:
        return None
    matrix = np.array(rows, dtype=float)
    if matrix.ndim != 2 or matrix.shape[0] < 2 or matrix.shape[1] < 1:
        return None
    if not np.isfinite(matrix).all():
        return None
    corr = np.corrcoef(matrix, rowvar=False)
    return corr if np.isfinite(corr).all() else None


def beta(asset_returns: Sequence[object], benchmark_returns: Sequence[object]) -> float | None:
    """Market beta: covariance(asset, benchmark) / variance(benchmark)."""
    benchmark = clean_numeric(benchmark_returns)
    asset = clean_numeric(asset_returns)
    if len(asset) != len(benchmark) or len(asset) < 2:
        return None
    variance = float(np.var(benchmark, ddof=1))
    if variance <= 0:
        return None
    cov = covariance(asset, benchmark)
    return None if cov is None else cov / variance


def alpha(
    asset_return: object,
    benchmark_return: object,
    beta_value: object,
    *,
    risk_free_rate: float = 0.0,
) -> float | None:
    """Jensen alpha as a decimal."""
    asset = _finite_float(asset_return)
    benchmark = _finite_float(benchmark_return)
    beta_number = _finite_float(beta_value)
    if asset is None or benchmark is None or beta_number is None:
        return None
    return asset - (risk_free_rate + beta_number * (benchmark - risk_free_rate))


def linear_regression(x_values: Sequence[object], y_values: Sequence[object]) -> dict | None:
    """Simple OLS regression with slope, intercept, r, and r_squared."""
    x = clean_numeric(x_values)
    y = clean_numeric(y_values)
    if len(x) != len(y) or len(x) < 2:
        return None
    x_arr = np.array(x, dtype=float)
    y_arr = np.array(y, dtype=float)
    x_var = float(np.var(x_arr, ddof=1))
    if x_var <= 0:
        return None
    slope = float(np.cov(x_arr, y_arr)[0, 1] / x_var)
    intercept = float(np.mean(y_arr) - slope * np.mean(x_arr))
    r_value = correlation(x, y)
    return {
        "slope": slope,
        "intercept": intercept,
        "r": r_value,
        "r_squared": None if r_value is None else r_value ** 2,
    }


def percentile_normalize(value: object, low: object, high: object) -> float | None:
    """Map value to a 0-100 score between low and high bounds."""
    number = _finite_float(value)
    lower = _finite_float(low)
    upper = _finite_float(high)
    if number is None or lower is None or upper is None or upper == lower:
        return None
    score = (number - lower) / (upper - lower) * 100.0
    return max(0.0, min(100.0, score))


def percentile(values: Sequence[object], pct: float) -> float | None:
    """Return a numeric percentile from finite values."""
    cleaned = clean_numeric(values)
    if not cleaned or not 0 <= pct <= 100:
        return None
    return float(np.percentile(cleaned, pct))


def percentile_rank(values: Sequence[object], current: object, *, inclusive: bool = True) -> float | None:
    """Return 0-100 percentile rank of current within finite values."""
    cleaned = clean_numeric(values)
    current_value = _finite_float(current)
    if not cleaned or current_value is None:
        return None
    arr = np.array(cleaned, dtype=float)
    count = np.sum(arr <= current_value) if inclusive else np.sum(arr < current_value)
    return float(count / len(arr) * 100.0)


def winsorize(values: Sequence[object], *, lower_pct: float = 5.0, upper_pct: float = 95.0) -> list[float]:
    """Clip values to percentile bounds."""
    cleaned = clean_numeric(values)
    if not cleaned:
        return []
    if not 0 <= lower_pct <= upper_pct <= 100:
        raise ValueError("percentile bounds must satisfy 0 <= lower <= upper <= 100")
    lower = float(np.percentile(cleaned, lower_pct))
    upper = float(np.percentile(cleaned, upper_pct))
    return [max(lower, min(upper, value)) for value in cleaned]


def rank_values(values: Sequence[object], *, descending: bool = True) -> list[int | None]:
    """Return competition ranks; invalid values receive None."""
    parsed = [_finite_float(value) for value in values]
    valid = sorted(
        ((index, value) for index, value in enumerate(parsed) if value is not None),
        key=lambda item: item[1],
        reverse=descending,
    )
    ranks: list[int | None] = [None] * len(parsed)
    previous_value = None
    previous_rank = 0
    for position, (index, value) in enumerate(valid, start=1):
        if previous_value is None or value != previous_value:
            previous_rank = position
            previous_value = value
        ranks[index] = previous_rank
    return ranks
