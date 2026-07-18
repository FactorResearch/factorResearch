from __future__ import annotations

from codes.services import company_search


def _loader() -> list[dict]:
    return [
        {"symbol": "MSFT", "name": "Microsoft Corporation"},
        {"symbol": "AAPL", "name": "Apple Inc."},
        {"symbol": "BRK.B", "name": "Berkshire Hathaway Inc."},
        {"symbol": "APP", "name": "Applovin Corporation"},
    ]


def test_exact_ticker_precedes_all_other_matches():
    company_search.clear_company_search_cache()

    results = company_search.search_companies("aapl", loader=_loader)

    assert results[0].as_dict() == {"symbol": "AAPL", "name": "Apple Inc."}


def test_company_name_suffix_and_word_prefix_are_normalized():
    company_search.clear_company_search_cache()

    results = company_search.search_companies("berkshire", loader=_loader)

    assert results[0].symbol == "BRK.B"
    assert results[0].name == "Berkshire Hathaway Inc."


def test_partial_name_returns_supported_matches_with_display_metadata():
    company_search.clear_company_search_cache()

    results = company_search.search_companies("appl", loader=_loader)

    assert {item.symbol for item in results} == {"AAPL", "APP"}
    assert all(item.name for item in results)


def test_empty_or_unmatched_query_returns_no_suggestions():
    company_search.clear_company_search_cache()

    assert company_search.search_companies("") == []
    assert company_search.search_companies("zzzz", loader=_loader) == []
