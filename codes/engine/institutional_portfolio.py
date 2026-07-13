"""V2.3 institutional portfolio analytics.

All functions are stateless: callers provide holdings, cached company analysis,
and optional price histories. Results are computed for the current request and
are not persisted by this module.
"""

from __future__ import annotations

import math
from typing import Any

import numpy as np
import pandas as pd

VERSION = "2.3.0"


def analyze_portfolio(
    portfolio: dict,
    *,
    analyses: dict[str, dict] | None = None,
    histories: dict[str, pd.DataFrame] | None = None,
) -> dict:
    holdings = portfolio.get("holdings") or {}
    if not holdings:
        return {"engine_version": VERSION, "error": "Portfolio is empty"}

    analyses = analyses or {}
    histories = histories or {}
    weights = holding_weights(holdings)
    returns = return_matrix(histories)
    correlation = correlation_matrix(returns)

    result = {
        "engine_version": VERSION,
        "weights": weights,
        "exposures": {
            "sector": exposure_by(weights, analyses, "sector"),
            "industry": exposure_by(weights, analyses, "industry"),
            "country": country_exposure(weights, analyses),
            "market_cap": market_cap_exposure(weights, analyses),
            "style": style_exposure(weights, analyses),
        },
        "estimated_liquidity": estimated_liquidity(weights, analyses),
        "hidden_concentration": hidden_concentration(weights, analyses, correlation),
        "correlation_matrix": correlation,
        "hierarchical_clustering": hierarchical_clustering(correlation),
        "pca": pca_summary(returns),
        "historical_stress_testing": historical_stress_tests(returns),
        "advanced_monte_carlo": {
            method: advanced_monte_carlo(returns, method=method)
            for method in ("gbm", "bootstrap", "fat_tail", "regime_aware")
        },
        "error": None,
    }
    return result


def holding_weights(holdings: dict[str, dict[str, Any]]) -> dict[str, float]:
    raw = {}
    for symbol, holding in holdings.items():
        shares = float(holding.get("shares") or 0.0)
        price = holding.get("current_price")
        if price is None:
            price = holding.get("price_at_add")
        raw[str(symbol).upper()] = max(shares * float(price or 0.0), 0.0)
    total = sum(raw.values())
    if total <= 0 and raw:
        equal = 1.0 / len(raw)
        return {symbol: equal for symbol in raw}
    return {symbol: value / total for symbol, value in raw.items() if total > 0}


def exposure_by(weights: dict[str, float], analyses: dict[str, dict], field: str) -> dict[str, float]:
    totals: dict[str, float] = {}
    for symbol, weight in weights.items():
        analysis = analyses.get(symbol) or {}
        label = (
            analysis.get(field)
            or (analysis.get("sec_facts") or {}).get(field)
            or (analysis.get("company") or {}).get(field)
            or "Unknown"
        )
        totals[str(label or "Unknown")] = totals.get(str(label or "Unknown"), 0.0) + weight
    return _pct_map(totals)


def country_exposure(weights: dict[str, float], analyses: dict[str, dict]) -> dict[str, float]:
    totals: dict[str, float] = {}
    for symbol, weight in weights.items():
        analysis = analyses.get(symbol) or {}
        country = analysis.get("country") or (analysis.get("company") or {}).get("country")
        if not country:
            country = _infer_country(symbol)
        totals[country] = totals.get(country, 0.0) + weight
    return _pct_map(totals)


def market_cap_exposure(weights: dict[str, float], analyses: dict[str, dict]) -> dict[str, float]:
    totals = {"Mega": 0.0, "Large": 0.0, "Mid": 0.0, "Small": 0.0, "Unknown": 0.0}
    for symbol, weight in weights.items():
        analysis = analyses.get(symbol) or {}
        market_cap = analysis.get("market_cap")
        if market_cap is None:
            market_cap = (analysis.get("graham") or {}).get("market_cap")
        bucket = _market_cap_bucket(market_cap)
        totals[bucket] += weight
    return _pct_map({key: value for key, value in totals.items() if value > 0})


