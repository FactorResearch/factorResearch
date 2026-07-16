from unittest.mock import patch

from codes.app import server


HEADERS = {"Origin": "http://localhost"}


def test_account_delete_rejects_unauthenticated_request_before_data_access():
    with patch("codes.auth.get_authenticated_user_id", return_value=None), \
         patch("codes.app.account_service.delete_account_data") as delete:
        response = server.test_client().post("/account/delete", headers=HEADERS)

    assert response.status_code == 401
    delete.assert_not_called()


def test_account_delete_preserves_authenticated_erasure_flow():
    with patch("codes.auth.get_authenticated_user_id", return_value="user-1"), \
         patch("codes.app.account_service.delete_account_data", return_value={
             "portfolios": 1,
             "database_records": {"subscriptions": 1},
             "analytics_events": 2,
             "custom_snapshots": 3,
         }), \
         patch("codes.app.invalidate_portfolio_cache"), \
         patch("codes.app.clear_rate_limits_for_user"):
        response = server.test_client().post("/account/delete", headers=HEADERS)

    assert response.status_code == 200
    assert response.get_json() == {
        "analytics_events": 2,
        "custom_snapshots": 3,
        "database_records": {"subscriptions": 1},
        "portfolios": 1,
    }
