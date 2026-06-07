"""
Tests for Earnings Revision Model (PROJECT_MAP.md P1 feature).

Covers:
  1. Pure math helpers (_pct_change, _sigmoid_score, _linear_slope, _filter_outliers)
  2. Metric calculators (calc_eps_revision, calc_revenue_revision,
     calc_earnings_surprise_avg, calc_revision_breadth)
  3. Component scorers (_score_eps_revision_30d, etc.)
  4. get_revision_score() with mocked fetchers
  5. Signal threshold mapping
  6. scorer.enhanced_composite() integration (earnings_revision_result param)
"""

import math
import pytest
from unittest.mock import patch
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from codes.models.earnings_revision import (
    _safe, _pct_change, _sigmoid_score, _linear_slope, _filter_outliers,
    calc_eps_revision, calc_revenue_revision,
    calc_earnings_surprise_avg, calc_revision_breadth,
    _score_eps_revision_30d, _score_eps_revision_90d,
    _score_revenue_revision, _score_earnings_surprise,
    get_revision_score, SIGNAL_THRESHOLDS,
)
from codes.engine import scorer


# ── Fixtures ──────────────────────────────────────────────────────────────────

def _eps_est(values, n_analyst=10):
    """Build eps_estimates list newest-first from a list of avg values."""
    periods = [f"2025-{(12 - i):02d}-30" for i in range(len(values))]
    return [
        {"period": p, "eps_avg": v, "eps_high": v * 1.1, "eps_low": v * 0.9,
         "n_analyst": n_analyst}
        for p, v in zip(periods, values)
    ]


def _rev_est(values, n_analyst=10):
    periods = [f"2025-{(12 - i):02d}-30" for i in range(len(values))]
    return [
        {"period": p, "rev_avg": v, "rev_high": v * 1.05, "rev_low": v * 0.95,
         "n_analyst": n_analyst}
        for p, v in zip(periods, values)
    ]


def _surprises(actual_list, estimate_list):
    periods = [f"2025-{(12 - i):02d}-30" for i in range(len(actual_list))]
    results = []
    for p, a, e in zip(periods, actual_list, estimate_list):
        pct = (a - e) / abs(e) * 100 if abs(e) > 1e-10 else None
        results.append({"period": p, "actual": a, "estimate": e, "surprise_pct": pct})
    return results


def _rec_trend(period, sb, b, h, s, ss):
    return {"period": period, "strong_buy": sb, "buy": b, "hold": h,
            "sell": s, "strong_sell": ss}


def _make_base_args(**overrides):
    base = dict(
        graham_result    = {"total_score": 50, "total_max": 100},
        quality_result   = {"total_score": 50, "total_max": 100, "roe": 12},
        momentum_result  = {"total_score": 50, "total_max": 100},
        piotroski_result = {"f_score": 5, "f_score_max": 9},
        risk_result      = {"risk_score": 50, "risk_score_max": 100, "risk_criteria": []},
        altman_result    = {"risk_score": 50, "zone": "grey"},
        buffett_result   = {"total_score": 50, "total_max": 100},
    )
    base.update(overrides)
    return base


# ══════════════════════════════════════════════════════════════════════════════
# 1. Pure helpers
# ══════════════════════════════════════════════════════════════════════════════

class TestSafe:
    def test_valid_float(self):
        assert _safe(3.14) == pytest.approx(3.14)

    def test_none_returns_none(self):
        assert _safe(None) is None

    def test_nan_returns_none(self):
        assert _safe(float("nan")) is None

    def test_inf_returns_none(self):
        assert _safe(float("inf")) is None

    def test_string_float(self):
        assert _safe("2.5") == pytest.approx(2.5)

    def test_invalid_string(self):
        assert _safe("abc") is None


class TestPctChange:
    def test_positive_change(self):
        assert _pct_change(100, 110) == pytest.approx(10.0)

    def test_negative_change(self):
        assert _pct_change(100, 90) == pytest.approx(-10.0)

    def test_zero_old_returns_none(self):
        assert _pct_change(0, 10) is None

    def test_near_zero_old_returns_none(self):
        assert _pct_change(1e-12, 5) is None

    def test_negative_old_uses_abs(self):
        # pct_change(-100, -90) = (-90 - -100) / 100 = +10%
        assert _pct_change(-100, -90) == pytest.approx(10.0)