def style_exposure(weights: dict[str, float], analyses: dict[str, dict]) -> dict[str, float]:
    totals: dict[str, float] = {}
    for symbol, weight in weights.items():
        enhanced = (analyses.get(symbol) or {}).get("enhanced") or {}
        scores = {
            "Value": _num(enhanced.get("graham_pct")),
            "Quality": _num(enhanced.get("quality_pct")),
            "Momentum": _num(enhanced.get("momentum_pct")),
            "Defensive": _num(enhanced.get("risk_pct")),
            "Profitability": _num(enhanced.get("profitability_pct")),
        }
        best_label, best_score = max(scores.items(), key=lambda item: item[1])
        label = best_label if best_score >= 55 else "Blend"
        totals[label] = totals.get(label, 0.0) + weight
    return _pct_map(totals)


def estimated_liquidity(weights: dict[str, float], analyses: dict[str, dict]) -> dict:
    rows = []
    weighted_score = 0.0
    for symbol, weight in weights.items():
        analysis = analyses.get(symbol) or {}
        market_cap = analysis.get("market_cap") or (analysis.get("graham") or {}).get("market_cap")
        market_cap_m = _num(market_cap)
        estimated_daily_dollar_volume = market_cap_m * 1_000_000 * 0.002 if market_cap_m > 0 else None
        if estimated_daily_dollar_volume is None:
            tier, score = "Unknown", 50.0
        elif estimated_daily_dollar_volume >= 250_000_000:
            tier, score = "High", 95.0
        elif estimated_daily_dollar_volume >= 25_000_000:
            tier, score = "Medium", 70.0
        else:
            tier, score = "Low", 35.0
        weighted_score += weight * score
        rows.append({
            "symbol": symbol,
            "weight": round(weight * 100, 2),
            "tier": tier,
            "estimated_daily_dollar_volume": (
                round(estimated_daily_dollar_volume, 2)
                if estimated_daily_dollar_volume is not None else None
            ),
        })
    return {
        "score": round(weighted_score, 2),
        "holdings": rows,
        "method": "Estimated from market cap when live volume is unavailable.",
    }


def return_matrix(histories: dict[str, pd.DataFrame]) -> pd.DataFrame:
    series = []
    for symbol, history in (histories or {}).items():
        frame = pd.DataFrame(history)
        if frame.empty or "Date" not in frame or "Close" not in frame:
            continue
        frame = frame.copy()
        frame["Date"] = pd.to_datetime(frame["Date"], errors="coerce")
        frame["Close"] = pd.to_numeric(frame["Close"], errors="coerce")
        frame = frame.dropna(subset=["Date", "Close"]).sort_values("Date")
        returns = frame.set_index("Date")["Close"].pct_change().dropna().rename(symbol)
        if len(returns) >= 6:
            series.append(returns)
    if not series:
        return pd.DataFrame()
    return pd.concat(series, axis=1).dropna(how="any")


def correlation_matrix(returns: pd.DataFrame) -> dict:
    if returns.empty or returns.shape[1] < 2:
        return {"symbols": list(returns.columns), "matrix": [], "average_correlation": None}
    corr = returns.corr().replace([np.inf, -np.inf], np.nan).fillna(0.0)
    symbols = list(corr.columns)
    values = corr.to_numpy(dtype=float)
    if len(symbols) > 1:
        upper = values[np.triu_indices(len(symbols), k=1)]
        avg_corr = float(np.mean(upper)) if upper.size else None
    else:
        avg_corr = None
    return {
        "symbols": symbols,
        "matrix": [[round(float(value), 4) for value in row] for row in values],
        "average_correlation": round(avg_corr, 4) if avg_corr is not None else None,
    }


