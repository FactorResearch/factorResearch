"""
Tests for market_cap wiring: app.analyze_stock -> screener -> db.value_metrics.

Verifies:
  1. update_stock_after_analysis prefers top-level analysis_result["market_cap"]
     (live-price fallback) over graham.score()'s market_cap.
  2. Falls back to graham's market_cap when top-level key is absent (legacy
     cached analyses without the new key).
  3. db.upsert is called with the resolved market_cap.
  4. _enrich_from_analysis_cache applies the same precedence for cached
     analysis blobs (new key vs legacy graham-only key).
"""

import sys
import os
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from codes.engine import screener


def _make_analysis(symbol="AAPL", market_cap=None, graham_market_cap=None,
                    composite_score=65.0, price=150.0):
    return {
        "name": f"{symbol} Inc.", "sector": "Technology", "price": price,
        "market_cap": market_cap,
        "graham":    {"total_score": 60, "total_max": 100,
                      "graham_number": 120.0, "margin_of_safety": 20.0,
                      "market_cap": graham_market_cap},
        "quality":   {"total_score": 70, "total_max": 100},
        "buffett":   {"intrinsic_value": 180.0},
        "enhanced":  {"composite_score": composite_score, "verdict": "FAVORABLE",
                      "verdict_label": "favorable", "graham_pct": 60.0,
                      "quality_pct": 70.0},
        "composite": {},
    }


def _stub(symbol):
    return {
        "symbol": symbol, "name": symbol, "sector": "Unknown",
        "graham_score": 0, "graham_max": 100, "graham_pct": 0,
        "quality_score": 0, "quality_max": 100, "quality_pct": 0,
        "composite_score": 0, "verdict": "PENDING", "verdict_label": "pending",
        "roe": None, "op_margin": None, "eps_years": 0, "div_years": 0,
        "graham_number": None, "buffett_iv": None, "market_cap": None,
        "price": None, "analyzed": False,
    }


class TestUpdateStockAfterAnalysisMarketCap:
    def setup_method(self):
        screener._progress["results"] = [_stub("AAPL")]

    def test_prefers_top_level_market_cap(self):
        with patch("codes.engine.screener.db.upsert") as mock_upsert:
            screener.update_stock_after_analysis(
                "AAPL", _make_analysis(market_cap=2_500_000.0, graham_market_cap=1_000_000.0)
            )
        row = next(r for r in screener._progress["results"] if r["symbol"] == "AAPL")
        assert row["market_cap"] == 2_500_000.0
        mock_upsert.assert_called_once()
        assert mock_upsert.call_args.kwargs["market_cap"] == 2_500_000.0

    def test_falls_back_to_graham_market_cap_when_top_level_absent(self):
        with patch("codes.engine.screener.db.upsert") as mock_upsert:
            screener.update_stock_after_analysis(
                "AAPL", _make_analysis(market_cap=None, graham_market_cap=1_000_000.0)
            )
        row = next(r for r in screener._progress["results"] if r["symbol"] == "AAPL")
        assert row["market_cap"] == 1_000_000.0
        assert mock_upsert.call_args.kwargs["market_cap"] == 1_000_000.0

    def test_both_absent_gives_none(self):
        with patch("codes.engine.screener.db.upsert") as mock_upsert:
            screener.update_stock_after_analysis(
                "AAPL", _make_analysis(market_cap=None, graham_market_cap=None)
            )
        row = next(r for r in screener._progress["results"] if r["symbol"] == "AAPL")
        assert row["market_cap"] is None
        assert mock_upsert.call_args.kwargs["market_cap"] is None

    def test_db_upsert_receives_composite_and_verdict(self):
        with patch("codes.engine.screener.db.upsert") as mock_upsert:
            screener.update_stock_after_analysis(
                "AAPL", _make_analysis(market_cap=2_500_000.0)
            )
        kwargs = mock_upsert.call_args.kwargs
        assert kwargs["composite_score"] == 65.0
        assert kwargs["verdict"] == "FAVORABLE"
        assert kwargs["graham_number"] == 120.0
        assert kwargs["buffett_iv"] == 180.0


class TestEnrichFromAnalysisCacheMarketCap:
    def setup_method(self):
        screener._progress["results"] = [_stub("MSFT")]

    def test_uses_top_level_market_cap_when_present(self):
        cached = _make_analysis("MSFT", market_cap=3_000_000.0, graham_market_cap=900_000.0)
        with patch("codes.engine.screener.db.list_analysis_entries", return_value={
            "MSFT": {"data": cached, "updated_at": "2026-07-14"}
        }):
            screener._enrich_from_analysis_cache()
        row = next(r for r in screener._progress["results"] if r["symbol"] == "MSFT")
        assert row["market_cap"] == 3_000_000.0

    def test_falls_back_to_graham_market_cap_for_legacy_cache(self):
        """Legacy cached analyses lack the top-level 'market_cap' key entirely."""
        cached = _make_analysis("MSFT", market_cap=None, graham_market_cap=900_000.0)
        del cached["market_cap"]  # simulate pre-upgrade cached blob
        with patch("codes.engine.screener.db.list_analysis_entries", return_value={
            "MSFT": {"data": cached, "updated_at": "2026-07-14"}
        }):
            screener._enrich_from_analysis_cache()
        row = next(r for r in screener._progress["results"] if r["symbol"] == "MSFT")
        assert row["market_cap"] == 900_000.0

    def test_new_symbol_appended_with_market_cap(self):
        cached = _make_analysis("TSLA", market_cap=1_800_000.0)
        with patch("codes.engine.screener.db.list_analysis_entries", return_value={
            "TSLA": {"data": cached, "updated_at": "2026-07-14"}
        }):
            screener._enrich_from_analysis_cache()
        row = next(r for r in screener._progress["results"] if r["symbol"] == "TSLA")
        assert row["market_cap"] == 1_800_000.0


if __name__ == "__main__":
    import pytest as _pytest
    _pytest.main([__file__, "-v"])
