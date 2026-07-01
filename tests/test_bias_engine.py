"""Tests for codes.models.bias_engine — pure classification logic."""

import pytest

from codes.models.bias_engine import Bias, RiskLevel, classify


def test_high_score_high_probability_is_outperform():
    result = classify(composite_score=75, risk_level=RiskLevel.LOW,
                       probability_outperform=0.7, distress_flag=False)
    assert result["bias"] == Bias.OUTPERFORM.value
    assert result["confidence"] > 0


def test_distress_flag_overrides_high_score():
    result = classify(composite_score=90, risk_level=RiskLevel.LOW,
                       probability_outperform=0.9, distress_flag=True)
    assert result["bias"] == Bias.UNDERPERFORM.value
    assert result["confidence"] == 1.0


def test_low_score_or_low_probability_is_underperform():
    r1 = classify(composite_score=20, risk_level=RiskLevel.HIGH,
                   probability_outperform=0.5, distress_flag=False)
    assert r1["bias"] == Bias.UNDERPERFORM.value

    r2 = classify(composite_score=50, risk_level=RiskLevel.HIGH,
                   probability_outperform=0.2, distress_flag=False)
    assert r2["bias"] == Bias.UNDERPERFORM.value


def test_mixed_signals_are_neutral():
    result = classify(composite_score=50, risk_level=RiskLevel.MEDIUM,
                       probability_outperform=0.5, distress_flag=False)
    assert result["bias"] == Bias.NEUTRAL.value


@pytest.mark.parametrize("score,prob,expected", [
    (60.0, 0.6, Bias.OUTPERFORM),   # exactly at both thresholds → inclusive
    (59.9, 0.6, Bias.NEUTRAL),      # just below score threshold
    (35.0, 0.5, Bias.UNDERPERFORM), # exactly at score threshold → inclusive
    (50.0, 0.4, Bias.UNDERPERFORM), # exactly at prob threshold → inclusive
])
def test_boundary_values(score, prob, expected):
    result = classify(composite_score=score, risk_level=RiskLevel.MEDIUM,
                       probability_outperform=prob, distress_flag=False)
    assert result["bias"] == expected.value


def test_confidence_is_monotonic_with_distance_from_thresholds():
    near = classify(composite_score=61, risk_level=RiskLevel.LOW,
                     probability_outperform=0.61, distress_flag=False)
    far = classify(composite_score=95, risk_level=RiskLevel.LOW,
                    probability_outperform=0.95, distress_flag=False)
    assert far["confidence"] > near["confidence"]

    near_u = classify(composite_score=34, risk_level=RiskLevel.HIGH,
                       probability_outperform=0.39, distress_flag=False)
    far_u = classify(composite_score=5, risk_level=RiskLevel.HIGH,
                      probability_outperform=0.05, distress_flag=False)
    assert far_u["confidence"] > near_u["confidence"]


def test_probability_outperform_is_passed_through_and_clamped():
    result = classify(composite_score=50, risk_level=RiskLevel.MEDIUM,
                       probability_outperform=1.4, distress_flag=False)
    assert result["probability_outperform"] == 1.0
