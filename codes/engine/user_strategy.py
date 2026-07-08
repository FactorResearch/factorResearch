"""
User Strategy Weighting — ISSUE_012 Layer 3.

Stores ONLY per-user weight preferences (codes/data/db.py: user_weights
table). Company analysis and factor scores are never duplicated per user —
weighted_score is always computed dynamically at request time from
company_analysis.get_company_analysis()'s shared factor_scores.
"""

from ..data import db
from . import company_analysis
from .factor_engine import FACTOR_SOURCES

# Defaults mirror scorer.ENHANCED_WEIGHTS where a factor is scored there;
# piotroski/buffett default to 0 since they're currently display-only in
# the legacy composite. Users can raise them via set_user_weights().
DEFAULT_WEIGHTS = {
    "graham":             0.12,
    "quality":            0.18,
    "momentum":           0.12,
    "piotroski":          0.0,
    "risk":               0.06,
    "buffett":            0.0,
    "earnings_revision":  0.12,
    "profitability":      0.12,
    "fcf_quality":        0.10,
    "capital_allocation": 0.08,
    "growth_quality":     0.07,
}


def normalize_weights(raw: dict[str, float]) -> dict[str, float]:
    """Clamp negatives to 0, drop unknown factor names, sum to 1.0."""
    cleaned = {k: max(0.0, float(v)) for k, v in raw.items() if k in FACTOR_SOURCES}
    total = sum(cleaned.values())
    if total <= 0:
        n = len(FACTOR_SOURCES)
        return {k: 1.0 / n for k in FACTOR_SOURCES}
    return {k: cleaned.get(k, 0.0) / total for k in FACTOR_SOURCES}


def get_user_weights(user_id: str) -> dict[str, float]:
    """Return a user's normalized weights, or normalized defaults if unset."""
    stored = db.get_user_weights(user_id)
    if not stored:
        return normalize_weights(DEFAULT_WEIGHTS)
    return normalize_weights(stored)


def set_user_weights(user_id: str, weights: dict[str, float]) -> dict[str, float]:
    """Validate, normalize, and persist a user's weight config."""
    normalized = normalize_weights(weights)
    db.set_user_weights(user_id, normalized)
    return normalized


def compute_weighted_score(symbol: str, user_id: str | None = None,
                            weights: dict[str, float] | None = None) -> dict:
    """
    weighted_score = Σ(factor_pct × user_weight), computed at request time.
    Missing factors are excluded and remaining weights are renormalized
    proportionally (consistent with altman.py / growth_quality.py pattern)
    so absent data doesn't silently zero out the score.
    """
    analysis = company_analysis.get_company_analysis(symbol)
    if analysis is None:
        return {"symbol": symbol.upper(), "error": "No shared analysis available for this company."}

    w = normalize_weights(weights) if weights is not None else get_user_weights(user_id or "")

    factor_pcts: dict[str, float] = {}
    for factor_name, fs in analysis["factor_scores"].items():
        score, max_score = fs.get("score"), fs.get("max_score")
        if score is not None and max_score:
            factor_pcts[factor_name] = score / max_score * 100

    available_weight = sum(w[k] for k in factor_pcts if k in w)
    if available_weight <= 0:
        weighted_score = 50.0
    else:
        raw = sum(factor_pcts[k] * w[k] for k in factor_pcts if k in w)
        weighted_score = round(raw / available_weight, 2)

    # Simpler, correct proportional reweight:
    weighted_score = (
        round(sum(factor_pcts[k] * w[k] for k in factor_pcts if k in w) / available_weight, 2)
        if available_weight > 0 else 50.0
    )

    missing = [k for k in FACTOR_SOURCES if k not in factor_pcts]

    return {
        "symbol":          analysis["symbol"],
        "weighted_score":  weighted_score,
        "weights_used":    w,
        "factor_pcts":     {k: round(v, 2) for k, v in factor_pcts.items()},
        "missing_factors": missing,
        "updated_at":      analysis["updated_at"],
    }