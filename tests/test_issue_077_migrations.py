from __future__ import annotations

import json
from pathlib import Path
from typing import Mapping
from unittest.mock import Mock

import pytest

from codes.core import financial_math
from codes.core.ports import AnalyticsContext, TickerUniverseReader
from codes.data.providers.sec_universe import SecTickerUniverseAdapter
from codes.engine import scorer, universe
from codes.services import product_analytics, stock_analysis

ROOT = Path(__file__).resolve().parents[1]


class FakeAnalyticsContext:
    def __init__(self) -> None:
        self.opted_out = False

    def anonymous_id(self) -> str | None:
        return "anon-077"

    def authenticated_user_id(self) -> str | None:
        return "user-077"

    def page_path(self) -> str | None:
        return "/reference-migration"

    def is_opted_out(self) -> bool:
        return self.opted_out

    def set_opt_out(self, opt_out: bool) -> None:
        self.opted_out = opt_out


class FakeUniverseReader:
    def read_tickers(self) -> list[str]:
        return ["AAPL", "MSFT"]


def test_product_analytics_uses_injected_context_without_flask(monkeypatch) -> None:
    context: AnalyticsContext = FakeAnalyticsContext()
    insert = Mock()
    increment = Mock(return_value={"usage_count": 1, "feature_usage": {}})
    executor = Mock()
    executor.submit = lambda function, *args: function(*args)
    monkeypatch.setattr(product_analytics, "_EXECUTOR", executor)
    monkeypatch.setattr(product_analytics.analytics_db, "insert_event", insert)
    monkeypatch.setattr(product_analytics.db, "increment_usage", increment)
    monkeypatch.setattr(product_analytics, "_context", context)

    result = product_analytics.track_event("user-077", "migration_verified")

    assert result["usage_count"] == 1
    assert insert.call_args.kwargs["anonymous_id"] == "anon-077"
    assert insert.call_args.kwargs["page_path"] == "/reference-migration"
    product_analytics.set_tracking_opt_out(True)
    assert product_analytics.is_tracking_opted_out() is True


def test_sec_adapter_normalizes_provider_payload() -> None:
    response = Mock()
    response.json.return_value = {
        "0": {"ticker": " aapl "},
        "1": {"ticker": "MSFT"},
        "2": {"ticker": "AAPL"},
        "3": {"name": "Missing ticker"},
        "4": "invalid row",
    }
    http_get = Mock(return_value=response)

    reader: TickerUniverseReader = SecTickerUniverseAdapter(http_get=http_get)

    assert reader.read_tickers() == ["AAPL", "MSFT"]
    response.raise_for_status.assert_called_once_with()


def test_universe_workflow_accepts_interchangeable_reader(monkeypatch) -> None:
    monkeypatch.setattr(universe.cache, "read", lambda *_: None)
    written: list[tuple[str, str, list[str]]] = []
    monkeypatch.setattr(
        universe.cache,
        "write",
        lambda namespace, key, value: written.append((namespace, key, value)),
    )

    assert universe.get_universe(FakeUniverseReader()) == ["AAPL", "MSFT"]
    assert written == [("universe", "sec_all", ["AAPL", "MSFT"])]


def test_analysis_pipeline_is_an_application_service() -> None:
    assert stock_analysis.__name__ == "codes.services.stock_analysis"
    assert not (ROOT / "codes" / "app_modules" / "analysis.py").exists()


def test_financial_outputs_match_pre_migration_golden_fixture() -> None:
    golden = json.loads(
        (ROOT / "tests" / "fixtures" / "issue_077_financial_golden.json").read_text()
    )
    composite_fixture: Mapping[str, object] = golden["enhanced_composite"]
    result = scorer.enhanced_composite(**composite_fixture["inputs"])
    for key, expected in composite_fixture["expected"].items():
        assert result[key] == expected

    math_fixture = golden["financial_math"]
    prices = math_fixture["prices"]
    assert financial_math.cagr(prices[0], 121, 2) == pytest.approx(math_fixture["expected_cagr"])
    assert financial_math.max_drawdown(prices) == pytest.approx(
        math_fixture["expected_max_drawdown"]
    )
