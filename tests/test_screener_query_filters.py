from codes.app_modules.tabs.screener import _sector_from_search


def test_sector_filter_is_read_from_url_query():
    assert _sector_from_search("?tab=screener&sector=Surety%20Insurance") == "Surety Insurance"


def test_sector_filter_handles_missing_and_bounded_values():
    assert _sector_from_search(None) == ""
    assert len(_sector_from_search("?sector=" + "x" * 200)) == 100
