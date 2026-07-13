"""V2.2 factor research and attribution engine.

The engine operates on normalized return series. Provider adapters, database
loaders, and UI code should prepare data before calling this module.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from codes.core import financial_math as fm
from codes.core.engine_contracts import (
    EngineContract,
    EngineSchema,
    FeatureFlag,
    SchemaField,
    validate_engine_input,
    validate_engine_output,
)

VERSION = "2.2.0"
PERIODS_PER_YEAR = 12

MODEL_FACTORS = {
    "capm": ("mkt_rf",),
    "ff3": ("mkt_rf", "smb", "hml"),
    "carhart4": ("mkt_rf", "smb", "hml", "mom"),
    "ff5": ("mkt_rf", "smb", "hml", "rmw", "cma"),
}

CONTRACT = EngineContract(
    name="factor_research",
    version=VERSION,
    feature_flags=frozenset({
        FeatureFlag.INTERNAL,
        FeatureFlag.BETA,
        FeatureFlag.V2,
        FeatureFlag.ENTERPRISE,
    }),
    input_schema=EngineSchema((
        SchemaField("returns", (pd.DataFrame,), description="Normalized period return table"),
        SchemaField("model", (str,), required=False, nullable=True, description="capm, ff3, carhart4, or ff5"),
        SchemaField("risk_free_rate", (int, float), required=False, nullable=True, description="Annual risk-free rate"),
    )),
    output_schema=EngineSchema((
        SchemaField("model", (str,), description="Factor model used"),
        SchemaField("observations", (int,), description="Number of aligned return observations"),
        SchemaField("alpha_annualized", (int, float), description="Annualized regression intercept"),
        SchemaField("betas", (dict,), description="Factor exposure coefficients"),
        SchemaField("r_squared", (int, float), description="Regression explanatory power"),
        SchemaField("return_attribution", (dict,), description="Annualized factor and residual attribution"),
    )),
    documentation=__doc__ or "",
    interpretation_guide=(
        "Factor betas describe historical sensitivity to common return factors. "
        "Attribution is diagnostic and should not be treated as a forecast or recommendation."
    ),
)


def get_contract() -> EngineContract:
    return CONTRACT


def validate_input(payload: dict | None):
    return validate_engine_input(CONTRACT, payload)


def validate_output(payload: dict | None):
    return validate_engine_output(CONTRACT, payload)


def analyze_factor_model(
    returns: pd.DataFrame,
    *,
    model: str = "ff3",
    risk_free_rate: float = 0.0,
    periods_per_year: int = PERIODS_PER_YEAR,
) -> dict:
    """Run CAPM, Fama-French, or Carhart attribution on normalized returns."""
    normalized_model = _normalize_model(model)
    factors = MODEL_FACTORS[normalized_model]
    table = _prepare_factor_table(
        returns,
        factors=factors,
        risk_free_rate=risk_free_rate,
        periods_per_year=periods_per_year,
    )
    if len(table) < len(factors) + 2:
        return _empty_result(normalized_model, "Insufficient observations after alignment")

    y = table["asset_excess"].to_numpy(dtype=float)
    x = table[list(factors)].to_numpy(dtype=float)
    x_design = np.column_stack([np.ones(len(table)), x])

    coefficients, *_ = np.linalg.lstsq(x_design, y, rcond=None)
    alpha_period = float(coefficients[0])
    betas = {factor: float(value) for factor, value in zip(factors, coefficients[1:])}

    fitted = x_design @ coefficients
    residuals = y - fitted
    ss_res = float(np.sum(residuals ** 2))
    ss_tot = float(np.sum((y - float(np.mean(y))) ** 2))
    r_squared = 0.0 if ss_tot <= 0 else max(0.0, min(1.0, 1.0 - ss_res / ss_tot))

    attribution = return_attribution(
        betas,
        table[list(factors)],
        alpha_period=alpha_period,
        residuals=residuals,
        periods_per_year=periods_per_year,
    )

    return {
        "engine_version": VERSION,
        "model": normalized_model,
        "factors": list(factors),
        "observations": int(len(table)),
        "alpha_period": alpha_period,
        "alpha_annualized": alpha_period * periods_per_year,
        "betas": betas,
        "r_squared": r_squared,
        "return_attribution": attribution,
    }


def capm(
    returns: pd.DataFrame,
    *,
    risk_free_rate: float = 0.0,
    periods_per_year: int = PERIODS_PER_YEAR,
) -> dict:
    return analyze_factor_model(
        returns,
        model="capm",
        risk_free_rate=risk_free_rate,
        periods_per_year=periods_per_year,
    )


def capm_from_price_history(
    price_history,
    benchmark_history,
    *,
    risk_free_rate: float = 0.0,
    periods_per_year: int = PERIODS_PER_YEAR,
) -> dict:
    """Build CAPM attribution from normalized Date/Close price history."""
    frame = _price_return_frame(price_history, benchmark_history)
    if len(frame) < 12:
        return _empty_result("capm", "Insufficient overlapping return history")
    return capm(frame, risk_free_rate=risk_free_rate, periods_per_year=periods_per_year)


def fama_french_3(
    returns: pd.DataFrame,
    *,
    risk_free_rate: float = 0.0,
    periods_per_year: int = PERIODS_PER_YEAR,
) -> dict:
    return analyze_factor_model(
        returns,
        model="ff3",
        risk_free_rate=risk_free_rate,
        periods_per_year=periods_per_year,
    )


def carhart_4(
    returns: pd.DataFrame,
    *,
    risk_free_rate: float = 0.0,
    periods_per_year: int = PERIODS_PER_YEAR,
) -> dict:
    return analyze_factor_model(
        returns,
        model="carhart4",
        risk_free_rate=risk_free_rate,
        periods_per_year=periods_per_year,
    )


def fama_french_5(
    returns: pd.DataFrame,
    *,
    risk_free_rate: float = 0.0,
    periods_per_year: int = PERIODS_PER_YEAR,
) -> dict:
    return analyze_factor_model(
        returns,
        model="ff5",
        risk_free_rate=risk_free_rate,
        periods_per_year=periods_per_year,
    )


def return_attribution(
    betas: dict[str, float],
    factor_returns: pd.DataFrame,
    *,
    alpha_period: float = 0.0,
    residuals: list[float] | np.ndarray | None = None,
    periods_per_year: int = PERIODS_PER_YEAR,
) -> dict:
    """Decompose annualized excess return into factor, alpha, and residual pieces."""
    factor_contributions = {}
    for factor, beta in betas.items():
        if factor not in factor_returns:
            continue
        factor_contributions[factor] = float(beta) * float(factor_returns[factor].mean()) * periods_per_year

    residual_annualized = 0.0
    if residuals is not None:
        residual_arr = np.asarray(residuals, dtype=float)
        if residual_arr.size:
            residual_annualized = float(np.mean(residual_arr)) * periods_per_year

    alpha_annualized = float(alpha_period) * periods_per_year
    factor_total = float(sum(factor_contributions.values()))
    total = factor_total + alpha_annualized + residual_annualized
    return {
        "factor_contributions": factor_contributions,
        "factor_total": factor_total,
        "alpha": alpha_annualized,
        "residual": residual_annualized,
        "total_excess_return": total,
    }


def holdings_attribution(
    holdings: dict[str, dict[str, Any]],
    holding_factor_results: dict[str, dict[str, Any]],
) -> dict:
    """Aggregate holding-level factor exposures and return attribution by portfolio weight."""
    weights = _holding_weights(holdings)
    exposure_totals: dict[str, float] = {}
    contribution_totals: dict[str, float] = {}
    holding_rows = []

    for symbol, weight in weights.items():
        result = holding_factor_results.get(symbol, {})
        betas = result.get("betas") or {}
        attribution = (result.get("return_attribution") or {}).get("factor_contributions") or {}
        for factor, value in betas.items():
            exposure_totals[factor] = exposure_totals.get(factor, 0.0) + weight * float(value)
        for factor, value in attribution.items():
            contribution_totals[factor] = contribution_totals.get(factor, 0.0) + weight * float(value)
        holding_rows.append({
            "symbol": symbol,
            "weight": weight,
            "betas": {factor: weight * float(value) for factor, value in betas.items()},
            "factor_contributions": {factor: weight * float(value) for factor, value in attribution.items()},
        })

    return {
        "weights": weights,
        "portfolio_betas": exposure_totals,
        "portfolio_factor_contributions": contribution_totals,
        "holdings": holding_rows,
    }


def rolling_attribution(
    returns: pd.DataFrame,
    *,
    model: str = "ff3",
    window: int = 36,
    min_periods: int | None = None,
    risk_free_rate: float = 0.0,
    periods_per_year: int = PERIODS_PER_YEAR,
) -> list[dict]:
    """Run factor attribution over rolling windows."""
    if window < 3:
        raise ValueError("window must be at least 3 observations")
    min_obs = min_periods or window
    if min_obs < 3 or min_obs > window:
        raise ValueError("min_periods must be between 3 and window")

    prepared = _prepare_factor_table(
        returns,
        factors=MODEL_FACTORS[_normalize_model(model)],
        risk_free_rate=risk_free_rate,
        periods_per_year=periods_per_year,
    )
    rows: list[dict] = []
    for end in range(min_obs, len(prepared) + 1):
        start = max(0, end - window)
        frame = prepared.iloc[start:end].copy()
        frame["asset_return"] = frame["asset_excess"]
        result = analyze_factor_model(
            frame,
            model=model,
            risk_free_rate=0.0,
            periods_per_year=periods_per_year,
        )
        end_date = prepared.index[end - 1]
        rows.append({
            "end_date": str(end_date.date()) if hasattr(end_date, "date") else str(end_date),
            "observations": result["observations"],
            "alpha_annualized": result["alpha_annualized"],
            "betas": result["betas"],
            "r_squared": result["r_squared"],
            "return_attribution": result["return_attribution"],
        })
    return rows


def _normalize_model(model: str) -> str:
    normalized = str(model or "ff3").lower().replace("-", "").replace("_", "")
    aliases = {
        "famafrench3": "ff3",
        "famafrench5": "ff5",
        "carhart": "carhart4",
        "carhartfour": "carhart4",
        "carhart4factor": "carhart4",
    }
    normalized = aliases.get(normalized, normalized)
    if normalized not in MODEL_FACTORS:
        raise ValueError(f"Unsupported factor model: {model}")
    return normalized


def _prepare_factor_table(
    returns: pd.DataFrame,
    *,
    factors: tuple[str, ...],
    risk_free_rate: float,
    periods_per_year: int,
) -> pd.DataFrame:
    if not isinstance(returns, pd.DataFrame) or returns.empty:
        return pd.DataFrame()
    table = returns.copy()
    if "Date" in table.columns:
        table["Date"] = pd.to_datetime(table["Date"])
        table = table.sort_values("Date").set_index("Date")

    if "asset_excess" not in table.columns:
        if "asset_return" not in table.columns:
            return pd.DataFrame()
        rf = _period_rf(table, risk_free_rate=risk_free_rate, periods_per_year=periods_per_year)
        table["asset_excess"] = pd.to_numeric(table["asset_return"], errors="coerce") - rf

    if "mkt_rf" not in table.columns and "mkt_excess" in table.columns:
        table["mkt_rf"] = table["mkt_excess"]
    if "mkt_rf" not in table.columns and "market_return" in table.columns:
        rf = _period_rf(table, risk_free_rate=risk_free_rate, periods_per_year=periods_per_year)
        table["mkt_rf"] = pd.to_numeric(table["market_return"], errors="coerce") - rf

    required = ["asset_excess", *factors]
    missing = [column for column in required if column not in table.columns]
    if missing:
        return pd.DataFrame()
    table = table[required].apply(pd.to_numeric, errors="coerce").replace([np.inf, -np.inf], np.nan)
    return table.dropna()


def _price_return_frame(price_history, benchmark_history) -> pd.DataFrame:
    stock = _history_frame(price_history)
    benchmark = _history_frame(benchmark_history)
    if stock.empty or benchmark.empty:
        return pd.DataFrame()
    stock["asset_return"] = stock["Close"].pct_change()
    benchmark["mkt_rf"] = benchmark["Close"].pct_change()
    return (
        stock[["Date", "asset_return"]]
        .merge(benchmark[["Date", "mkt_rf"]], on="Date", how="inner")
        .dropna()
    )


def _history_frame(history) -> pd.DataFrame:
    frame = pd.DataFrame(history) if history is not None else pd.DataFrame()
    if frame.empty or "Date" not in frame.columns or "Close" not in frame.columns:
        return pd.DataFrame()
    frame = frame.copy()
    frame["Date"] = pd.to_datetime(frame["Date"], errors="coerce")
    frame["Close"] = pd.to_numeric(frame["Close"], errors="coerce")
    return frame.dropna(subset=["Date", "Close"]).sort_values("Date").reset_index(drop=True)


def _period_rf(table: pd.DataFrame, *, risk_free_rate: float, periods_per_year: int) -> pd.Series | float:
    if "rf" in table.columns:
        return pd.to_numeric(table["rf"], errors="coerce")
    if "risk_free_return" in table.columns:
        return pd.to_numeric(table["risk_free_return"], errors="coerce")
    return float(risk_free_rate) / periods_per_year if periods_per_year > 0 else 0.0


def _holding_weights(holdings: dict[str, dict[str, Any]]) -> dict[str, float]:
    raw_values = {}
    for symbol, holding in (holdings or {}).items():
        value = holding.get("market_value")
        if value is None:
            value = float(holding.get("shares", 0) or 0) * float(holding.get("price", holding.get("price_at_add", 0)) or 0)
        raw_values[str(symbol).upper()] = max(float(value or 0.0), 0.0)
    total = sum(raw_values.values())
    if total <= 0 and raw_values:
        equal = 1.0 / len(raw_values)
        return {symbol: equal for symbol in raw_values}
    return {symbol: value / total for symbol, value in raw_values.items() if total > 0}


def _empty_result(model: str, error: str) -> dict:
    return {
        "engine_version": VERSION,
        "model": model,
        "factors": list(MODEL_FACTORS[model]),
        "observations": 0,
        "alpha_period": 0.0,
        "alpha_annualized": 0.0,
        "betas": {},
        "r_squared": 0.0,
        "return_attribution": {
            "factor_contributions": {},
            "factor_total": 0.0,
            "alpha": 0.0,
            "residual": 0.0,
            "total_excess_return": 0.0,
        },
        "error": error,
    }
