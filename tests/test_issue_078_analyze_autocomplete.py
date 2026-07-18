from __future__ import annotations

from unittest.mock import patch

from codes.app_modules.layout import build_layout
from codes.app_modules.tabs.analyze import update_company_suggestions
from codes.services.company_search import CompanySuggestion


def test_suggestion_callback_renders_ticker_and_company_name_without_analysis():
    suggestion = CompanySuggestion("AAPL", "Apple Inc.", (0, 4, "AAPL"))
    with patch("codes.app_modules.tabs.analyze.company_search.search_companies", return_value=[suggestion]):
        children, status, query = update_company_suggestions("apple", None)

    assert status == "1 company suggestions available."
    assert query == "apple"
    rendered = children[0].to_plotly_json()
    assert rendered["props"]["id"] == {"type": "ticker-suggestion", "symbol": "AAPL"}
    assert rendered["props"]["role"] == "option"


def test_suggestion_failure_keeps_manual_search_available():
    with patch(
        "codes.app_modules.tabs.analyze.company_search.search_companies",
        side_effect=TimeoutError("search timeout"),
    ):
        children, status, _query = update_company_suggestions("apple", None)

    assert "temporarily unavailable" in status
    assert "temporarily unavailable" in children[0].to_plotly_json()["props"]["children"]


def test_analyze_layout_exposes_combobox_and_live_suggestion_regions():
    layout = build_layout().to_plotly_json()
    serialized = str(layout)

    assert "ticker-suggestions" in serialized
    assert "ticker-search-status" in serialized
    assert "ticker-selected-symbol" in serialized
