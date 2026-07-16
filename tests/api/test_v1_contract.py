"""Executable contract checks for ISSUE_060's public API v1."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import get_type_hints

import flask
import pytest

from codes.api import api_v1, v1
from codes.api import schemas as typed_schemas

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def contract() -> dict:
    return json.loads((ROOT / "openapi.yaml").read_text(encoding="utf-8"))


@pytest.fixture
def client() -> flask.testing.FlaskClient:
    app = flask.Flask(__name__)
    app.secret_key = "issue-060-test"

    @app.before_request
    def request_context() -> None:
        flask.g.request_id = "req-contract-test"

    app.register_blueprint(api_v1)
    return app.test_client()


def _resolve(contract: dict, schema: dict) -> dict:
    if "$ref" not in schema:
        return schema
    current = contract
    for segment in schema["$ref"].removeprefix("#/").split("/"):
        current = current[segment]
    return current


def _assert_schema(contract: dict, schema: dict, value: object) -> None:
    schema = _resolve(contract, schema)
    for member in schema.get("allOf", []):
        _assert_schema(contract, member, value)
    expected = _expected_type(schema.get("type"), value)
    if value is None:
        return
    if expected == "object":
        assert isinstance(value, dict)
        assert set(schema.get("required", [])) <= set(value)
        properties = schema.get("properties", {})
        if schema.get("additionalProperties") is False:
            assert set(value) <= set(properties)
        for name, child in properties.items():
            if name in value and child:
                _assert_schema(contract, child, value[name])
    elif expected == "array":
        assert isinstance(value, list)
        for item in value:
            _assert_schema(contract, schema.get("items", {}), item)
    else:
        _assert_primitive(expected, value)
    if "const" in schema:
        assert value == schema["const"]


def _expected_type(expected: str | list[str] | None, value: object) -> str | None:
    if not isinstance(expected, list):
        return expected
    if value is None:
        assert "null" in expected
        return None
    return next(item for item in expected if item != "null")


def _assert_primitive(expected: str | None, value: object) -> None:
    checks = {
        "string": lambda item: isinstance(item, str),
        "integer": lambda item: isinstance(item, int) and not isinstance(item, bool),
        "number": lambda item: isinstance(item, (int, float)) and not isinstance(item, bool),
        "boolean": lambda item: isinstance(item, bool),
    }
    if expected in checks:
        assert checks[expected](value)


def _response_schema(contract: dict, path: str, status: int) -> dict:
    operation = contract["paths"][path]["get"]
    response = _resolve(contract, operation["responses"][str(status)])
    return response["content"]["application/json"]["schema"]


def test_every_public_operation_is_versioned_and_uniquely_named(contract: dict) -> None:
    assert contract["openapi"] == "3.1.0"
    assert contract["servers"] == [{"url": "/api/v1"}]
    operation_ids = [item["get"]["operationId"] for item in contract["paths"].values()]
    assert len(operation_ids) == len(set(operation_ids))


def test_blueprint_routes_and_spec_paths_are_identical(contract: dict) -> None:
    app = flask.Flask(__name__)
    app.register_blueprint(api_v1)
    actual = {
        re.sub(r"<([^:>]+:)?([^>]+)>", r"{\2}", rule.rule.removeprefix("/api/v1"))
        for rule in app.url_map.iter_rules()
        if rule.endpoint.startswith("api_v1.")
    }
    assert actual == set(contract["paths"])


def test_analysis_response_matches_documented_schema(client, contract, monkeypatch) -> None:
    monkeypatch.setattr(
        v1.stock_analysis,
        "get_cached_analysis",
        lambda _symbol: {
            "symbol": "AAPL",
            "name": "Apple Inc.",
            "sector": "Technology",
            "price": 201.5,
            "market_cap": 3_000_000,
            "analysis_version": "2026.07",
            "generated_at": "2026-07-16T20:00:00+00:00",
            "enhanced": {"composite_score": 82.5, "verdict": "ATTRACTIVE"},
            "provider_secret": "must-not-leak",
        },
    )
    response = client.get("/api/v1/analysis/AAPL")
    assert response.status_code == 200
    payload = response.get_json()
    _assert_schema(contract, _response_schema(contract, "/analysis/{symbol}", 200), payload)
    assert "provider_secret" not in payload["data"]


def test_screener_response_is_paginated_and_contract_checked(client, contract, monkeypatch) -> None:
    monkeypatch.setattr(
        v1.screener_service,
        "get_results",
        lambda: [
            {"symbol": symbol, "composite_score": score, "analyzed": True}
            for symbol, score in (("AAPL", 90), ("MSFT", 80), ("NVDA", 70))
        ],
    )
    response = client.get("/api/v1/screener?page=2&page_size=2")
    payload = response.get_json()
    _assert_schema(contract, _response_schema(contract, "/screener", 200), payload)
    assert [item["symbol"] for item in payload["data"]] == ["NVDA"]
    assert payload["pagination"] == {
        "page": 2,
        "page_size": 2,
        "total_items": 3,
        "total_pages": 2,
    }


def test_authenticated_contracts_and_safe_error_envelope(client, contract, monkeypatch) -> None:
    monkeypatch.setattr(v1, "_authenticated_user", lambda: None)
    response = client.get("/api/v1/account")
    payload = response.get_json()
    assert response.status_code == 401
    _assert_schema(contract, _response_schema(contract, "/account", 401), payload)
    assert payload["error"] == {
        "code": "unauthorized",
        "message": "Authentication is required.",
    }


def test_authenticated_success_responses_match_contract(client, contract, monkeypatch) -> None:
    monkeypatch.setattr(v1, "_authenticated_user", lambda: "user-1")
    monkeypatch.setattr(v1.account_service, "display_name", lambda _user: "Ada")
    monkeypatch.setattr(v1.account_service, "auth_provider", lambda: "session")
    monkeypatch.setattr(
        v1.account_service,
        "get_settings",
        lambda _user: {
            "appearance": {"theme": "dark"},
            "notifications": {"product_updates": True},
            "api_keys": ["must-not-leak"],
        },
    )
    monkeypatch.setattr(
        v1.account_service,
        "portfolio_summaries",
        lambda _user: [{"name": "Core", "holdings": 3}],
    )
    monkeypatch.setattr(
        v1.account_service,
        "subscription_summary",
        lambda _user: {
            "plan": "premium",
            "status": "active",
            "trial_usage": 2,
            "paid": True,
            "billing_url": "/unversioned-must-not-leak",
        },
    )
    cases = (
        ("/api/v1/account", "/account"),
        ("/api/v1/portfolios", "/portfolios"),
        ("/api/v1/billing", "/billing"),
    )
    for url, path in cases:
        response = client.get(url)
        assert response.status_code == 200
        _assert_schema(contract, _response_schema(contract, path, 200), response.get_json())
    account = client.get("/api/v1/account").get_json()["data"]
    billing = client.get("/api/v1/billing").get_json()["data"]
    assert "api_keys" not in account["settings"]
    assert "billing_url" not in billing


def test_typed_transport_schemas_track_openapi_fields(contract: dict) -> None:
    pairs = (
        (typed_schemas.AnalysisResource, "Analysis"),
        (typed_schemas.ScreenerResource, "ScreenerItem"),
        (typed_schemas.PortfolioSummary, "PortfolioSummary"),
        (typed_schemas.AppearanceSettings, "AppearanceSettings"),
        (typed_schemas.NotificationSettings, "NotificationSettings"),
        (typed_schemas.AccountSettings, "AccountSettings"),
        (typed_schemas.AccountResource, "Account"),
        (typed_schemas.BillingResource, "Billing"),
    )
    for python_schema, openapi_name in pairs:
        typed_fields = set(get_type_hints(python_schema))
        contract_fields = set(contract["components"]["schemas"][openapi_name]["properties"])
        assert typed_fields == contract_fields


def test_openapi_document_is_served_from_the_versioned_api(client) -> None:
    response = client.get("/api/v1/openapi.yaml")
    assert response.status_code == 200
    assert response.mimetype == "application/yaml"
    assert json.loads(response.get_data(as_text=True))["info"]["version"] == "1.0.0"


def test_health_response_matches_documented_schema(client, contract) -> None:
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    _assert_schema(contract, _response_schema(contract, "/health", 200), response.get_json())
