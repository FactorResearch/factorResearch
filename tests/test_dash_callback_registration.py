import json
from unittest.mock import patch


def test_dash_registers_global_callbacks_on_first_request():
    with patch("codes.data.db.init_db", return_value=None), \
         patch("codes.data.sec_data.get_ticker_map", return_value={}), \
         patch("codes.engine.universe.get_universe", return_value=[]), \
         patch("codes.engine.screener.load_cached_only", return_value=[]), \
         patch("codes.engine.screener.get_screener_results", return_value=[]), \
         patch("codes.engine.screener.get_progress", return_value={
             "running": False, "total": 0, "done": 0, "current": "",
         }):
        import codes.app as app_module

        client = app_module.server.test_client()
        headers = {"Origin": "http://localhost", "Referer": "http://localhost/"}
        index_response = client.get("/", headers=headers)
        canada_route_response = client.get("/screener/ca", headers=headers)
        layout_response = client.get("/_dash-layout", headers=headers)
        dependencies_response = client.get("/_dash-dependencies", headers=headers)

        assert index_response.status_code == 200
        assert canada_route_response.status_code == 200
        assert layout_response.status_code == 200
        assert dependencies_response.status_code == 200

        dependencies = json.loads(dependencies_response.data)
        outputs = {dependency["output"] for dependency in dependencies}
        assert any("screener-table-container.children" in output for output in outputs)
        assert not any("screener-market-link" in output and "href" in output for output in outputs)
        assert "screener-country-tabs-container.children" not in outputs
        assert len(outputs) > 20

        table_dependency = next(
            dependency for dependency in dependencies
            if "screener-table-container.children" in dependency["output"]
        )
        assert {"id": "url", "property": "pathname"} in table_dependency["inputs"]
        callback_response = client.post(
            "/_dash-update-component",
            headers=headers,
            json={
                "output": table_dependency["output"],
                "outputs": [
                    {"id": "screener-table-container", "property": "children"},
                    {"id": "sector-filter", "property": "options"},
                    {"id": "screener-page-store", "property": "data"},
                ],
                "inputs": [
                    {"id": "screener-ready-store", "property": "data", "value": 0},
                    {"id": "url", "property": "pathname", "value": "/screener/ca"},
                    {"id": "page-load-interval", "property": "n_intervals", "value": 1},
                    {"id": "index-filter", "property": "data", "value": []},
                    {"id": "sector-filter", "property": "value", "value": ""},
                    {
                        "id": "screener-sort-store",
                        "property": "data",
                        "value": {"col": "composite_score", "asc": False},
                    },
                    {"id": "screener-page-store", "property": "data", "value": 1},
                ],
                "state": [
                    {"id": "screener-viewed-store", "property": "data", "value": []},
                ],
                "changedPropIds": ["url.pathname"],
            },
        )

        assert callback_response.status_code == 200
        assert "Loading screener data" not in callback_response.get_data(as_text=True)
        assert "Screener is waiting for cached" in callback_response.get_data(as_text=True)
