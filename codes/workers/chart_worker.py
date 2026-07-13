"""Idempotent chart precompute helpers."""

from __future__ import annotations

from codes.data import cache, db
from codes.services import chart_service

PRIMARY_ANALYSIS_CHARTS = ("eps_history", "price_history", "dividend_history")


def precompute_analysis_charts(ticker: str, chart_types: tuple[str, ...] = PRIMARY_ANALYSIS_CHARTS) -> dict:
    """Generate common chart datasets after an analysis has been persisted."""
    data = _load_analysis(ticker)
    if not data:
        return {"ticker": ticker.upper(), "generated": [], "errors": [{"chart_type": "*", "error": "analysis_missing"}]}

    generated: list[dict] = []
    errors: list[dict] = []
    for chart_type in chart_types:
        dataset = chart_service.get_analysis_chart_dataset(data, chart_type)
        meta = dataset.get("meta", {})
        if dataset.get("error"):
            errors.append({"chart_type": chart_type, "error": dataset["error"]})
        else:
            generated.append({
                "chart_type": chart_type,
                "cache_key": meta.get("cache_key"),
                "cache_hit": meta.get("cache_hit"),
            })
    return {"ticker": ticker.upper(), "generated": generated, "errors": errors}


def _load_analysis(ticker: str) -> dict | None:
    loader = getattr(db, "get_analysis", None)
    if loader is not None:
        return loader(ticker)
    return cache.read("analysis", ticker.upper()) or cache.read("analysis", ticker.lower())
