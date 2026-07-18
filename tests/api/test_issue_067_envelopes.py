from __future__ import annotations

import flask

from codes.api import api_v1, contracts, v1


def _client() -> flask.testing.FlaskClient:
    app = flask.Flask(__name__)
    app.secret_key = "issue-067-test"

    @app.before_request
    def request_context() -> None:
        flask.g.request_id = "req-issue-067"

    app.register_blueprint(api_v1)
    return app.test_client()


def test_error_envelope_has_request_correlation_and_safe_details() -> None:
    payload = contracts.error_response(
        "dependency_unavailable",
        None,
        "req-issue-067",
        details={"section": "history"},
    )
    assert payload == {
        "error": {
            "code": "dependency_unavailable",
            "message": "A required service is temporarily unavailable.",
            "retryable": True,
            "details": {"section": "history"},
        },
        "meta": {"api_version": "v1", "request_id": "req-issue-067"},
    }


def test_cursor_round_trip_is_opaque_and_bounded() -> None:
    cursor = contracts.encode_cursor(25)
    assert contracts.decode_cursor(cursor) == 25
    try:
        contracts.decode_cursor("not-a-cursor")
    except ValueError as error:
        assert str(error) == "cursor is invalid"
    else:
        raise AssertionError("malformed cursor must be rejected")


def test_screener_cursor_response_is_bounded_and_has_next_cursor(monkeypatch) -> None:
    monkeypatch.setattr(
        v1.screener_service,
        "get_results",
        lambda: [{"symbol": f"S{index:02d}", "composite_score": index} for index in range(5)],
    )
    client = _client()
    response = client.get("/api/v1/screener?cursor=Mg&page_size=2")
    assert response.status_code == 200
    payload = response.get_json()
    assert len(payload["data"]) == 2
    assert payload["pagination"]["next_cursor"] == contracts.encode_cursor(4)


def test_partial_data_response_preserves_successful_sections() -> None:
    payload = contracts.partial_data_response(
        {"history": [1, 2]},
        "req-issue-067",
        [{"code": "dependency_unavailable", "message": "Unavailable", "retryable": True}],
    )
    assert payload["partial"] is True
    assert payload["data"] == {"history": [1, 2]}
