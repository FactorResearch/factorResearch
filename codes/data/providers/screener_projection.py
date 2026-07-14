"""Typed, provider-neutral screener projections for verified market facts."""

from __future__ import annotations

from codes.engine import scorer
from codes.models import graham, quality


FUNDAMENTAL_PROJECTION_VERSION = "fundamental-v1"


def build_fundamental_screener_projection(
    *,
    market_code: str,
    symbol: str,
    name: str | None,
    sector: str | None,
    currency: str | None,
    sec_facts: dict,
    data_confidence: str,
    price: float | None = None,
) -> dict:
    """Calculate the durable, pre-momentum screener row for one issuer."""
    graham_result = graham.score(price, sec_facts)
    quality_result = quality.score(sec_facts)
    composite = scorer.fundamental_only(graham_result, quality_result)

    return {
        "market_code": market_code.upper(),
        "symbol": symbol.upper(),
        "name": name or symbol.upper(),
        "sector": sector,
        "currency": currency,
        "graham_score": graham_result["total_score"],
        "graham_max": graham_result["total_max"],
        "graham_pct": composite["graham_pct"],
        "quality_score": quality_result["total_score"],
        "quality_max": quality_result["total_max"],
        "quality_pct": composite["quality_pct"],
        "composite_score": composite["composite_score"],
        "verdict": composite["verdict"],
        "verdict_label": composite["verdict_label"],
        "roe": quality_result.get("roe"),
        "op_margin": quality_result.get("op_margin"),
        "eps_years": graham_result.get("eps_years", 0),
        "div_years": graham_result.get("div_years", 0),
        "graham_number": graham_result.get("graham_number"),
        "buffett_iv": None,
        "market_cap": graham_result.get("market_cap"),
        "price": price,
        "analyzed": True,
        "score_scope": "fundamental",
        "projection_version": FUNDAMENTAL_PROJECTION_VERSION,
        "data_confidence": data_confidence,
    }
