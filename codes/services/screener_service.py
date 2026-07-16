"""Application boundary for screener queries and analysis projections."""

from __future__ import annotations

from codes.data import db as _db
from codes.data.us_indices import US_INDEX_DEFINITIONS, row_matches_any_index
from codes.engine import screener as _screener
from codes.engine.scorer import verdict_for_score


def get_screener_results() -> list[dict]:
    return _screener.get_screener_results()


def get_results() -> list[dict]:
    """Concise alias for API adapters."""
    return get_screener_results()


def get_progress() -> dict:
    return _screener.get_progress()


def get_analysis(symbol: str) -> dict | None:
    return _db.get_analysis(symbol)


def update_from_analysis(symbol: str, result: dict) -> None:
    _screener.update_stock_after_analysis(symbol, result)


def update_stock_after_analysis(symbol: str, result: dict) -> None:
    """Compatibility name kept at the service boundary during migration."""
    update_from_analysis(symbol, result)


def load_cached_only() -> list[dict]:
    return _screener.load_cached_only()