class TestSigmoidScore:
    def test_center_gives_50(self):
        assert _sigmoid_score(0.0, center=0.0, scale=5.0) == pytest.approx(50.0, abs=0.01)

    def test_large_positive_near_100(self):
        assert _sigmoid_score(100.0, center=0.0, scale=5.0) > 99.0

    def test_large_negative_near_0(self):
        assert _sigmoid_score(-100.0, center=0.0, scale=5.0) < 1.0

    def test_bounded_0_100(self):
        for v in [-50, -10, 0, 10, 50]:
            s = _sigmoid_score(v)
            assert 0 < s < 100


class TestLinearSlope:
    def test_flat_series_zero_slope(self):
        slope = _linear_slope([5.0, 5.0, 5.0, 5.0])
        assert slope == pytest.approx(0.0, abs=1e-6)

    def test_rising_series_positive_slope(self):
        slope = _linear_slope([1.0, 2.0, 3.0, 4.0])
        assert slope is not None and slope > 0

    def test_falling_series_negative_slope(self):
        slope = _linear_slope([4.0, 3.0, 2.0, 1.0])
        assert slope is not None and slope < 0

    def test_single_value_returns_none(self):
        assert _linear_slope([5.0]) is None

    def test_zero_mean_returns_none(self):
        assert _linear_slope([1.0, -1.0]) is None  # mean≈0


class TestFilterOutliers:
    def test_no_outliers_unchanged(self):
        vals = [1.0, 2.0, 3.0, 2.0, 1.5]
        assert _filter_outliers(vals) == vals

    def test_obvious_outlier_removed(self):
        vals = [5.0, 5.1, 5.2, 5.0, 1000.0]
        filtered = _filter_outliers(vals)
        assert 1000.0 not in filtered

    def test_two_values_unchanged(self):
        assert _filter_outliers([1.0, 100.0]) == [1.0, 100.0]


# ══════════════════════════════════════════════════════════════════════════════
# 2. Metric calculators
# ══════════════════════════════════════════════════════════════════════════════

class TestCalcEpsRevision:
    def test_rising_estimates_positive(self):
        # newest=1.50, prior=1.40 => +7.1%
        est = _eps_est([1.50, 1.40, 1.30])
        result = calc_eps_revision(est, lookback_periods=1)
        assert result is not None and result > 0

    def test_falling_estimates_negative(self):
        est = _eps_est([1.20, 1.40, 1.60])
        result = calc_eps_revision(est, lookback_periods=1)
        assert result is not None and result < 0

    def test_flat_estimates_near_zero(self):
        est = _eps_est([1.00, 1.00, 1.00])
        result = calc_eps_revision(est, lookback_periods=1)
        assert result is not None and abs(result) < 0.001

    def test_single_estimate_returns_none(self):
        est = _eps_est([1.50])
        assert calc_eps_revision(est) is None

    def test_empty_returns_none(self):
        assert calc_eps_revision([]) is None

    def test_90d_proxy_uses_longer_window(self):
        # Rising trend over 4+ estimates
        est = _eps_est([1.60, 1.50, 1.40, 1.30])
        result_90d = calc_eps_revision(est, lookback_periods=3)
        assert result_90d is not None


class TestCalcRevenueRevision:
    def test_rising_revenue_positive(self):
        est = _rev_est([1e9, 9e8, 8e8])
        result = calc_revenue_revision(est, lookback_periods=1)
        assert result is not None and result > 0

    def test_falling_revenue_negative(self):
        est = _rev_est([8e8, 9e8, 1e9])
        result = calc_revenue_revision(est, lookback_periods=1)
        assert result is not None and result < 0

    def test_empty_returns_none(self):
        assert calc_revenue_revision([]) is None


class TestCalcEarningsSurpriseAvg:
    def test_consistent_beats(self):
        surp = _surprises([1.10, 1.05, 1.08, 1.12], [1.00, 1.00, 1.00, 1.00])
        avg = calc_earnings_surprise_avg(surp, n_quarters=4)
        assert avg is not None and avg > 0

    def test_consistent_misses(self):
        surp = _surprises([0.90, 0.92, 0.88, 0.91], [1.00, 1.00, 1.00, 1.00])
        avg = calc_earnings_surprise_avg(surp, n_quarters=4)
        assert avg is not None and avg < 0

    def test_outlier_filtered(self):
        # Three normal + one extreme outlier (500%)
        surp = _surprises([1.05, 1.03, 1.04, 6.00], [1.00, 1.00, 1.00, 1.00])
        avg = calc_earnings_surprise_avg(surp, n_quarters=4)
        assert avg is not None and avg < 50  # outlier should be filtered

    def test_empty_returns_none(self):
        assert calc_earnings_surprise_avg([]) is None

    def test_respects_n_quarters(self):
        surp = _surprises([1.10, 1.10, 0.80, 0.80], [1.00, 1.00, 1.00, 1.00])
        avg4 = calc_earnings_surprise_avg(surp, n_quarters=4)
        avg2 = calc_earnings_surprise_avg(surp, n_quarters=2)
        # Only 2Q: both positive beats; 4Q includes misses
        assert avg2 > avg4


