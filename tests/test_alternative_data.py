"""
Tests for Phase E alternative_data.py.

The module is intentionally provider-free for now: it must return a stable,
neutral schema without performing network access or affecting composite scores.
SEC 8-K sentiment can score caller-supplied text deterministically.
"""

import os
import sys

import pytest

ROOT = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, os.path.join(ROOT, "codes", "engine"))
sys.path.insert(0, os.path.join(ROOT, "codes", "models"))

import alternative_data
import scorer


def _base_scorer_args(**overrides):
    base = dict(
        graham_result={"total_score": 50, "total_max": 100},
        quality_result={"total_score": 50, "total_max": 100, "roe": 12},
        momentum_result={"total_score": 50, "total_max": 100},
        piotroski_result={"f_score": 5},
        risk_result={"risk_score": 50, "risk_score_max": 100},
        altman_result={"risk_score": 50, "zone": "safe"},
        buffett_result={"total_score": 50, "total_max": 100},
    )
    base.update(overrides)
    return base


def test_alternative_data_schema_is_neutral_without_provider_data():
    result = alternative_data.get_alternative_data_score(" aapl ")

    assert result["ticker"] == "AAPL"
    assert result["alternative_data_score"] == pytest.approx(50.0)
    assert result["total_score"] == pytest.approx(50.0)
    assert result["total_max"] == pytest.approx(100.0)
    assert result["signal"] == "NEUTRAL"
    assert result["status"] == "NO_DATA"
    assert result["available"] is False
    assert result["low_coverage"] is True
    assert result["provider"] is None
    assert result["phase"] == "Phase E"


def test_alternative_data_includes_phase_e_signals():
    result = alternative_data.get_alternative_data_score("MSFT")
    signals = result["signals"]

    assert [s["name"] for s in signals] == [
        "sec_8k_sentiment",
        "hiring_velocity",
        "web_traffic",
        "insider_trends",
        "institutional_ownership",
        "patent_activity",
        "supply_chain_relationships",
    ]
    assert all(s["score"] == pytest.approx(50.0) for s in signals)
    assert all(s["signal"] == "NEUTRAL" for s in signals)
    assert all(s["available"] is False for s in signals)
    assert signals[0]["status"] == "NO_DATA"
    assert signals[1]["status"] == "PLANNED"
    assert signals[2]["status"] == "WAITING_FOR_SOURCE"
    assert signals[-1]["status"] == "RESEARCH"


def test_sec_8k_sentiment_is_deterministic_and_auditable():
    filings = [
        {
            "title": "8-K",
            "text": (
                "The company reported strong growth and improved profitability. "
                "A prior material weakness was resolved."
            ),
        }
    ]

    result = alternative_data.get_alternative_data_score("MSFT", sec_8k_filings=filings)
    signal = result["signals"][0]

    assert result["available"] is True
    assert signal["name"] == "sec_8k_sentiment"
    assert signal["status"] == "AVAILABLE"
    assert signal["score"] > 50
    assert signal["details"]["method"] == "fixed_lexicon_v1"
    assert signal["details"]["positive_hits"] > signal["details"]["negative_hits"]


def test_sec_8k_sentiment_can_turn_bearish():
    filings = [
        "The issuer disclosed a default, an impairment charge, and a lawsuit."
    ]

    signal = alternative_data.get_sec_8k_sentiment_signal("TSLA", filings)

    assert signal["available"] is True
    assert signal["signal"] == "BEARISH"
    assert signal["score"] < 40


def test_framework_only_does_not_change_enhanced_composite_weights():
    assert "alternative_data" not in scorer.ENHANCED_WEIGHTS

    baseline = scorer.enhanced_composite(**_base_scorer_args())
    with_alt_data_available = scorer.enhanced_composite(**_base_scorer_args())

    assert with_alt_data_available["composite_score"] == baseline["composite_score"]
