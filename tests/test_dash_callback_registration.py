from unittest.mock import patch


def test_dash_global_callbacks_are_attached_to_app():
    with patch("codes.data.db.init_db", return_value=None), \
         patch("codes.data.sec_data.get_ticker_map", return_value={}), \
         patch("codes.engine.universe.get_universe", return_value=[]), \
         patch("codes.engine.screener.load_cached_only", return_value=[]):
        import codes.app as app

    callback_keys = set(app.app.callback_map)

    assert any("screener-table-container.children" in key for key in callback_keys)
    assert any("screener-country-store.data" in key for key in callback_keys)
    assert len(callback_keys) > 20