class TestCalcRevisionBreadth:
    def test_improving_sentiment_positive(self):
        trends = [
            _rec_trend("2025-04", 15, 10, 5, 2, 1),  # more bulls than before
            _rec_trend("2025-03", 10, 8,  5, 4, 3),
        ]
        breadth = calc_revision_breadth(trends)
        assert breadth is not None and breadth > 0

    def test_deteriorating_sentiment_negative(self):
        trends = [
            _rec_trend("2025-04", 5,  4,  5, 12, 8),   # more bears
            _rec_trend("2025-03", 10, 8,  5,  4, 3),
        ]
        breadth = calc_revision_breadth(trends)
        assert breadth is not None and breadth < 0

    def test_empty_returns_none(self):
        assert calc_revision_breadth([]) is None

    def test_single_period_computes_from_level(self):
        trends = [_rec_trend("2025-04", 10, 8, 4, 2, 1)]
        breadth = calc_revision_breadth(trends)
        assert breadth is not None
        assert -1.0 <= breadth <= 1.0

    def test_result_clamped_to_minus1_plus1(self):
        trends = [
            _rec_trend("2025-04", 100, 0, 0, 0, 0),
            _rec_trend("2025-03",   0, 0, 0, 100, 0),
        ]
        breadth = calc_revision_breadth(trends)
        assert -1.0 <= breadth <= 1.0


# ══════════════════════════════════════════════════════════════════════════════
# 3. Component scorers
# ══════════════════════════════════════════════════════════════════════════════

class TestComponentScorers:
    def test_eps_30d_none_gives_neutral(self):
        score, note = _score_eps_revision_30d(None)
        assert score == pytest.approx(35 * 0.5)
        assert "neutral" in note.lower() or "unavailable" in note.lower()

    def test_eps_30d_strong_up_high_score(self):
        score, _ = _score_eps_revision_30d(10.0)
        assert score > 35 * 0.7   # well above neutral

    def test_eps_30d_strong_down_low_score(self):
        score, _ = _score_eps_revision_30d(-10.0)
        assert score < 35 * 0.3   # well below neutral

    def test_eps_90d_none_gives_neutral(self):
        score, _ = _score_eps_revision_90d(None)
        assert score == pytest.approx(25 * 0.5)

    def test_revenue_none_gives_neutral(self):
        score, _ = _score_revenue_revision(None)
        assert score == pytest.approx(20 * 0.5)

    def test_surprise_none_gives_neutral(self):
        score, _ = _score_earnings_surprise(None)
        assert score == pytest.approx(20 * 0.5)

    def test_surprise_big_beat_high_score(self):
        score, _ = _score_earnings_surprise(15.0)
        assert score > 20 * 0.7

    def test_surprise_big_miss_low_score(self):
        score, _ = _score_earnings_surprise(-15.0)
        assert score < 20 * 0.3

    def test_all_scores_bounded(self):
        for val in [None, -20.0, -5.0, 0.0, 5.0, 20.0]:
            s30, _ = _score_eps_revision_30d(val)
            s90, _ = _score_eps_revision_90d(val)
            sr,  _ = _score_revenue_revision(val)
            ss,  _ = _score_earnings_surprise(val)
            assert 0 <= s30 <= 35
            assert 0 <= s90 <= 25
            assert 0 <= sr  <= 20
            assert 0 <= ss  <= 20


# ══════════════════════════════════════════════════════════════════════════════
# 4. Signal thresholds
# ══════════════════════════════════════════════════════════════════════════════

class TestSignalThresholds:
    def _signal_at(self, score):
        for threshold, sig in SIGNAL_THRESHOLDS:
            if score >= threshold:
                return sig
        return "STRONG_DOWN"

    def test_strong_up_at_75(self):
        assert self._signal_at(75) == "STRONG_UP"

    def test_strong_up_at_90(self):
        assert self._signal_at(90) == "STRONG_UP"

    def test_up_at_60(self):
        assert self._signal_at(60) == "UP"

    def test_neutral_at_50(self):
        assert self._signal_at(50) == "NEUTRAL"

    def test_down_at_25(self):
        assert self._signal_at(25) == "DOWN"

    def test_strong_down_at_20(self):
        assert self._signal_at(20) == "STRONG_DOWN"

    def test_strong_down_at_0(self):
        assert self._signal_at(0) == "STRONG_DOWN"


