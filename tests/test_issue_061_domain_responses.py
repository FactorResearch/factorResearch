"""Acceptance coverage for ISSUE_061's platform-neutral response boundary."""

from __future__ import annotations

from codes.app_modules.analysis_ui import _build_analysis_content
from codes.domain.responses import (
    AnalysisResponse,
    CapabilityResponse,
    ErrorResponse,
    FactorResponse,
    JobResponse,
    PortfolioResponse,
    SubscriptionResponse,
    UserResponse,
)
from codes.services import analysis_jobs, screener_service

PRESENTATION_KEYS = {
    "badge",
    "class",
    "class_name",
    "classname",
    "color",
    "component",
    "css_class",
    "icon",
    "layout",
    "style",
    "verdict_label",
}


def _assert_semantic_only(value: object) -> None:
    if isinstance(value, dict):
        assert not ({key.lower() for key in value} & PRESENTATION_KEYS)
        for child in value.values():
            _assert_semantic_only(child)
    elif isinstance(value, list):
        for child in value:
            _assert_semantic_only(child)


def _analysis() -> dict:
    return {
        "symbol": "AAPL",
        "name": "Apple Inc.",
        "sector": "Technology",
        "price": 210.0,
        "market_cap": 3_000_000,
        "analysis_version": "2026.07",
        "generated_at": "2026-07-16T20:00:00+00:00",
        "graham": {
            "criteria": [],
            "total_score": 80,
            "total_max": 105,
            "grade": "A",
            "color": "green",
        },
        "quality": {"criteria": [], "total_score": 70, "total_max": 100},
        "momentum": {"criteria": [], "total_score": 65, "total_max": 100},
        "enhanced": {
            "composite_score": 78,
            "verdict": "HIGH_CONVICTION",
            "verdict_label": "high-conviction",
            "style": {"color": "green"},
        },
        "market_fear": {
            "regime": "ELEVATED",
            "color": "amber",
            "market_fear_score": 60,
            "error": None,
        },
        "secondary_status": "complete",
    }


def test_all_required_domain_response_models_are_immutable_dataclasses() -> None:
    response_types = (
        AnalysisResponse,
        FactorResponse,
        PortfolioResponse,
        JobResponse,
        UserResponse,
        SubscriptionResponse,
        ErrorResponse,
        CapabilityResponse,
    )
    assert all(response_type.__dataclass_params__.frozen for response_type in response_types)


def test_analysis_response_contains_semantics_and_removes_presentation_fields() -> None:
    response = AnalysisResponse.from_mapping(_analysis())
    payload = response.to_dict()
    _assert_semantic_only(payload)
    assert payload["verdict"] == "HIGH_CONVICTION"
    assert {factor["key"] for factor in payload["factors"]} >= {
        "graham",
        "quality",
        "momentum",
        "market_fear",
    }
    assert {item["key"] for item in payload["capabilities"]} == {
        "summary",
        "factor_details",
        "historical_charts",
        "secondary_signals",
    }


def test_web_renderer_consumes_the_same_analysis_response_as_api_serialization() -> None:
    response = AnalysisResponse.from_mapping(_analysis())
    rendered = str(_build_analysis_content(response))
    assert "Apple Inc." in rendered
    assert "High Conviction" in rendered
    assert response.to_dict()["company_name"] == "Apple Inc."


def test_screener_web_and_api_projections_share_the_same_response(monkeypatch) -> None:
    raw = {
        "symbol": "AAPL",
        "name": "Apple",
        "sector": "Technology",
        "composite_score": 75,
        "verdict": "HIGH_CONVICTION",
        "verdict_label": "high-conviction",
        "color": "green",
        "analyzed": True,
    }
    monkeypatch.setattr(screener_service._screener, "get_screener_results", lambda: [raw])
    domain_response = screener_service.get_result_responses()[0]
    web_data = screener_service.get_screener_results()[0]
    assert domain_response.to_dict().items() <= web_data.items()
    _assert_semantic_only(web_data)


def test_user_portfolio_subscription_error_job_and_capability_shapes_are_semantic(
    monkeypatch,
) -> None:
    values = [
        UserResponse.from_mapping(
            {
                "display_name": "Ada",
                "auth_provider": "session",
                "settings": {
                    "appearance": {"theme": "dark"},
                    "api_keys": ["secret"],
                },
            }
        ).to_dict(),
        PortfolioResponse.from_mapping({"name": "Core", "holdings": 4}).to_dict(),
        SubscriptionResponse.from_mapping(
            {"plan": "premium", "status": "active", "paid": True, "billing_url": "/billing"}
        ).to_dict(),
        ErrorResponse("not_found", "Resource not found.").to_dict(),
        CapabilityResponse("export", False, "PLAN_REQUIRED").to_dict(),
        JobResponse("AVAILABLE", 2, 1, 0).to_dict(),
    ]
    for value in values:
        _assert_semantic_only(value)
    assert "api_keys" not in values[0]["settings"]
    assert "billing_url" not in values[2]

    monkeypatch.setattr(
        analysis_jobs,
        "health",
        lambda: {"backend": "redis", "queued": 2, "processing": 1, "dead_letter": 0},
    )
    assert analysis_jobs.health_response().to_dict() == values[-1]
