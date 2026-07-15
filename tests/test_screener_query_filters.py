from codes.app_modules.tabs.screener import apply_sector_filter_from_url, _sector_from_search


def test_sector_filter_is_read_from_url_query():
    assert _sector_from_search("?tab=screener&sector=Surety%20Insurance") == "Surety Insurance"


def test_sector_filter_handles_missing_and_bounded_values():
    assert _sector_from_search(None) == ""
    assert len(_sector_from_search("?sector=" + "x" * 200)) == 100


def test_initial_url_hydrates_sector_dropdown():
    assert apply_sector_filter_from_url("/", "?tab=screener&sector=Surety%20Insurance") == "Surety Insurance"
