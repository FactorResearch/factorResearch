"""
Historical Factor Snapshots — ISSUE_012 Layer 5.

Append-only dated record of factor scores, distinct from Layer 1's
factor_scores table (which only ever holds the latest value). Backtests
should read from here via get_factor_scores_asof() instead of the current
score, once enough history has accumulated — this eliminates the
[BACKTEST BIAS WARNING] documented in codes/engine/backtest.py.

Snapshots are recorded going forward only; there is no way to backfill
scores for dates before this module existed.
"""

from __future__ import annotations

import datetime

from ..data import db
from . import factor_engine


def snapshot_today(symbol: str, analysis_result: dict,
                    as_of: str | None = None) -> dict:
    """
    Extract factor scores from a completed analysis and record them as an
    immutable dated snapshot. Call this alongside
    factor_engine.persist_factor_scores() — same extraction, different
    (append-only, dated) storage.
    """
    snapshot_date = as_of or datetime.date.today().isoformat()
    scores = factor_engine.extract_factor_scores(analysis_result)
    if scores:
        db.record_factor_snapshot(symbol.upper(), snapshot_date, scores)
    return scores


def get_factor_scores_asof(symbol: str, as_of: str) -> dict[str, dict]:
    """
    Return {factor_name: {score, max_score, snapshot_date}} using the most
    recent snapshot on or before `as_of` for each known factor. Factors
    with no snapshot at or before that date are omitted (not backfilled
    with today's score — that would reintroduce the bias this layer fixes).
    """
    symbol = symbol.upper().strip()
    out: dict[str, dict] = {}
    for factor_name in factor_engine.FACTOR_SOURCES:
        row = db.get_factor_score_asof(symbol, factor_name, as_of)
        if row:
            out[factor_name] = row
    return out


def has_sufficient_history(symbol: str, min_dates: int = 2) -> bool:
    """
    True once a symbol has enough distinct snapshot dates for a rebalanced
    backtest to be meaningfully point-in-time rather than a single frozen
    score. Callers (e.g. backtest.py) should gate on this before trusting
    get_factor_scores_asof() over the current live score.
    """
    return len(db.list_snapshot_dates(symbol.upper())) >= min_dates