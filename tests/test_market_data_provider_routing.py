from codes.data import market_data


def test_market_fear_does_not_request_vix_from_generic_tiingo_path():
    assert market_data.get_market_fear_inputs() == {
        "vix": None,
        "vixeq": None,
        "spread_history": [],
    }
