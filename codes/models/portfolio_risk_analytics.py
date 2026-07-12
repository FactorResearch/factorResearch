"""Portfolio-level V2.1 risk analytics from an equity curve."""

from __future__ import annotations

import math
from typing import Any

import numpy as np
import pandas as pd

from codes.core import financial_math as fm
from codes.models.risk_metrics import RISK_FREE_RATE

MONTHS_PER_YEAR = 12
ROLLING_WINDOW_MONTHS = 12


def analyze_equity_curve(
    dates: list[str],
    values: list[float],
    *,
    risk_free_rate: float = RISK_FREE_RATE,
) -> dict[str, Any]:
    """Compute portfolio risk analytics from monthly portfolio values."""
    frame = _clean_curve(dates, values)
    if frame.empty or len(frame) < 3:
        return {"error": "Insufficient portfolio history for risk analytics"}

    frame["return"] = frame["value"].pct_change()
    returns = frame["return"].dropna().values.astype(float)
    if len(returns) < 2:
        return {"error": "Insufficient return history for risk analytics"}

    frame["peak"] = frame["value"].cummax()
    frame["drawdown"] = np.where(
        frame["peak"] > 0,
        frame["value"] / frame["peak"] - 1.0,
        0.0,
    )

    max_drawdown = float(frame["drawdown"].min())
    total_return = float(frame["value"].iloc[-1] / frame["value"].iloc[0] - 1.0)
    n_years = max((frame["date"].iloc[-1] - frame["date"].iloc[0]).days / 365.25, 1 / MONTHS_PER_YEAR)
    annual_return = fm.cagr(frame["value"].iloc[0], frame["value"].iloc[-1], n_years) or 0.0
    downside_deviation = _downside_deviation(returns, risk_free_rate)
    var_95 = fm.percentile(returns, 5) or 0.0
    tail = returns[returns <= var_95]
    cvar_95 = float(np.mean(tail)) if len(tail) else var_95
    recovery_time = _recovery_time_months(frame)
    ulcer = _ulcer_index(frame["drawdown"].values)
    rolling = _rolling_ratios(frame, risk_free_rate)

    return {
        "error": None,
        "n_months": int(len(frame)),
        "n_years": round(n_years, 1),
        "total_return": round(total_return * 100, 2),
        "annual_return": round(annual_return * 100, 2),
        "max_drawdown": round(max_drawdown * 100, 2),
        "downside_deviation": round(downside_deviation * 100, 2) if downside_deviation is not None else None,
        "var_95": round(var_95 * 100, 2),
        "cvar_95": round(cvar_95 * 100, 2),
        "recovery_time_months": recovery_time,
        "recovery_factor": _recovery_factor(total_return, max_drawdown),
        "ulcer_index": round(ulcer * 100, 2),
        "worst_month": _worst_period(frame, "ME"),
        "worst_quarter": _worst_period(frame, "QE"),
        "worst_year": _worst_period(frame, "YE"),
        "drawdown_curve": [
            {"date": row.date.strftime("%Y-%m-%d"), "drawdown": round(float(row.drawdown) * 100, 2)}
            for row in frame.itertuples()
        ],
        "underwater": [
            {"date": row.date.strftime("%Y-%m-%d"), "value": round(float(row.drawdown) * 100, 2)}
            for row in frame.itertuples()
        ],
        "rolling_sharpe": rolling["sharpe"],
        "rolling_sortino": rolling["sortino"],
        "risk_free_rate": risk_free_rate,
    }


def _clean_curve(dates: list[str], values: list[float]) -> pd.DataFrame:
    if not dates or not values or len(dates) != len(values):
        return pd.DataFrame()
    frame = pd.DataFrame({"date": pd.to_datetime(dates), "value": pd.to_numeric(values, errors="coerce")})
    frame = frame.replace([np.inf, -np.inf], np.nan).dropna()
    frame = frame[frame["value"] > 0].sort_values("date").reset_index(drop=True)
    return frame


def _downside_deviation(returns: np.ndarray, risk_free_rate: float) -> float | None:
    if len(returns) == 0:
        return None
    rf_period = risk_free_rate / MONTHS_PER_YEAR
    downside_sq = np.minimum(returns - rf_period, 0.0) ** 2
    variance = float(np.sum(downside_sq) / len(returns))
    return math.sqrt(variance) * math.sqrt(MONTHS_PER_YEAR) if variance > 0 else None


def _recovery_time_months(frame: pd.DataFrame) -> int | None:
    trough_idx = int(frame["drawdown"].idxmin())
    if float(frame["drawdown"].iloc[trough_idx]) >= 0:
        return 0
    prior_peak = float(frame["peak"].iloc[trough_idx])
    recovered = frame.iloc[trough_idx:][frame.iloc[trough_idx:]["value"] >= prior_peak]
    if recovered.empty:
        return None
    recovery_date = recovered["date"].iloc[0]
    trough_date = frame["date"].iloc[trough_idx]
    return max(
        0,
        (recovery_date.year - trough_date.year) * 12
        + (recovery_date.month - trough_date.month),
    )


def _ulcer_index(drawdowns: np.ndarray) -> float:
    if len(drawdowns) == 0:
        return 0.0
    downside = np.minimum(drawdowns, 0.0)
    return math.sqrt(float(np.mean(downside ** 2)))


def _recovery_factor(total_return: float, max_drawdown: float) -> float | None:
    if max_drawdown >= -0.001:
        return None
    return round(total_return / abs(max_drawdown), 3)


def _worst_period(frame: pd.DataFrame, freq: str) -> dict[str, Any] | None:
    indexed = frame.set_index("date")["value"]
    period_values = indexed.resample(freq).last().dropna()
    if len(period_values) < 2:
        return None
    period_returns = period_values.pct_change().dropna()
    if period_returns.empty:
        return None
    worst_date = period_returns.idxmin()
    return {
        "period": worst_date.strftime("%Y" if freq == "YE" else "%Y-%m"),
        "return": round(float(period_returns.loc[worst_date]) * 100, 2),
    }


def _rolling_ratios(frame: pd.DataFrame, risk_free_rate: float) -> dict[str, list[dict[str, Any]]]:
    returns = frame[["date", "return"]].dropna().reset_index(drop=True)
    sharpe_points: list[dict[str, Any]] = []
    sortino_points: list[dict[str, Any]] = []
    if len(returns) < ROLLING_WINDOW_MONTHS:
        return {"sharpe": sharpe_points, "sortino": sortino_points}

    for end in range(ROLLING_WINDOW_MONTHS, len(returns) + 1):
        window = returns.iloc[end - ROLLING_WINDOW_MONTHS:end]
        values = window["return"].values.astype(float)
        date = window["date"].iloc[-1].strftime("%Y-%m-%d")
        sharpe = fm.sharpe_ratio(values, risk_free_rate=risk_free_rate, periods_per_year=MONTHS_PER_YEAR)
        annual_return = float(np.mean(values) * MONTHS_PER_YEAR)
        sortino = fm.sortino_ratio(
            values,
            annual_return=annual_return,
            risk_free_rate=risk_free_rate,
            periods_per_year=MONTHS_PER_YEAR,
        )
        sharpe_points.append({"date": date, "value": round(sharpe, 3) if sharpe is not None else None})
        sortino_points.append({"date": date, "value": round(sortino, 3) if sortino is not None else None})
    return {"sharpe": sharpe_points, "sortino": sortino_points}
