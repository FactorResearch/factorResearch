"""Portfolio optimization engine.

Optimizers are long-only and fully invested:

* weights sum to 1.0
* weights are bounded between 0 and max_weight
* no leverage
* no shorting

Inputs are normalized monthly return series. Provider-specific price loading
belongs outside this module.
"""

from __future__ import annotations

import math
from typing import Any

import numpy as np
import pandas as pd

from codes.core.engine_contracts import (
    EngineContract,
    EngineSchema,
    FeatureFlag,
    SchemaField,
    validate_engine_input,
    validate_engine_output,
)

MONTHS_PER_YEAR = 12
DEFAULT_RISK_FREE_RATE = 0.045


CONTRACT = EngineContract(
    name="portfolio_optimization",
    version="2.0.0",
    feature_flags=frozenset({
        FeatureFlag.INTERNAL,
        FeatureFlag.BETA,
        FeatureFlag.V2,
        FeatureFlag.ENTERPRISE,
    }),
    input_schema=EngineSchema((
        SchemaField("returns", (pd.DataFrame,), description="Aligned monthly asset returns"),
        SchemaField("current_weights", (dict,), required=False, nullable=True, description="Current portfolio weights by symbol"),
    )),
    output_schema=EngineSchema((
        SchemaField("symbols", (list,), description="Optimized symbols"),
        SchemaField("n_months", (int,), description="Overlapping monthly return observations"),
        SchemaField("methods", (dict,), description="Current and optimized portfolio allocations"),
        SchemaField("risk_free_rate", (int, float), description="Annual risk-free rate used"),
    )),
    documentation=__doc__ or "",
    interpretation_guide=(
        "Outputs are advisory allocations derived from historical monthly "
        "returns and covariance. They are not trade instructions."
    ),
)


def get_contract() -> EngineContract:
    return CONTRACT


def validate_input(payload: dict | None):
    return validate_engine_input(CONTRACT, payload)


def validate_output(payload: dict | None):
    return validate_engine_output(CONTRACT, payload)


def optimize_portfolio(
    returns: pd.DataFrame,
    current_weights: dict[str, float] | None = None,
    *,
    risk_free_rate: float = DEFAULT_RISK_FREE_RATE,
    max_weight: float = 1.0,
    risk_aversion: float = 3.0,
) -> dict[str, Any]:
    """Run V2.0 portfolio optimizers against aligned monthly returns."""
    clean = _clean_returns(returns)
    if clean.empty or len(clean) < 6:
        return {"error": "Insufficient overlapping return history"}

    symbols = list(clean.columns)
    n_assets = len(symbols)
    if n_assets == 0:
        return {"error": "No valid assets to optimize"}

    current = _normalize_weights(current_weights, symbols)
    if current is None:
        current = np.repeat(1.0 / n_assets, n_assets)

    if n_assets == 1:
        weights = np.array([1.0], dtype=float)
        methods = {
            "current": _method_result(symbols, weights, clean, risk_free_rate),
            "mean_variance": _method_result(symbols, weights, clean, risk_free_rate),
            "max_sharpe": _method_result(symbols, weights, clean, risk_free_rate),
            "min_variance": _method_result(symbols, weights, clean, risk_free_rate),
            "risk_parity": _method_result(symbols, weights, clean, risk_free_rate),
        }
        return _result(symbols, clean, methods, risk_free_rate)

    try:
        from scipy.optimize import minimize
    except ModuleNotFoundError:
        return {"error": "SciPy is required for portfolio optimization"}

    mean_returns = clean.mean().values.astype(float) * MONTHS_PER_YEAR
    cov = _annualized_covariance(clean)
    bounds = _bounds(n_assets, max_weight)
    constraints = ({"type": "eq", "fun": lambda w: float(np.sum(w) - 1.0)},)
    x0 = _bounded_initial(current, max_weight)

    def variance(weights: np.ndarray) -> float:
        return _portfolio_variance(weights, cov)

    def negative_sharpe(weights: np.ndarray) -> float:
        stats = _portfolio_stats(weights, mean_returns, cov, risk_free_rate)
        sharpe = stats["sharpe"]
        if sharpe is None:
            return 1e6
        return -float(sharpe)

    def negative_utility(weights: np.ndarray) -> float:
        ret = float(weights @ mean_returns)
        var = variance(weights)
        return -(ret - risk_aversion * var)

    def risk_parity_error(weights: np.ndarray) -> float:
        contributions = _risk_contributions(weights, cov)
        if contributions is None:
            return 1e6
        target = np.repeat(1.0 / n_assets, n_assets)
        return float(np.sum((contributions - target) ** 2))

    methods = {
        "current": _method_result(symbols, current, clean, risk_free_rate),
        "mean_variance": _method_result(
            symbols,
            _solve(minimize, negative_utility, x0, bounds, constraints),
            clean,
            risk_free_rate,
        ),
        "max_sharpe": _method_result(
            symbols,
            _solve(minimize, negative_sharpe, x0, bounds, constraints),
            clean,
            risk_free_rate,
        ),
        "min_variance": _method_result(
            symbols,
            _solve(minimize, variance, x0, bounds, constraints),
            clean,
            risk_free_rate,
        ),
        "risk_parity": _method_result(
            symbols,
            _solve(minimize, risk_parity_error, x0, bounds, constraints),
            clean,
            risk_free_rate,
        ),
    }
    return _result(symbols, clean, methods, risk_free_rate)


