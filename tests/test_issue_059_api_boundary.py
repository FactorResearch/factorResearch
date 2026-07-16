"""Acceptance tests for ISSUE_059's initial API-first service boundary."""

from __future__ import annotations

import ast
from pathlib import Path

from codes.services import account_service, portfolio_service, screener_service, stock_analysis


ROOT = Path(__file__).resolve().parents[1]
ADAPTERS = (
    "codes/app_modules/tabs/analyze.py",
    "codes/app_modules/tabs/portfolio.py",
    "codes/app_modules/tabs/pricing.py",
    "codes/app_modules/tabs/profile.py",
    "codes/app_modules/tabs/screener.py",
    "codes/routes/analyze.py",
    "codes/routes/charts.py",
)
FORBIDDEN = ("codes.billing", "codes.data", "codes.engine", "codes.portfolio")


def _imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    result: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            result.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            result.add(node.module)
    return result


def test_product_delivery_adapters_do_not_bypass_services() -> None:
    for relative in ADAPTERS:
        direct = {
            imported
            for imported in _imports(ROOT / relative)
            if imported.startswith(FORBIDDEN)
        }
        assert not direct, f"{relative} bypasses services: {sorted(direct)}"


def test_analyze_boundary_owns_cached_analysis(monkeypatch) -> None:
    monkeypatch.setattr(stock_analysis.db, "get_analysis", lambda symbol: {"symbol": symbol})
    assert stock_analysis.get_cached_analysis("aapl") == {"symbol": "AAPL"}


def test_portfolio_boundary_owns_research_lookup(monkeypatch) -> None:
    monkeypatch.setattr(
        portfolio_service._db,
        "get_analysis_entries",
        lambda symbols: {"symbols": list(symbols)},
    )
    assert portfolio_service.analysis_entries(["AAPL"]) == {"symbols": ["AAPL"]}


def test_screener_boundary_owns_projection_update(monkeypatch) -> None:
    seen = []
    monkeypatch.setattr(
        screener_service._screener,
        "update_stock_after_analysis",
        lambda symbol, result: seen.append((symbol, result)),
    )
    screener_service.update_from_analysis("AAPL", {"score": 90})
    assert seen == [("AAPL", {"score": 90})]


def test_account_boundary_composes_profile_summary(monkeypatch) -> None:
    monkeypatch.setattr(account_service.portfolio_service, "list_portfolios", lambda _uid: ["Core"])
    monkeypatch.setattr(
        account_service.portfolio_service,
        "load_portfolio",
        lambda _uid, _name: {"holdings": {"AAPL": {}, "MSFT": {}}},
    )
    assert account_service.portfolio_summaries("user-1") == [
        {"name": "Core", "holdings": 2}
    ]


def test_direct_client_database_access_is_explicitly_prohibited() -> None:
    policy = (ROOT / "docs/api-first-boundary.md").read_text(encoding="utf-8")
    normalized = " ".join(policy.split())
    assert "must never connect directly to PostgreSQL" in normalized
    assert "New UI callbacks and routes must use an existing service boundary" in normalized
