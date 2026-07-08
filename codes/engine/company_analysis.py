"""
Shared Company Analysis — ISSUE_012 Layer 2.

Read-only view combining shared factor scores (Layer 1) with display
metadata (name, sector, price). Deliberately contains NO weighting logic —
weighted_score = Σ(factor_score × user_weight) is Layer 3's job and must
be computed at request time from get_company_analysis()'s factor_scores,
never duplicated or baked in here.
"""

from ..data import db
from . import factor_engine


def get_company_analysis(symbol: str) -> dict | None:
    """
    Return the shared, weighting-free analysis for one company:
      {
        "symbol": str,
        "name": str, "sector": str, "price": float | None,
        "market_cap": float | None, "updated_at": str | None,
        "factor_scores": {factor_name: {score, max_score, computed_at}},
      }
    None if the company has never been analyzed.
    """
    symbol = symbol.upper().strip()
    entry = db.get_analysis_entry(symbol)
    if not entry:
        return None
    data = entry["data"]
    if not data or "error" in data:
        return None

    return {
        "symbol":        symbol,
        "name":          data.get("name", symbol),
        "sector":        data.get("sector", ""),
        "price":         data.get("price"),
        "market_cap":    data.get("market_cap"),
        "updated_at":    entry.get("updated_at"),
        "factor_scores": factor_engine.get_factor_scores(symbol),
    }


def list_analyzed_companies() -> list[str]:
    """Every symbol with a shared company analysis available."""
    return db.list_analysis_tickers()