# ══════════════════════════════════════════════════════════════════════════════
# 5. get_revision_score() with mocked fetchers
# ══════════════════════════════════════════════════════════════════════════════

class TestGetRevisionScoreIntegration:
    """Patch the four fetch functions so no network I/O occurs."""

    def _call(self, surprises=None, eps=None, rev=None, rec=None, symbol="AAPL"):
        with patch("codes.models.earnings_revision._fetch_earnings_surprises",
                   return_value=surprises or []), \
             patch("codes.models.earnings_revision._fetch_eps_estimates",
                   return_value=eps or []), \
             patch("codes.models.earnings_revision._fetch_revenue_estimates",
                   return_value=rev or []), \
             patch("codes.models.earnings_revision._fetch_recommendation_trends",
                   return_value=rec or []):
            return get_revision_score(symbol)

    def test_output_schema_complete(self):
        result = self._call()
        required = {
            "ticker", "eps_revision_30d", "eps_revision_90d",
            "revenue_revision_30d", "earnings_surprise_avg",
            "revision_breadth", "forward_momentum_score", "signal",
            "low_coverage", "n_available", "total_score", "total_max", "criteria",
        }
        assert required.issubset(result.keys())

    def test_no_data_gives_neutral_50(self):
        result = self._call()
        assert result["forward_momentum_score"] == pytest.approx(50.0, abs=0.5)
        assert result["signal"] == "NEUTRAL"

    def test_total_max_is_100(self):
        assert self._call()["total_max"] == 100

    def test_forward_score_bounded_0_100(self):
        # All data strongly positive
        surp = _surprises([1.15] * 4, [1.00] * 4)
        eps  = _eps_est([2.00, 1.80, 1.60, 1.40])
        rev  = _rev_est([1e9, 9e8, 8e8])
        result = self._call(surprises=surp, eps=eps, rev=rev)
        assert 0 <= result["forward_momentum_score"] <= 100

    def test_all_positive_signals_strong_up_or_up(self):
        surp = _surprises([1.15] * 4, [1.00] * 4)   # 15% beats
        eps  = _eps_est([2.00, 1.80, 1.60, 1.40])   # rising estimates
        rev  = _rev_est([1e9, 9e8, 8e8])             # rising revenue
        result = self._call(surprises=surp, eps=eps, rev=rev)
        assert result["signal"] in ("STRONG_UP", "UP")

    def test_all_negative_signals_down_or_strong_down(self):
        surp = _surprises([0.85] * 4, [1.00] * 4)   # 15% misses
        eps  = _eps_est([1.40, 1.60, 1.80, 2.00])   # falling estimates
        rev  = _rev_est([8e8, 9e8, 1e9])             # falling revenue
        result = self._call(surprises=surp, eps=eps, rev=rev)
        assert result["signal"] in ("DOWN", "STRONG_DOWN")

    def test_low_coverage_flag_set_for_single_analyst(self):
        eps = _eps_est([1.50, 1.40], n_analyst=1)
        result = self._call(eps=eps)
        assert result["low_coverage"] is True

    def test_low_coverage_false_for_multiple_analysts(self):
        eps = _eps_est([1.50, 1.40], n_analyst=15)
        result = self._call(eps=eps)
        assert result["low_coverage"] is False

    def test_n_available_counts_non_none_metrics(self):
        # No data → all None → n_available = 0
        result = self._call()
        assert result["n_available"] == 0

    def test_ticker_uppercased(self):
        result = self._call(symbol="aapl")
        assert result["ticker"] == "AAPL"

    def test_criteria_has_four_items(self):
        result = self._call()
        assert len(result["criteria"]) == 4

    def test_criteria_max_sums_to_100(self):
        result = self._call()
        assert sum(c["max"] for c in result["criteria"]) == 100

    def test_total_score_equals_forward_momentum_score(self):
        surp = _surprises([1.10] * 4, [1.00] * 4)
        eps  = _eps_est([1.50, 1.40])
        result = self._call(surprises=surp, eps=eps)
        # total_score is set equal to forward_momentum_score
        assert math.isclose(result["total_score"], result["forward_momentum_score"],
                            abs_tol=0.01)


# ══════════════════════════════════════════════════════════════════════════════
# 6. scorer.enhanced_composite() integration
# ══════════════════════════════════════════════════════════════════════════════