def hierarchical_clustering(correlation: dict, *, threshold: float = 0.75) -> dict:
    symbols = correlation.get("symbols") or []
    matrix = np.array(correlation.get("matrix") or [])
    if len(symbols) == 0:
        return {"clusters": [], "method": "correlation_threshold", "threshold": threshold}
    seen: set[str] = set()
    clusters = []
    for index, symbol in enumerate(symbols):
        if symbol in seen:
            continue
        members = [symbol]
        seen.add(symbol)
        for other_index, other in enumerate(symbols):
            if other in seen or other_index == index:
                continue
            if matrix.size and float(matrix[index, other_index]) >= threshold:
                members.append(other)
                seen.add(other)
        clusters.append({"id": len(clusters) + 1, "members": members})
    return {"clusters": clusters, "method": "correlation_threshold", "threshold": threshold}


def pca_summary(returns: pd.DataFrame) -> dict:
    if returns.empty or returns.shape[1] < 2:
        return {"components": [], "explained_variance": [], "method": "covariance_eigendecomposition"}
    normalized = (returns - returns.mean()) / returns.std(ddof=0).replace(0, np.nan)
    normalized = normalized.dropna(axis=1, how="any")
    if normalized.shape[1] < 2:
        return {"components": [], "explained_variance": [], "method": "covariance_eigendecomposition"}
    cov = np.cov(normalized.to_numpy(dtype=float), rowvar=False)
    eigenvalues, eigenvectors = np.linalg.eigh(cov)
    order = np.argsort(eigenvalues)[::-1]
    eigenvalues = eigenvalues[order]
    eigenvectors = eigenvectors[:, order]
    total = float(np.sum(eigenvalues))
    explained = [float(value / total) if total > 0 else 0.0 for value in eigenvalues]
    symbols = list(normalized.columns)
    components = []
    for idx in range(min(3, len(explained))):
        loadings = {
            symbol: round(float(eigenvectors[pos, idx]), 4)
            for pos, symbol in enumerate(symbols)
        }
        components.append({
            "component": idx + 1,
            "explained_variance": round(explained[idx] * 100, 2),
            "loadings": loadings,
        })
    return {
        "components": components,
        "explained_variance": [round(value * 100, 2) for value in explained[:5]],
        "method": "covariance_eigendecomposition",
    }


def hidden_concentration(weights: dict[str, float], analyses: dict[str, dict], correlation: dict) -> dict:
    flags = []
    for symbol, weight in weights.items():
        if weight >= 0.25:
            flags.append({
                "type": "single_name",
                "label": symbol,
                "weight": round(weight * 100, 2),
                "severity": "high" if weight >= 0.35 else "medium",
            })
    for label, exposure in exposure_by(weights, analyses, "sector").items():
        if exposure >= 35:
            flags.append({
                "type": "sector",
                "label": label,
                "weight": exposure,
                "severity": "high" if exposure >= 50 else "medium",
            })
    clusters = hierarchical_clustering(correlation).get("clusters") or []
    for cluster in clusters:
        members = cluster.get("members") or []
        if len(members) < 2:
            continue
        weight = sum(weights.get(symbol, 0.0) for symbol in members)
        if weight >= 0.40:
            flags.append({
                "type": "correlated_cluster",
                "label": ", ".join(members),
                "weight": round(weight * 100, 2),
                "severity": "high" if weight >= 0.60 else "medium",
            })
    score = max(0.0, 100.0 - sum(20 if flag["severity"] == "high" else 10 for flag in flags))
    return {"score": round(score, 2), "flags": flags}


