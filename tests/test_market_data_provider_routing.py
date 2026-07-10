from unittest.mock import patch

from codes.data import market_data


def test_market_fear_does_not_request_vix_from_generic_tiingo_path():
    with patch.object(market_data.api_fetcher, "get_price") as price, \
         patch.object(market_data.api_fetcher, "get_price_history") as history:
        result = market_data.get_market_fear_inputs()

    assert result == {"vix": None, "vixeq": None, "spread_history": []}
    price.assert_not_called()
    history.assert_not_called()