class TestScorerIntegration:
    def test_weights_sum_to_one(self):
        from codes.engine.scorer import ENHANCED_WEIGHTS
        total = sum(ENHANCED_WEIGHTS.values())
        assert math.isclose(total, 1.0, abs_tol=1e-9), \
            f"ENHANCED_WEIGHTS sum = {total:.6f}, expected 1.0"

    def test_earnings_revision_key_in_weights(self):
        from codes.engine.scorer import ENHANCED_WEIGHTS
        assert "earnings_revision" in ENHANCED_WEIGHTS
        assert ENHANCED_WEIGHTS["earnings_revision"] == pytest.approx(0.12)

    def test_omitting_er_result_gives_neutral_50(self):
        """Omitting earnings_revision_result should use neutral 50 internally."""
        args = _make_base_args()
        result = scorer.enhanced_composite(**args)
        assert result["composite_score"] >= 0
        assert result["earnings_revision_pct"] == pytest.approx(50.0)

    def test_er_pct_in_return_dict(self):
        args = _make_base_args()
        result = scorer.enhanced_composite(**args)
        assert "earnings_revision_pct" in result

    def test_er_signal_in_return_dict_when_provided(self):
        er = {"total_score": 75.0, "total_max": 100, "signal": "STRONG_UP",
              "forward_momentum_score": 75.0, "criteria": []}
        result = scorer.enhanced_composite(**_make_base_args(), earnings_revision_result=er)
        assert result["earnings_revision_signal"] == "STRONG_UP"

    def test_er_signal_none_when_not_provided(self):
        result = scorer.enhanced_composite(**_make_base_args())
        assert result.get("earnings_revision_signal") is None

    def test_high_er_score_increases_composite(self):
        """Strong upward revision should lift composite vs neutral."""
        args = _make_base_args()
        without_er = scorer.enhanced_composite(**args)
        er_strong = {"total_score": 90.0, "total_max": 100, "signal": "STRONG_UP",
                     "forward_momentum_score": 90.0, "criteria": []}
        with_strong_er = scorer.enhanced_composite(**args, earnings_revision_result=er_strong)
        assert with_strong_er["composite_score"] > without_er["composite_score"]

    def test_low_er_score_decreases_composite(self):
        args = _make_base_args()
        without_er = scorer.enhanced_composite(**args)
        er_weak = {"total_score": 10.0, "total_max": 100, "signal": "STRONG_DOWN",
                   "forward_momentum_score": 10.0, "criteria": []}
        with_weak_er = scorer.enhanced_composite(**args, earnings_revision_result=er_weak)
        assert with_weak_er["composite_score"] < without_er["composite_score"]

    def test_er_impact_proportional_to_weight(self):
        """
        Changing er_pct by Δ should change composite by Δ × weight(er).
        All other factors held at 50.
        """
        from codes.engine.scorer import ENHANCED_WEIGHTS
        w_er = ENHANCED_WEIGHTS["earnings_revision"]
        args = _make_base_args()

        er_60 = {"total_score": 60.0, "total_max": 100, "criteria": []}
        er_40 = {"total_score": 40.0, "total_max": 100, "criteria": []}

        res_60 = scorer.enhanced_composite(**args, earnings_revision_result=er_60)
        res_40 = scorer.enhanced_composite(**args, earnings_revision_result=er_40)

        expected_delta = (60.0 - 40.0) * w_er
        actual_delta   = res_60["composite_score"] - res_40["composite_score"]

        # Grey zone applies a -10 penalty that shifts both, so difference is preserved
        assert math.isclose(actual_delta, expected_delta, abs_tol=0.15)

    def test_greenblatt_still_not_in_composite(self):
        """Greenblatt must remain display-only after adding earnings_revision."""
        args = _make_base_args()
        without_gb = scorer.enhanced_composite(**args)
        gb = {"earnings_yield": 99.0, "roic": 99.0, "fcf_yield": 99.0,
              "magic_score": None}
        with_gb = scorer.enhanced_composite(**args, greenblatt_result=gb)
        assert math.isclose(
            without_gb["composite_score"],
            with_gb["composite_score"],
            abs_tol=0.01,
        )

    def test_backward_compat_no_er_arg(self):
        """Callers not passing earnings_revision_result must still work."""
        args = _make_base_args()
        try:
            result = scorer.enhanced_composite(**args)
        except TypeError as exc:
            pytest.fail(f"enhanced_composite raised TypeError: {exc}")
        assert "composite_score" in result


if __name__ == "__main__":
    import pytest as _pytest
    _pytest.main([__file__, "-v"])
