"""
Shared Factor Engine — ISSUE_012 Layer 1.

Extracts atomic factor scores from already-computed model results
(graham, quality, momentum, etc.) and persists them once per company,
shared globally. This does NOT recompute anything — it reads the same
result dicts analyze_stock() already produces and normalizes/stores them.

Downstream layers (user weighting, strategy cache, historical snapshots)
will read from get_factor_scores() instead of re-running model code.
"""

from ..data import db

# Canonical factor name -> (result_dict_key_in_analyze_stock, score_key, max_key)
# score_key/max_key follow each model's own total_score/total_max convention.
FACTOR_SOURCES = {
    "graham":             ("graham",             "total_score", "total_max"),
    "quality":            ("quality",             "total_score", "total_max"),
    "momentum":           ("momentum",             "total_score", "total_max"),
    "piotroski":          ("piotroski",             "f_score",     "f_score_max"),
    "risk":               ("risk",                 "risk_score",  "risk_score_max"),
    "buffett":             ("buffett",              "total_score", "total_max"),
    "earnings_revision":   ("earnings_revision",    "total_score", "total_max"),
    "profitability":       ("profitability",        "total_score", "total_max"),
    "fcf_quality":         ("fcf_quality",           "total_score", "total_max"),
    "capital_allocation":  ("capital_allocation",    "total_score", "total_max"),
    "growth_quality":      ("growth_quality",        "total_score", "total_max"),
    "accounting_quality":  ("accounting_quality",    "total_score", "total_max"),
}


def extract_factor_scores(analysis_result: dict) -> dict[str, tuple[float | None, float | None]]:
    """
    Pull (score, max) pairs for every known factor out of an analyze_stock()
    result dict. Missing/None sub-results are skipped, not zeroed.
    """
    out: dict[str, tuple[float | None, float | None]] = {}
    for factor_name, (result_key, score_key, max_key) in FACTOR_SOURCES.items():
        sub = analysis_result.get(result_key)
        if not sub:
            continue
        score = sub.get(score_key)
        max_score = sub.get(max_key)
        if score is not None:
            out[factor_name] = (score, max_score)
    return out


def persist_factor_scores(symbol: str, analysis_result: dict) -> dict:
    scores = extract_factor_scores(analysis_result)
    if scores:
        db.upsert_factor_scores(symbol.upper(), scores)
        # ISSUE_012 Layer 5: also append an immutable dated snapshot so
        # backtests can build real point-in-time history over time.
        from . import factor_snapshot
        factor_snapshot.snapshot_today(symbol, analysis_result)
    return scores


def get_factor_scores(symbol: str) -> dict[str, dict]:
    """Read shared factor scores for a company. See db.get_factor_scores()."""
    return db.get_factor_scores(symbol.upper())