def advanced_monte_carlo(
    returns: pd.DataFrame,
    *,
    method: str = "gbm",
    paths: int = 1000,
    months: int = 24,
    seed: int = 230,
) -> dict:
    if returns.empty:
        return {"method": method, "error": "Insufficient return history"}
    portfolio_returns = returns.mean(axis=1)
    if len(portfolio_returns) < 6:
        return {"method": method, "error": "Insufficient return history"}
    rng = np.random.default_rng(seed)
    values = np.ones((paths, months + 1), dtype=float)
    mu = float(portfolio_returns.mean())
    sigma = float(portfolio_returns.std(ddof=0) or 0.0)
    downside_sigma = float(portfolio_returns[portfolio_returns < 0].std(ddof=0) or sigma or 0.01)
    for step in range(1, months + 1):
        if method == "bootstrap":
            shocks = rng.choice(portfolio_returns.to_numpy(dtype=float), size=paths, replace=True)
            growth = 1.0 + shocks
        elif method == "fat_tail":
            shocks = rng.standard_t(df=5, size=paths) * (sigma / math.sqrt(5 / 3 if sigma else 1))
            growth = np.exp((mu - 0.5 * sigma ** 2) + shocks)
        elif method == "regime_aware":
            stress = rng.random(paths) < 0.25
            shocks = rng.normal(mu, sigma or 0.01, size=paths)
            stress_shocks = rng.normal(mu - downside_sigma, max(downside_sigma, 0.01), size=paths)
            growth = 1.0 + np.where(stress, stress_shocks, shocks)
        else:
            shocks = rng.normal(0.0, sigma or 0.01, size=paths)
            growth = np.exp((mu - 0.5 * sigma ** 2) + shocks)
        values[:, step] = np.maximum(values[:, step - 1] * growth, 0.0)
    terminal = values[:, -1]
    return {
        "method": method,
        "tier": "advanced",
        "months": months,
        "paths": paths,
        "p05": round(float(np.percentile(terminal, 5) - 1) * 100, 2),
        "p50": round(float(np.percentile(terminal, 50) - 1) * 100, 2),
        "p95": round(float(np.percentile(terminal, 95) - 1) * 100, 2),
        "expected_return": round(float(np.mean(terminal) - 1) * 100, 2),
        "probability_loss": round(float(np.mean(terminal < 1.0)) * 100, 2),
        "error": None,
    }


def historical_stress_tests(returns: pd.DataFrame) -> list[dict]:
    if returns.empty:
        return []
    portfolio_returns = returns.mean(axis=1).sort_index()
    periods = {
        "COVID shock": ("2020-02-01", "2020-04-30"),
        "2022 rate shock": ("2022-01-01", "2022-10-31"),
        "Recent worst quarter": None,
    }
    rows = []
    for label, window in periods.items():
        if window is None:
            quarterly = (1 + portfolio_returns).resample("QE").prod() - 1
            if quarterly.empty:
                continue
            value = float(quarterly.min())
            rows.append({"scenario": label, "return": round(value * 100, 2), "source": "portfolio_history"})
            continue
        start, end = window
        slice_ = portfolio_returns.loc[start:end]
        if slice_.empty:
            continue
        value = float((1 + slice_).prod() - 1)
        rows.append({"scenario": label, "return": round(value * 100, 2), "source": "portfolio_history"})
    if not rows:
        annualized_vol = float(portfolio_returns.std(ddof=0) * math.sqrt(12))
        rows = [
            {"scenario": "Equity crash", "return": round(-1.5 * annualized_vol * 100, 2), "source": "volatility_proxy"},
            {"scenario": "Liquidity shock", "return": round(-0.75 * annualized_vol * 100, 2), "source": "volatility_proxy"},
        ]
    return rows


def _pct_map(values: dict[str, float]) -> dict[str, float]:
    return {
        key: round(float(value) * 100, 2)
        for key, value in sorted(values.items(), key=lambda item: item[1], reverse=True)
    }


def _market_cap_bucket(market_cap) -> str:
    value = _num(market_cap)
    if value <= 0:
        return "Unknown"
    # Existing analysis stores market cap in millions.
    if value >= 200_000:
        return "Mega"
    if value >= 10_000:
        return "Large"
    if value >= 2_000:
        return "Mid"
    return "Small"


def _infer_country(symbol: str) -> str:
    symbol = str(symbol).upper()
    if symbol.endswith(".TO") or symbol.endswith(".V"):
        return "Canada"
    if symbol.endswith(".L"):
        return "United Kingdom"
    if symbol.endswith(".T"):
        return "Japan"
    return "United States"


def _num(value) -> float:
    try:
        if value is None or (isinstance(value, float) and math.isnan(value)):
            return 0.0
        return float(value)
    except (TypeError, ValueError):
        return 0.0