def _clean_returns(returns: pd.DataFrame) -> pd.DataFrame:
    if returns is None or returns.empty:
        return pd.DataFrame()
    clean = returns.copy()
    clean = clean.apply(pd.to_numeric, errors="coerce")
    clean = clean.replace([np.inf, -np.inf], np.nan).dropna(axis=0, how="any")
    clean = clean.loc[:, clean.std(ddof=1) > 0]
    return clean


def _annualized_covariance(returns: pd.DataFrame) -> np.ndarray:
    cov = returns.cov().values.astype(float) * MONTHS_PER_YEAR
    cov = np.nan_to_num(cov, nan=0.0, posinf=0.0, neginf=0.0)
    cov = (cov + cov.T) / 2.0
    min_diag = max(float(np.max(np.diag(cov))) * 1e-8, 1e-10)
    return cov + np.eye(cov.shape[0]) * min_diag


def _normalize_weights(weights: dict[str, float] | None, symbols: list[str]) -> np.ndarray | None:
    if not weights:
        return None
    values = []
    for symbol in symbols:
        try:
            values.append(float(weights.get(symbol, 0.0)))
        except (TypeError, ValueError):
            values.append(0.0)
    arr = np.array(values, dtype=float)
    arr = np.where(np.isfinite(arr) & (arr > 0), arr, 0.0)
    total = float(np.sum(arr))
    if total <= 0:
        return None
    return arr / total


def _bounds(n_assets: int, max_weight: float) -> tuple[tuple[float, float], ...]:
    upper = min(max(float(max_weight), 1.0 / n_assets), 1.0)
    return tuple((0.0, upper) for _ in range(n_assets))


def _bounded_initial(weights: np.ndarray, max_weight: float) -> np.ndarray:
    clipped = np.clip(weights, 0.0, max_weight)
    total = float(np.sum(clipped))
    if total <= 0:
        return np.repeat(1.0 / len(weights), len(weights))
    return clipped / total


def _solve(minimize, objective, x0, bounds, constraints) -> np.ndarray:
    result = minimize(
        objective,
        x0,
        method="SLSQP",
        bounds=bounds,
        constraints=constraints,
        options={"maxiter": 500, "ftol": 1e-10, "disp": False},
    )
    if not result.success or result.x is None:
        return x0
    weights = np.clip(np.asarray(result.x, dtype=float), 0.0, 1.0)
    total = float(np.sum(weights))
    return x0 if total <= 0 else weights / total


def _portfolio_variance(weights: np.ndarray, cov: np.ndarray) -> float:
    value = float(weights @ cov @ weights)
    return max(value, 0.0)


def _portfolio_stats(
    weights: np.ndarray,
    mean_returns: np.ndarray,
    cov: np.ndarray,
    risk_free_rate: float,
) -> dict[str, float | None]:
    ret = float(weights @ mean_returns)
    var = _portfolio_variance(weights, cov)
    vol = math.sqrt(var)
    sharpe = None if vol <= 0 else (ret - risk_free_rate) / vol
    return {
        "expected_return": ret,
        "volatility": vol,
        "sharpe": sharpe,
    }


def _risk_contributions(weights: np.ndarray, cov: np.ndarray) -> np.ndarray | None:
    variance = _portfolio_variance(weights, cov)
    if variance <= 0:
        return None
    marginal = cov @ weights
    contributions = weights * marginal / variance
    contributions = np.where(np.isfinite(contributions), contributions, 0.0)
    total = float(np.sum(contributions))
    if total <= 0:
        return None
    return contributions / total


def _method_result(
    symbols: list[str],
    weights: np.ndarray,
    returns: pd.DataFrame,
    risk_free_rate: float,
) -> dict[str, Any]:
    clean = _clean_returns(returns)
    mean_returns = clean.mean().values.astype(float) * MONTHS_PER_YEAR
    cov = _annualized_covariance(clean)
    stats = _portfolio_stats(weights, mean_returns, cov, risk_free_rate)
    contributions = _risk_contributions(weights, cov)
    return {
        "weights": {
            symbol: round(float(weight), 6)
            for symbol, weight in zip(symbols, weights)
        },
        "risk_contribution": {
            symbol: round(float(contribution), 6)
            for symbol, contribution in zip(symbols, contributions)
        } if contributions is not None else {},
        "expected_return": round(stats["expected_return"] * 100, 2),
        "volatility": round(stats["volatility"] * 100, 2),
        "sharpe": round(stats["sharpe"], 3) if stats["sharpe"] is not None else None,
    }


def _result(
    symbols: list[str],
    returns: pd.DataFrame,
    methods: dict[str, dict[str, Any]],
    risk_free_rate: float,
) -> dict[str, Any]:
    return {
        "symbols": symbols,
        "n_months": int(len(returns)),
        "methods": methods,
        "risk_free_rate": risk_free_rate,
        "error": None,
    }
