from types import SimpleNamespace

import pytest

from codes.data.providers import registry


def test_disabled_registered_market_fails_before_cache_use(monkeypatch):
    monkeypatch.setattr(registry, "is_market_enabled", lambda _code: False)

    with pytest.raises(ValueError, match="Canada market support is disabled"):
        registry.require_symbol_market_enabled("SHOP.TO")


def test_new_market_registration_supplies_scoring_facts(monkeypatch):
    provider = object()
    registration = registry.MarketProviderRegistration(
        market_code="GB",
        market_name="United Kingdom",
        symbol_matcher=lambda symbol: symbol.endswith(".L"),
        provider_factory=lambda: provider,
        scoring_builder=lambda selected, symbol: SimpleNamespace(
            can_score=selected is provider and symbol == "VOD.L",
            sec_facts={"source_market": "GB", "name": "Vodafone"},
            quality_report=SimpleNamespace(issues=()),
        ),
        projection_builder=lambda _symbol: True,
    )
    monkeypatch.setattr(registry, "MARKET_PROVIDERS", registry.MARKET_PROVIDERS + (registration,))
    monkeypatch.setattr(registry, "is_market_enabled", lambda code: code == "GB")

    assert registry.provider_for_symbol("VOD.L") is provider
    assert registry.scoring_facts_for_symbol("VOD.L") == {
        "source_market": "GB",
        "name": "Vodafone",
    }


def test_unrecognized_symbol_keeps_us_fallback(monkeypatch):
    monkeypatch.setattr(registry, "is_market_enabled", lambda _code: False)

    registry.require_symbol_market_enabled("AAPL")
    assert registry.provider_for_symbol("AAPL") is None
    assert registry.scoring_facts_for_symbol("AAPL") is None
