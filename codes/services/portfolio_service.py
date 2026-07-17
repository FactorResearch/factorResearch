"""Application boundary for user-owned portfolio workflows.

Presentation and API adapters call this module instead of importing the legacy
portfolio engine or persistence layer.  The legacy module remains an internal
implementation detail until its repositories are split into narrower ports.
"""

from __future__ import annotations

from codes import portfolio as _portfolio
from codes.data import db as _db

MAX_HOLDINGS = _portfolio.MAX_HOLDINGS
MIN_SHARES = _portfolio.MIN_SHARES


def list_portfolios(user_id: str) -> list[str]:
    return _portfolio.list_portfolios(user_id)


def create_portfolio(user_id: str, name: str) -> dict:
    return _portfolio.create_portfolio(user_id, name)


def load_portfolio(user_id: str, name: str) -> dict | None:
    return _portfolio.load_portfolio(user_id, name)


def save_portfolio(user_id: str, portfolio: dict, *, expected_version: int | None = None) -> None:
    _portfolio.save_portfolio(user_id, portfolio, expected_version=expected_version)


def delete_portfolio(user_id: str, name: str) -> None:
    _portfolio.delete_portfolio(user_id, name)


def list_portfolio_changes(user_id: str, since: str | None = None) -> list[dict]:
    return _portfolio.list_portfolio_changes(user_id, since)


def restore_portfolio(user_id: str, portfolio_id: str, *, expected_version: int) -> dict:
    return _portfolio.restore_portfolio(user_id, portfolio_id, expected_version=expected_version)


def add_holding(
    user_id: str,
    portfolio_name: str,
    symbol: str,
    shares: float,
    price: float,
    company: str = "",
) -> tuple[dict, str | None]:
    return _portfolio.add_holding(user_id, portfolio_name, symbol, shares, price, company)


def remove_holding(user_id: str, portfolio_name: str, symbol: str):
    return _portfolio.remove_holding(user_id, portfolio_name, symbol)


def invalidate_simulation_cache(user_id: str, portfolio_name: str) -> None:
    _portfolio.invalidate_simulation_cache(user_id, portfolio_name)


def analysis_entries(symbols) -> dict:
    """Return cached research needed to render portfolio summaries."""
    return _db.get_analysis_entries(symbols)


def analyze_weak_links(portfolio: dict, backtest: dict | None = None) -> dict:
    return _portfolio.analyze_weak_links(portfolio, backtest)


def run_simulation(user_id: str, portfolio_name: str) -> dict:
    return _portfolio.run_simulation(user_id, portfolio_name)


def compare_portfolios(user_id: str, first: str, second: str) -> dict:
    return _portfolio.compare_portfolios(user_id, first, second)


def delete_all_user_data(user_id: str) -> dict:
    return _portfolio.delete_all_user_data(user_id)
