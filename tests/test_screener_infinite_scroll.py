"""
Tests for the infinite-scroll screener table (replaces server-side pagination).

Verifies:
  1. render_screener_table renders only `visible_count` rows (default 50)
     when more results are available.
  2. The scroll sentinel reports "Loading more…" while rows remain.
  3. When visible_count >= total results, all rows are rendered and the
     sentinel reports "Showing all".
  4. Changing the sector filter or sort resets visible_count back to 50.
"""

import sys
import os
from unittest.mock import patch, MagicMock

_ROOT = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, _ROOT)
sys.path.insert(0, os.path.join(_ROOT, "codes"))

# `codes.app` runs startup() at import time (ticker map, universe, screener
# load) which would hit the network / filesystem. Patch those before import.
with patch("codes.data.sec_data.get_ticker_map", return_value={}), \
     patch("codes.engine.universe.get_universe", return_value=[]), \
     patch("codes.engine.screener.load_cached_only", return_value=[]):
    from codes import app as graham_app


def _make_row(symbol, composite_score):
    return {
        "symbol": symbol, "name": f"{symbol} Inc.", "sector": "Technology",
        "graham_score": 50, "graham_max": 100, "graham_pct": 50.0,
        "quality_score": 50, "quality_max": 100, "quality_pct": 50.0,
        "composite_score": composite_score, "verdict": "PENDING",
        "verdict_label": "pending", "roe": None, "op_margin": None,
        "eps_years": 0, "div_years": 0, "graham_number": None,
        "buffett_iv": None, "market_cap": None, "price": None,
        "analyzed": False, "updated_at": None,
    }


def _results(n):
    return [_make_row(f"SYM{i:04d}", 100 - i) for i in range(n)]


def _call_render(visible_count, sector_filter="", sort_state=None,
                  results=None, triggered_id="screener-visible-count"):
    results = results if results is not None else _results(120)
    sort_state = sort_state or {"col": "composite_score", "asc": False}

    from dash._callback_context import context_value, AttributeDict
    context_value.set(AttributeDict(**{
        "response": {}, "request": None,
        "triggered_inputs": [{"prop_id": f"{triggered_id}.data", "value": None}],
    }))

    with patch.object(graham_app.screener, "get_screener_results", return_value=results), \
         patch.object(graham_app.screener, "get_progress",
                       return_value={"running": False, "total": len(results),
                                      "done": len(results), "failed": 0, "current": ""}), \
         patch.object(graham_app, "_get_portfolio_symbols", return_value={}), \
         patch.object(graham_app, "_last_screener_state", None):
        return graham_app.render_screener_table(
            ready=1, n_load=1, selected_indices=[], sector_filter=sector_filter,
            sort_state=sort_state, visible_count=visible_count, viewed_data=[],
        )


def _row_count(container):
    table = container.children[0]
    tbody = table.children[1]
    return len(tbody.children)


def _sentinel_text(container):
    return container.children[-1].children


def test_renders_only_visible_count_rows():
    container, _ = _call_render(visible_count=50)
    assert _row_count(container) == 50


def test_sentinel_shows_loading_more_when_rows_remain():
    container, _ = _call_render(visible_count=50)
    assert "Loading more" in _sentinel_text(container)
    assert "50" in _sentinel_text(container)
    assert "120" in _sentinel_text(container)


def test_renders_all_rows_when_visible_count_covers_total():
    container, _ = _call_render(visible_count=200)
    assert _row_count(container) == 120


def test_sentinel_shows_showing_all_when_no_rows_remain():
    container, _ = _call_render(visible_count=200)
    assert "Showing all" in _sentinel_text(container)
    assert "120" in _sentinel_text(container)


def test_sector_filter_change_resets_visible_count_to_50():
    container, _ = _call_render(
        visible_count=150, sector_filter="Technology",
        triggered_id="sector-filter",
    )
    assert _row_count(container) == 50


def test_sort_change_resets_visible_count_to_50():
    container, _ = _call_render(
        visible_count=150,
        sort_state={"col": "symbol", "asc": True},
        triggered_id="screener-sort-store",
    )
    assert _row_count(container) == 50


def test_no_pagination_controls_present():
    """Pagination has been fully replaced by the infinite-scroll sentinel."""
    container, _ = _call_render(visible_count=50)
    assert not hasattr(graham_app, "handle_pagination")
    # sentinel id should exist, pagination-controls className should not
    sentinel = container.children[-1]
    assert sentinel.id == "screener-scroll-sentinel"
