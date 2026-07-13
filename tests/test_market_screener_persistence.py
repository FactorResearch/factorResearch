from unittest.mock import MagicMock, patch

from codes.data.providers import registry
from codes.engine import screener


def _canada_row():
    return {
        "market_code": "CA",
        "symbol": "SHOP.TO",
        "name": "Shopify Inc.",
        "sector": None,
        "currency": "CAD",
        "graham_score": 25,
        "graham_max": 105,
        "graham_pct": 23.8,
        "quality_score": 55,
        "quality_max": 100,
        "quality_pct": 55.0,
        "composite_score": 38.5,
        "verdict": "PENDING",
        "verdict_label": "pending",
        "roe": 24.0,
        "op_margin": 16.0,
        "eps_years": 5,
        "div_years": 0,
        "graham_number": 42.0,
        "buffett_iv": None,
        "market_cap": None,
        "price": None,
        "analyzed": True,
        "score_scope": "fundamental",
        "projection_version": "fundamental-v1",
        "data_confidence": "regulatory_verified",
        "updated_at": "2026-07-13T12:00:00",
    }


def test_load_cached_only_loads_canada_without_us_universe():
    screener._progress["results"] = []
    with patch("codes.engine.screener.universe.get_universe", return_value=[]), \
         patch("codes.data.providers.registry.configured_market_codes", return_value=["US", "CA"]), \
         patch(
             "codes.data.providers.registry.backfill_enabled_market_screener_projections",
             return_value={"created": 0, "failed": 0},
         ), \
         patch("codes.engine.screener.db.get_market_screener_rows", return_value=[_canada_row()]), \
         patch("codes.engine.screener.db.count", return_value=0), \
         patch("codes.engine.screener._sync_progress_to_redis"):
        rows = screener.load_cached_only()

    assert len(rows) == 1
    assert rows[0]["market_code"] == "CA"
    assert rows[0]["symbol"] == "SHOP.TO"
    assert rows[0]["sector"] == "Unknown"
    assert rows[0]["data_confidence"] == "regulatory_verified"
    assert rows[0]["analyzed"] is True


def test_load_cached_only_keeps_same_symbol_separate_by_market():
    canada = {**_canada_row(), "symbol": "ABC"}
    screener._progress["results"] = []
    with patch("codes.engine.screener.universe.get_universe", return_value=["ABC"]), \
         patch("codes.engine.screener.sec_data.get_ticker_map", return_value={}), \
         patch("codes.engine.screener._enrich_from_analysis_cache", return_value=0), \
         patch("codes.engine.screener._enrich_from_db", return_value=0), \
         patch("codes.engine.screener.company_metadata.enrich_rows"), \
         patch("codes.data.providers.registry.configured_market_codes", return_value=["US", "CA"]), \
         patch(
             "codes.data.providers.registry.backfill_enabled_market_screener_projections",
             return_value={"created": 0, "failed": 0},
         ), \
         patch("codes.engine.screener.db.get_market_screener_rows", return_value=[canada]), \
         patch("codes.engine.screener.db.count", return_value=0), \
         patch("codes.engine.screener._sync_progress_to_redis"):
        rows = screener.load_cached_only()

    assert {(row["market_code"], row["symbol"]) for row in rows} == {
        ("US", "ABC"),
        ("CA", "ABC"),
    }


def test_backfill_requests_current_projection_version():
    builder = MagicMock(return_value=True)
    with patch.object(registry, "_enabled_markets", return_value={"US", "CA"}), \
         patch.dict(registry.MARKET_PROJECTION_BUILDERS, {"CA": builder}, clear=True), \
         patch.object(
             registry.db,
             "list_market_symbols_missing_screener",
             return_value=[{"market_code": "CA", "symbol": "SHOP.TO"}],
         ) as missing:
        stats = registry.backfill_enabled_market_screener_projections()

    assert stats == {"created": 1, "failed": 0}
    assert missing.call_args.args[2] == "fundamental-v1"
    builder.assert_called_once_with("SHOP.TO")
