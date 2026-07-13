"""V3 institutional portfolio analytics.

All functions are stateless: callers provide holdings, cached company analysis,
and optional price histories. Results are computed for the current request and
are not persisted by this module.
"""

from __future__ import annotations

import math
from typing import Any

import numpy as np
import pandas as pd

VERSION = "3.0.0"


def analyze_portfolio(
    portfolio: dict,
    *,
    analyses: dict[str, dict] | None = None,
    histories: dict[str, pd.DataFrame] | None = None,
    benchmark_symbol: str = "SPY",
    benchmark_history: pd.DataFrame | None = None,
) -> dict:
    holdings = portfolio.get("holdings") or {}
    if not holdings:
        return {"engine_version": VERSION, "error": "Portfolio is empty"}

    analyses = analyses or {}
    histories = histories or {}
    benchmark_symbol = str(benchmark_symbol or "SPY").upper().strip()
    weights = holding_weights(holdings)
    returns = return_matrix(histories)
    correlation = correlation_matrix(returns)
    benchmark_returns = benchmark_return_series(benchmark_history)
    factor_exposure = portfolio_factor_exposure(weights, analyses)
    risk_budget = risk_budgeting(returns, weights, benchmark_returns)

    result = {
        "engine_version": VERSION,
        "benchmark": benchmark_controls(benchmark_symbol),
        "weights": weights,
        "exposures": {
            "sector": exposure_by(weights, analyses, "sector"),
            "industry": exposure_by(weights, analyses, "industry"),
            "country": country_exposure(weights, analyses),
            "market_cap": market_cap_exposure(weights, analyses),
            "style": style_exposure(weights, analyses),
        },
        "portfolio_factor_exposure": factor_exposure,
        "risk_budget": risk_budget,
        "estimated_liquidity": estimated_liquidity(weights, analyses),
        "hidden_concentration": hidden_concentration(weights, analyses, correlation),
        "correlation_matrix": correlation,
        "hierarchical_clustering": hierarchical_clustering(correlation),
        "pca": pca_summary(returns),
        "historical_stress_testing": historical_stress_tests(returns),
        "scenario_shocks": scenario_shocks(weights, analyses, returns, risk_budget),
        "policy_checks": policy_checks(weights, factor_exposure, risk_budget, analyses, correlation),
        "rebalancing_optimizer": rebalancing_optimizer(holdings, weights, analyses),
        "attribution": return_attribution(weights, histories),
        "rolling_attribution": rolling_attribution(weights, histories),
        "income_yield": income_yield_view(weights, holdings, analyses),
        "tax_view": tax_aware_view(holdings),
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


def benchmark_return_series(history: pd.DataFrame | None) -> pd.Series:
    frame = pd.DataFrame(history)
    if frame.empty or "Date" not in frame or "Close" not in frame:
        return pd.Series(dtype=float)
    frame = frame.copy()
    frame["Date"] = pd.to_datetime(frame["Date"], errors="coerce")
    frame["Close"] = pd.to_numeric(frame["Close"], errors="coerce")
    frame = frame.dropna(subset=["Date", "Close"]).sort_values("Date")
    return frame.set_index("Date")["Close"].pct_change().dropna().rename("benchmark")


def benchmark_controls(selected: str) -> dict:
    options = [
        {"symbol": "SPY", "label": "S&P 500"},
        {"symbol": "QQQ", "label": "Nasdaq 100"},
        {"symbol": "IWM", "label": "Russell 2000"},
        {"symbol": "DIA", "label": "Dow Jones Industrial Average"},
        {"symbol": "VTI", "label": "US Total Market"},
        {"symbol": "ACWI", "label": "Global Equities"},
    ]
    symbols = {option["symbol"] for option in options}
    if selected not in symbols:
        options.append({"symbol": selected, "label": f"Custom benchmark: {selected}"})
    return {
        "selected": selected,
        "options": options,
        "premium_data_required": False,
    }


def portfolio_factor_exposure(weights: dict[str, float], analyses: dict[str, dict]) -> dict:
    fields = {
        "value": "graham_pct",
        "quality": "quality_pct",
        "momentum": "momentum_pct",
        "defensive": "risk_pct",
        "profitability": "profitability_pct",
        "factor_momentum": "factor_momentum_pct",
    }
    totals = {name: 0.0 for name in fields}
    coverage = {name: 0.0 for name in fields}
    for symbol, weight in weights.items():
        enhanced = (analyses.get(symbol) or {}).get("enhanced") or {}
        for name, field in fields.items():
            value = enhanced.get(field)
            if value is None:
                continue
            totals[name] += weight * _num(value)
            coverage[name] += weight
    return {
        name: {
            "score": round(totals[name] / coverage[name], 2) if coverage[name] else None,
            "coverage": round(coverage[name] * 100, 2),
        }
        for name in fields
    }


def risk_budgeting(
    returns: pd.DataFrame,
    weights: dict[str, float],
    benchmark_returns: pd.Series | None = None,
) -> dict:
    if returns.empty:
        return {"holdings": [], "portfolio": {}, "method": "covariance_risk_budget"}
    symbols = [symbol for symbol in returns.columns if symbol in weights]
    if not symbols:
        return {"holdings": [], "portfolio": {}, "method": "covariance_risk_budget"}
    frame = returns[symbols].dropna()
    if frame.empty:
        return {"holdings": [], "portfolio": {}, "method": "covariance_risk_budget"}
    raw_weights = np.array([weights[symbol] for symbol in symbols], dtype=float)
    raw_weights = raw_weights / raw_weights.sum() if raw_weights.sum() else np.ones(len(symbols)) / len(symbols)
    cov = frame.cov().to_numpy(dtype=float)
    portfolio_returns = frame.to_numpy(dtype=float) @ raw_weights
    variance = float(raw_weights @ cov @ raw_weights)
    monthly_vol = math.sqrt(max(variance, 0.0))
    annual_vol = monthly_vol * math.sqrt(12)
    cov_weight = cov @ raw_weights
    rows = []
    for index, symbol in enumerate(symbols):
        variance_share = (
            (raw_weights[index] * cov_weight[index] / variance) * 100
            if variance > 0 else 0.0
        )
        rows.append({
            "symbol": symbol,
            "weight": round(raw_weights[index] * 100, 2),
            "risk_contribution": round(variance_share, 2),
            "standalone_volatility": round(float(frame[symbol].std(ddof=0) * math.sqrt(12) * 100), 2),
        })
    beta = None
    if benchmark_returns is not None and not benchmark_returns.empty:
        joined = pd.concat([
            pd.Series(portfolio_returns, index=frame.index, name="portfolio"),
            benchmark_returns.rename("benchmark"),
        ], axis=1).dropna()
        if len(joined) >= 3:
            bench = joined["benchmark"].to_numpy(dtype=float)
            port = joined["portfolio"].to_numpy(dtype=float)
            bench_var = float(np.var(bench, ddof=1))
            if bench_var > 0:
                beta = float(np.cov(port, bench, ddof=1)[0, 1] / bench_var)
    var_95 = float(np.percentile(portfolio_returns, 5)) if len(portfolio_returns) else 0.0
    cvar_95 = float(np.mean(portfolio_returns[portfolio_returns <= var_95])) if len(portfolio_returns) else var_95
    downside = portfolio_returns[portfolio_returns < 0]
    downside_dev = float(np.sqrt(np.mean(np.square(downside))) * math.sqrt(12)) if len(downside) else 0.0
    return {
        "holdings": sorted(rows, key=lambda row: row["risk_contribution"], reverse=True),
        "portfolio": {
            "annual_volatility": round(annual_vol * 100, 2),
            "downside_deviation": round(downside_dev * 100, 2),
            "var_95": round(var_95 * 100, 2),
            "cvar_95": round(cvar_95 * 100, 2),
            "beta": round(beta, 3) if beta is not None else None,
        },
        "method": "covariance_risk_budget",
    }


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
    p05_path = [round(float(np.percentile(values[:, step], 5) - 1) * 100, 2) for step in range(months + 1)]
    p50_path = [round(float(np.percentile(values[:, step], 50) - 1) * 100, 2) for step in range(months + 1)]
    p95_path = [round(float(np.percentile(values[:, step], 95) - 1) * 100, 2) for step in range(months + 1)]
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
        "series": {
            "months": list(range(months + 1)),
            "p05": p05_path,
            "p50": p50_path,
            "p95": p95_path,
        },
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


def scenario_shocks(
    weights: dict[str, float],
    analyses: dict[str, dict],
    returns: pd.DataFrame,
    risk_budget: dict,
) -> list[dict]:
    sectors = exposure_by(weights, analyses, "sector")
    countries = country_exposure(weights, analyses)
    beta = ((risk_budget or {}).get("portfolio") or {}).get("beta")
    beta = _num(beta) or 1.0
    vol = ((risk_budget or {}).get("portfolio") or {}).get("annual_volatility")
    vol = (_num(vol) / 100.0) or (
        float(returns.mean(axis=1).std(ddof=0) * math.sqrt(12)) if not returns.empty else 0.16
    )
    tech_weight = _exposure_lookup(sectors, "Technology") / 100.0
    energy_weight = _exposure_lookup(sectors, "Energy") / 100.0
    non_us_weight = max(0.0, 1.0 - (_exposure_lookup(countries, "United States") / 100.0))
    scenarios = [
        ("Market -10%", -0.10 * beta, "beta_proxy"),
        ("Rates +100 bps", -0.25 * vol - 0.04 * tech_weight, "duration_proxy"),
        ("USD +5%", -0.05 * non_us_weight, "currency_exposure_proxy"),
        ("Technology -15%", -0.15 * tech_weight, "sector_exposure_proxy"),
        ("Oil +20%", 0.08 * energy_weight - 0.02 * (1.0 - energy_weight), "sector_exposure_proxy"),
    ]
    return [
        {"scenario": label, "estimated_impact": round(value * 100, 2), "method": method}
        for label, value, method in scenarios
    ]


def policy_checks(
    weights: dict[str, float],
    factor_exposure: dict,
    risk_budget: dict,
    analyses: dict[str, dict],
    correlation: dict,
) -> dict:
    sectors = exposure_by(weights, analyses, "sector")
    max_position = max(weights.values()) * 100 if weights else 0.0
    max_sector = max(sectors.values()) if sectors else 0.0
    beta = ((risk_budget or {}).get("portfolio") or {}).get("beta")
    avg_corr = (correlation or {}).get("average_correlation")
    quality = ((factor_exposure or {}).get("quality") or {}).get("score")
    rules = [
        ("Max single holding <= 25%", max_position <= 25.0, max_position, "position_concentration"),
        ("Max sector <= 35%", max_sector <= 35.0, max_sector, "sector_concentration"),
        ("Portfolio beta <= 1.20", beta is None or beta <= 1.20, beta, "market_sensitivity"),
        ("Average correlation <= 0.65", avg_corr is None or avg_corr <= 0.65, avg_corr, "hidden_correlation"),
        ("Quality exposure >= 50", quality is None or quality >= 50.0, quality, "factor_quality"),
    ]
    checks = [
        {
            "rule": label,
            "passed": bool(passed),
            "value": round(float(value), 3) if value is not None else None,
            "type": rule_type,
        }
        for label, passed, value, rule_type in rules
    ]
    return {
        "passed": sum(1 for check in checks if check["passed"]),
        "failed": sum(1 for check in checks if not check["passed"]),
        "checks": checks,
    }


def rebalancing_optimizer(
    holdings: dict[str, dict[str, Any]],
    weights: dict[str, float],
    analyses: dict[str, dict],
    *,
    max_position: float = 0.20,
) -> dict:
    total_value = _portfolio_value(holdings)
    if total_value <= 0 or not weights:
        return {"recommendations": [], "method": "constraint_rebalance"}
    target_weight = min(max_position, 1.0 / len(weights))
    residual = 1.0 - target_weight * len(weights)
    targets = {symbol: target_weight for symbol in weights}
    if residual > 0:
        quality_scores = {
            symbol: _num(((analyses.get(symbol) or {}).get("enhanced") or {}).get("quality_pct"))
            for symbol in weights
        }
        total_quality = sum(score for score in quality_scores.values() if score > 0)
        for symbol in targets:
            share = quality_scores[symbol] / total_quality if total_quality > 0 else 1.0 / len(weights)
            targets[symbol] += residual * share
    recommendations = []
    for symbol, weight in weights.items():
        current_value = total_value * weight
        target_value = total_value * targets[symbol]
        delta = target_value - current_value
        if abs(delta) < max(total_value * 0.01, 100):
            continue
        recommendations.append({
            "symbol": symbol,
            "action": "buy" if delta > 0 else "sell",
            "dollar_delta": round(delta, 2),
            "current_weight": round(weight * 100, 2),
            "target_weight": round(targets[symbol] * 100, 2),
        })
    return {
        "recommendations": sorted(recommendations, key=lambda row: abs(row["dollar_delta"]), reverse=True),
        "method": "max_position_quality_tilt",
        "constraints": {"max_position": round(max_position * 100, 2)},
    }


def return_attribution(weights: dict[str, float], histories: dict[str, pd.DataFrame]) -> dict:
    rows = []
    total = 0.0
    for symbol, weight in weights.items():
        frame = _history_frame(histories.get(symbol))
        if frame.empty or len(frame) < 2:
            continue
        start = float(frame["Close"].iloc[0])
        end = float(frame["Close"].iloc[-1])
        total_return = (end / start - 1.0) if start > 0 else 0.0
        contribution = weight * total_return
        total += contribution
        rows.append({
            "symbol": symbol,
            "weight": round(weight * 100, 2),
            "total_return": round(total_return * 100, 2),
            "contribution": round(contribution * 100, 2),
        })
    return {
        "total_attributed_return": round(total * 100, 2),
        "holdings": sorted(rows, key=lambda row: row["contribution"]),
        "method": "buy_and_hold_weighted_return",
    }


def rolling_attribution(weights: dict[str, float], histories: dict[str, pd.DataFrame]) -> list[dict]:
    returns = return_matrix(histories)
    if returns.empty:
        return []
    symbols = [symbol for symbol in returns.columns if symbol in weights]
    if not symbols:
        return []
    weighted = returns[symbols].mul(pd.Series({symbol: weights[symbol] for symbol in symbols}), axis=1)
    quarterly = weighted.resample("QE").sum().tail(8)
    rows = []
    for date, row in quarterly.iterrows():
        contributions = {
            symbol: round(float(value) * 100, 2)
            for symbol, value in row.sort_values().items()
        }
        rows.append({
            "end_date": date.strftime("%Y-%m-%d"),
            "total_contribution": round(float(row.sum()) * 100, 2),
            "contributions": contributions,
        })
    return rows


def income_yield_view(
    weights: dict[str, float],
    holdings: dict[str, dict[str, Any]],
    analyses: dict[str, dict],
) -> dict:
    rows = []
    weighted_yield = 0.0
    coverage = 0.0
    for symbol, weight in weights.items():
        analysis = analyses.get(symbol) or {}
        capital = analysis.get("capital_allocation") or {}
        enhanced = analysis.get("enhanced") or {}
        dividend_yield = (
            capital.get("dividend_yield_implied")
            or enhanced.get("dividend_yield_implied")
            or _latest_dividend_yield(analysis, holdings.get(symbol) or {})
        )
        if dividend_yield is None:
            rows.append({"symbol": symbol, "weight": round(weight * 100, 2), "yield": None, "income": None})
            continue
        value = _holding_value(holdings.get(symbol) or {})
        annual_income = value * (_num(dividend_yield) / 100.0)
        weighted_yield += weight * _num(dividend_yield)
        coverage += weight
        rows.append({
            "symbol": symbol,
            "weight": round(weight * 100, 2),
            "yield": round(_num(dividend_yield), 2),
            "income": round(annual_income, 2),
        })
    return {
        "weighted_yield": round(weighted_yield / coverage, 2) if coverage else None,
        "estimated_annual_income": round(sum(_num(row.get("income")) for row in rows), 2),
        "coverage": round(coverage * 100, 2),
        "holdings": rows,
        "method": "cached_dividend_yield_or_sec_dividend_proxy",
    }


def tax_aware_view(holdings: dict[str, dict[str, Any]]) -> dict:
    rows = []
    total_gain = 0.0
    for symbol, holding in holdings.items():
        shares = _num(holding.get("shares"))
        cost = _num(holding.get("price_at_add"))
        current = _num(holding.get("current_price") or holding.get("price_at_add"))
        cost_basis = shares * cost
        market_value = shares * current
        gain = market_value - cost_basis
        total_gain += gain
        rows.append({
            "symbol": symbol,
            "cost_basis": round(cost_basis, 2),
            "market_value": round(market_value, 2),
            "unrealized_gain": round(gain, 2),
            "gain_pct": round((gain / cost_basis) * 100, 2) if cost_basis > 0 else None,
            "tax_loss_candidate": gain < 0,
            "holding_period_status": "needs_lot_dates",
        })
    return {
        "unrealized_gain": round(total_gain, 2),
        "tax_loss_candidates": [row["symbol"] for row in rows if row["tax_loss_candidate"]],
        "holdings": rows,
        "method": "position_cost_basis_estimate",
        "premium_data_required_for_full_tax_lots": False,
    }


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


def _history_frame(history) -> pd.DataFrame:
    frame = pd.DataFrame(history)
    if frame.empty or "Date" not in frame or "Close" not in frame:
        return pd.DataFrame()
    frame = frame.copy()
    frame["Date"] = pd.to_datetime(frame["Date"], errors="coerce")
    frame["Close"] = pd.to_numeric(frame["Close"], errors="coerce")
    return frame.dropna(subset=["Date", "Close"]).sort_values("Date")


def _holding_value(holding: dict[str, Any]) -> float:
    shares = _num(holding.get("shares"))
    price = holding.get("current_price")
    if price is None:
        price = holding.get("price_at_add")
    return shares * _num(price)


def _portfolio_value(holdings: dict[str, dict[str, Any]]) -> float:
    return sum(_holding_value(holding) for holding in holdings.values())


def _latest_dividend_yield(analysis: dict, holding: dict[str, Any]) -> float | None:
    sec_facts = analysis.get("sec_facts") or {}
    dividends = sec_facts.get("dividends") or []
    if not dividends:
        return None
    latest = dividends[-1] if isinstance(dividends[-1], dict) else {}
    dividend = _num(latest.get("value"))
    price = _num(holding.get("current_price") or holding.get("price_at_add"))
    if dividend <= 0 or price <= 0:
        return None
    return dividend / price * 100


def _exposure_lookup(exposures: dict[str, float], needle: str) -> float:
    needle = needle.lower()
    for label, value in (exposures or {}).items():
        if needle in str(label).lower():
            return _num(value)
    return 0.0


def _num(value) -> float:
    try:
        if value is None or (isinstance(value, float) and math.isnan(value)):
            return 0.0
        return float(value)
    except (TypeError, ValueError):
        return 0.0
