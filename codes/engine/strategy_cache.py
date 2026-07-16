"""
Strategy Hash Cache — ISSUE_012 Layer 4.

Normalizes a user's weight configuration into a stable hash so identical
configurations from different users reuse the same cached backtest,
instead of each user re-triggering codes.engine.factor_backtest.run_factor_backtest().

Cache key components (per ISSUE_012 spec):
  strategy_hash        — hash of the normalized weight config
  data_version         — bump this manually when factor_scores data changes
                         materially (e.g. after a bulk SEC refresh sweep)
  rebalance_frequency  — reserved for future rebalancing strategies (n/a
                         for the current equal-weight top-N backtest, fixed
                         at "none")
  investment_universe  — top_n, since that defines which stocks qualify
  start_date/end_date  — derived from `years` (today's date is the anchor)

This module does not implement backtesting logic itself — it wraps
factor_backtest.run_factor_backtest() with cache read-through/write-through.
"""

from __future__ import annotations

import datetime
import hashlib
import json

from ..data import db
from . import factor_backtest, user_strategy

DATA_VERSION = "v1"          # bump manually when factor_scores semantics change
REBALANCE_FREQUENCY = "none"  # current backtest is buy-and-hold, no rebalancing


def strategy_hash(weights: dict[str, float]) -> str:
    """
    Stable hash of a normalized weight config. Rounds to 4 decimals and
    sorts keys so equivalent configs (e.g. differing float noise, or key
    ordering) always hash identically.
    """
    normalized = user_strategy.normalize_weights(weights)
    canonical = json.dumps(
        {k: round(v, 4) for k, v in sorted(normalized.items())},
        sort_keys=True,
    )
    return hashlib.sha256(canonical.encode()).hexdigest()[:16]


def _cache_key(weights: dict[str, float], top_n: int, years: int) -> str:
    h = strategy_hash(weights)
    end_date = datetime.date.today().isoformat()
    return f"{DATA_VERSION}:{h}:{REBALANCE_FREQUENCY}:{top_n}:{years}y:{end_date}"


def get_or_run_backtest(weights: dict[str, float], top_n: int = 10, years: int = 5,
                         force_refresh: bool = False) -> dict:
    """
    Cache-aware wrapper around factor_backtest.run_factor_backtest().
    Two users (or repeated calls) with the identical normalized weight
    config, top_n, and years reuse the same cached result.
    """
    normalized = user_strategy.normalize_weights(weights)
    key = _cache_key(normalized, top_n, years)

    if not force_refresh:
        cached = db.get_strategy_backtest(key)
        if cached is not None:
            cached = dict(cached)
            cached["cache_hit"] = True
            cached["strategy_hash"] = strategy_hash(normalized)
            return cached

    result = factor_backtest.run_factor_backtest(
        custom_weights=normalized, top_n=top_n, years=years
    )
    result["cache_hit"] = False
    result["strategy_hash"] = strategy_hash(normalized)

    if not result.get("error"):
        db.set_strategy_backtest(key, result)

    return result


def invalidate_all() -> None:
    """Call after a bulk SEC/factor-score refresh materially changes data."""
    db.invalidate_strategy_cache(DATA_VERSION)
