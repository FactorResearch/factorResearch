from types import SimpleNamespace
from unittest.mock import patch
import re

from codes.app_modules.tabs import analyze as analyze_tab


def test_dated_direct_link_ticker_drives_analysis_when_input_is_empty():
    result = {"name": "Apple Inc.", "cache_hit": True, "cache_source": "database"}

    with patch.object(analyze_tab.dash, "ctx", SimpleNamespace(triggered_id="analyze-btn")), \
         patch.object(analyze_tab, "check_rate_limit"), \
         patch.object(analyze_tab, "get_user_id", return_value=None), \
         patch.object(
             analyze_tab.permissions,
             "can_access_feature",
             return_value=SimpleNamespace(allowed=True, remaining=None),
         ), \
         patch.object(analyze_tab.product_analytics, "track_event"), \
         patch.object(analyze_tab, "analyze_stock", return_value=result) as analyze_stock, \
         patch.object(analyze_tab, "_build_analysis_content", return_value=["content"]), \
         patch.object(analyze_tab.screener, "update_stock_after_analysis"):
        output = analyze_tab.run_analysis(
            None,
            None,
            "/AAPL/analyze/20260711",
            None,
            [],
        )

    analyze_stock.assert_called_once_with("AAPL")
    assert re.fullmatch(r"/AAPL/analyze/\d{8}", output[0])
    assert output[1] == ["content"]
    assert output[6] == "AAPL"
    assert output[8] == "AAPL"
