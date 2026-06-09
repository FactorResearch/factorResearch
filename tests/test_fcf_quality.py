"""
Tests for FCF Quality Model (PROJECT_MAP.md P1 feature).

Covers:
  1. Each metric method in isolation
  2. Edge cases: missing data, zero denominators, negative values, single period
  3. Weighted scoring normalised to 0-100
  4. Signal threshold mapping
  5. Output JSON shape (strict keys, types)
  6. scorer.enhanced_composite() integration (fcf_quality_result param)
  7. ENHANCED_WEIGHTS sum to 1.0 after adding fcf_quality
"""

import math
import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from codes.models.fcf_quality import (
    FCFQualityAnalyzer,
    _signal,
    _norm_fcf_margin,
    _norm_fcf_conversion,
    _norm_fcf_stability,
    _norm_fcf_growth_consistency,
    _norm_accrual_ratio,
)
from codes.engine import scorer


# ── Helpers ───────────────────────────────────────────────────────────────────

def _rec(v):
    return [{"value": v}] if v is not None else []


def _recs(lst):
    return [{"value": v} for v in lst] if lst else []


def _sec(
    *,
    op_cf=None,
    capex=None,
    net_inc=None,
    revenue=None,
    total_assets=None,
    op_cf_list=None,
    capex_list=None,
    net_inc_list=None,
    revenue_list=None,
    total_assets_list=None,
):
    return {
        "op_cf":        _recs(op_cf_list) if op_cf_list else _rec(op_cf),
        "capex":        _recs(capex_list) if capex_list else _rec(capex),
        "net_inc":      _recs(net_inc_list) if net_inc_list else _rec(net_inc),
        "revenue":      _recs(revenue_list) if revenue_list else _rec(revenue),
        "total_assets": _recs(total_assets_list) if total_assets_list else _rec(total_assets),
    }


def _make(**kwargs):
    """Build an FCFQualityAnalyzer with standard defaults."""
    defaults = dict(
        op_cf=80_000, capex=20_000, net_inc=60_000,
        revenue=500_000, total_assets=400_000,
    )
    defaults.update(kwargs)
    return FCFQualityAnalyzer("TEST", _sec(**defaults))


def _make_base_scorer_args(**overrides):
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
# 1. Signal mapping
# ══════════════════════════════════════════════════════════════════════════════

class TestSignalMapping:
    def test_strong_cash_generator(self):
        assert _signal(80) == "STRONG_CASH_GENERATOR"
        assert _signal(100) == "STRONG_CASH_GENERATOR"

    def test_high_cash_quality(self):
        assert _signal(65) == "HIGH_CASH_QUALITY"
        assert _signal(79.9) == "HIGH_CASH_QUALITY"

    def test_neutral(self):
        assert _signal(45) == "NEUTRAL"
        assert _signal(64) == "NEUTRAL"

    def test_weak_cash_quality(self):
        assert _signal(30) == "WEAK_CASH_QUALITY"
        assert _signal(44) == "WEAK_CASH_QUALITY"

    def test_earnings_quality_risk(self):
        assert _signal(0) == "EARNINGS_QUALITY_RISK"
        assert _signal(29.9) == "EARNINGS_QUALITY_RISK"


# ══════════════════════════════════════════════════════════════════════════════
# 2. Normalisation helpers
# ══════════════════════════════════════════════════════════════════════════════

class TestNormFcfMargin:
    def test_above_20_gives_100(self):
        assert _norm_fcf_margin(20) == pytest.approx(100.0)
        assert _norm_fcf_margin(30) == pytest.approx(100.0)

    def test_zero_gives_0(self):
        assert _norm_fcf_margin(0) == pytest.approx(0.0)

    def test_negative_gives_0(self):
        assert _norm_fcf_margin(-5) == pytest.approx(0.0)

    def test_none_gives_0(self):
        assert _norm_fcf_margin(None) == pytest.approx(0.0)

    def test_10_pct_gives_50(self):
        assert _norm_fcf_margin(10) == pytest.approx(50.0)


class TestNormFcfConversion:
    def test_100_gives_100(self):
        assert _norm_fcf_conversion(100) == pytest.approx(100.0)
        assert _norm_fcf_conversion(150) == pytest.approx(100.0)

    def test_0_gives_0(self):
        assert _norm_fcf_conversion(0) == pytest.approx(0.0)

    def test_negative_gives_0(self):
        assert _norm_fcf_conversion(-10) == pytest.approx(0.0)

    def test_none_gives_50_neutral(self):
        assert _norm_fcf_conversion(None) == pytest.approx(50.0)

    def test_50_gives_50(self):
        assert _norm_fcf_conversion(50) == pytest.approx(50.0)


class TestNormFcfStability:
    def test_low_cv_gives_100(self):
        assert _norm_fcf_stability(0.0) == pytest.approx(100.0)
        assert _norm_fcf_stability(0.20) == pytest.approx(100.0)

    def test_high_cv_gives_0(self):
        assert _norm_fcf_stability(1.0) == pytest.approx(0.0)
        assert _norm_fcf_stability(2.0) == pytest.approx(0.0)

    def test_none_gives_50_neutral(self):
        assert _norm_fcf_stability(None) == pytest.approx(50.0)

    def test_mid_cv_in_range(self):
        v = _norm_fcf_stability(0.60)
        assert 0 < v < 100


class TestNormFcfGrowthConsistency:
    def test_all_positive_gives_100(self):
        assert _norm_fcf_growth_consistency(1.0) == pytest.approx(100.0)

    def test_none_positive_gives_0(self):
        assert _norm_fcf_growth_consistency(0.0) == pytest.approx(0.0)

    def test_none_gives_50_neutral(self):
        assert _norm_fcf_growth_consistency(None) == pytest.approx(50.0)

    def test_half_gives_50(self):
        assert _norm_fcf_growth_consistency(0.5) == pytest.approx(50.0)


class TestNormAccrualRatio:
    def test_very_negative_gives_100(self):
        assert _norm_accrual_ratio(-0.05) == pytest.approx(100.0)
        assert _norm_accrual_ratio(-0.20) == pytest.approx(100.0)

    def test_high_positive_gives_0(self):
        assert _norm_accrual_ratio(0.10) == pytest.approx(0.0)
        assert _norm_accrual_ratio(0.50) == pytest.approx(0.0)

    def test_none_gives_50_neutral(self):
        assert _norm_accrual_ratio(None) == pytest.approx(50.0)

    def test_zero_in_range(self):
        v = _norm_accrual_ratio(0.0)
        assert 0 < v < 100


# ══════════════════════════════════════════════════════════════════════════════
# 3. FCFQualityAnalyzer metric methods
# ══════════════════════════════════════════════════════════════════════════════

class TestCalcFcf:
    def test_basic_fcf(self):
        # FCF = 80k - abs(20k) = 60k
        pa = _make(op_cf=80_000, capex=20_000)
        assert pa.calc_fcf() == pytest.approx(60_000)

    def test_capex_stored_as_positive_outflow(self):
        # Some filers store capex negative — abs() guard
        pa = FCFQualityAnalyzer("X", _sec(op_cf=80_000, capex=-20_000))
        assert pa.calc_fcf() == pytest.approx(60_000)

    def test_no_op_cf_returns_none(self):
        pa = FCFQualityAnalyzer("X", _sec(capex=20_000))
        assert pa.calc_fcf() is None

    def test_no_capex_returns_none(self):
        pa = FCFQualityAnalyzer("X", _sec(op_cf=80_000))
        assert pa.calc_fcf() is None


class TestCalcFcfMargin:
    def test_basic_margin(self):
        # FCF=60k, Revenue=500k → 12%
        pa = _make(op_cf=80_000, capex=20_000, revenue=500_000)
        assert pa.calc_fcf_margin() == pytest.approx(12.0)

    def test_zero_revenue_returns_none(self):
        pa = _make(op_cf=80_000, capex=20_000, revenue=0)
        assert pa.calc_fcf_margin() is None

    def test_missing_revenue_returns_none(self):
        pa = FCFQualityAnalyzer("X", _sec(op_cf=80_000, capex=20_000))
        assert pa.calc_fcf_margin() is None

    def test_negative_fcf_gives_negative_margin(self):
        pa = _make(op_cf=10_000, capex=50_000, revenue=500_000)
        margin = pa.calc_fcf_margin()
        assert margin is not None and margin < 0


class TestCalcFcfConversion:
    def test_basic_conversion(self):
        # FCF=60k, NI=60k → 100%
        pa = _make(op_cf=80_000, capex=20_000, net_inc=60_000)
        assert pa.calc_fcf_conversion() == pytest.approx(100.0)

    def test_net_inc_zero_returns_none(self):
        pa = _make(op_cf=80_000, capex=20_000, net_inc=0)
        assert pa.calc_fcf_conversion() is None

    def test_missing_net_inc_returns_none(self):
        pa = FCFQualityAnalyzer("X", _sec(op_cf=80_000, capex=20_000))
        assert pa.calc_fcf_conversion() is None

    def test_high_fcf_vs_low_ni_gives_high_conversion(self):
        pa = _make(op_cf=100_000, capex=10_000, net_inc=30_000)
        conv = pa.calc_fcf_conversion()
        assert conv is not None and conv > 100


class TestCalcFcfStability:
    def test_stable_margins_give_low_cv(self):
        pa = FCFQualityAnalyzer(
            "X",
            _sec(
                op_cf_list   =[100, 100, 100, 100, 100],
                capex_list   =[10,  10,  10,  10,  10 ],
                revenue_list =[900, 900, 900, 900, 900],
            ),
        )
        cv = pa.calc_fcf_stability()
        assert cv is not None and cv == pytest.approx(0.0, abs=1e-6)

    def test_volatile_margins_give_high_cv(self):
        pa = FCFQualityAnalyzer(
            "X",
            _sec(
                op_cf_list   =[200, -50, 200, -50, 200],
                capex_list   =[10,   10,  10,  10,  10],
                revenue_list =[1000,1000,1000,1000,1000],
            ),
        )
        cv = pa.calc_fcf_stability()
        assert cv is not None and cv > 0.5

    def test_fewer_than_3_periods_returns_none(self):
        pa = FCFQualityAnalyzer(
            "X",
            _sec(
                op_cf_list   =[100, 100],
                capex_list   =[10,  10 ],
                revenue_list =[900, 900],
            ),
        )
        assert pa.calc_fcf_stability() is None


class TestCalcFcfGrowthConsistency:
    def test_always_growing_gives_1(self):
        pa = FCFQualityAnalyzer(
            "X",
            _sec(
                op_cf_list =[500, 400, 300, 200, 100],  # newest first, growing
                capex_list =[50,  40,  30,  20,  10 ],
            ),
        )
        frac = pa.calc_fcf_growth_consistency()
        assert frac == pytest.approx(1.0)

    def test_always_shrinking_gives_0(self):
        pa = FCFQualityAnalyzer(
            "X",
            _sec(
                op_cf_list =[100, 200, 300, 400, 500],  # newest first, shrinking
                capex_list =[10,  20,  30,  40,  50 ],
            ),
        )
        frac = pa.calc_fcf_growth_consistency()
        assert frac == pytest.approx(0.0)

    def test_fewer_than_3_returns_none(self):
        pa = FCFQualityAnalyzer(
            "X",
            _sec(op_cf_list=[200, 100], capex_list=[20, 10]),
        )
        assert pa.calc_fcf_growth_consistency() is None


class TestCalcAccrualRatio:
    def test_ocf_exceeds_ni_gives_negative_ratio(self):
        # NI=60k, OCF=80k, TA=400k → (60k-80k)/400k = -0.05
        pa = _make(op_cf=80_000, capex=20_000, net_inc=60_000, total_assets=400_000)
        ar = pa.calc_accrual_ratio()
        assert ar is not None
        assert ar == pytest.approx(-0.05, abs=1e-6)

    def test_ni_exceeds_ocf_gives_positive_ratio(self):
        pa = _make(op_cf=40_000, capex=10_000, net_inc=80_000, total_assets=400_000)
        ar = pa.calc_accrual_ratio()
        assert ar is not None and ar > 0

    def test_missing_total_assets_returns_none(self):
        pa = FCFQualityAnalyzer("X", _sec(op_cf=80_000, capex=20_000, net_inc=60_000))
        assert pa.calc_accrual_ratio() is None

    def test_zero_total_assets_returns_none(self):
        pa = _make(op_cf=80_000, capex=20_000, net_inc=60_000, total_assets=0)
        assert pa.calc_accrual_ratio() is None


class TestCalcFcfCagr5y:
    def test_basic_cagr(self):
        # FCF grows from 100k to 161k over 5y → CAGR ≈ 10%
        pa = FCFQualityAnalyzer(
            "X",
            _sec(
                op_cf_list =[180_000, 160_000, 140_000, 120_000, 110_000],
                capex_list =[19_000,  17_000,  15_000,  13_000,  10_000],
            ),
        )
        cagr = pa.calc_fcf_cagr_5y()
        assert cagr is not None
        assert cagr > 0

    def test_fewer_than_5_returns_none(self):
        pa = FCFQualityAnalyzer(
            "X",
            _sec(
                op_cf_list =[100, 90, 80, 70],
                capex_list =[10,   9,  8,  7],
            ),
        )
        assert pa.calc_fcf_cagr_5y() is None

    def test_negative_start_fcf_returns_none(self):
        pa = FCFQualityAnalyzer(
            "X",
            _sec(
                op_cf_list =[100, 90, 80, 70, 5],
                capex_list =[10,   9,  8,  7, 50],  # last FCF = 5-50 = -45
            ),
        )
        assert pa.calc_fcf_cagr_5y() is None


# ══════════════════════════════════════════════════════════════════════════════
# 4. get_fcf_quality_score output schema
# ══════════════════════════════════════════════════════════════════════════════

class TestGetFcfQualityScore:
    REQUIRED_KEYS = {
        "ticker", "fcf", "operating_cash_flow", "capex",
        "fcf_margin", "fcf_conversion", "fcf_stability",
        "fcf_growth_consistency", "accrual_ratio", "fcf_cagr_5y",
        "fcf_quality_score", "signal", "total_score", "total_max",
    }

    def test_output_has_required_keys(self):
        pa = _make()
        out = pa.get_fcf_quality_score()
        assert self.REQUIRED_KEYS == set(out.keys()), (
            f"Extra: {set(out.keys()) - self.REQUIRED_KEYS}  "
            f"Missing: {self.REQUIRED_KEYS - set(out.keys())}"
        )

    def test_score_in_range_0_to_100(self):
        pa = _make()
        out = pa.get_fcf_quality_score()
        assert 0.0 <= out["fcf_quality_score"] <= 100.0

    def test_ticker_stored_uppercase(self):
        pa = FCFQualityAnalyzer("aapl", _sec())
        out = pa.get_fcf_quality_score()
        assert out["ticker"] == "AAPL"

    def test_signal_consistent_with_score(self):
        pa = _make()
        out = pa.get_fcf_quality_score()
        from codes.models.fcf_quality import _signal
        assert out["signal"] == _signal(out["fcf_quality_score"])

    def test_total_score_matches_fcf_quality_score(self):
        pa = _make()
        out = pa.get_fcf_quality_score()
        assert out["total_score"] == out["fcf_quality_score"]
        assert out["total_max"] == 100.0

    def test_all_missing_data_does_not_crash(self):
        pa = FCFQualityAnalyzer("X", {})
        try:
            out = pa.get_fcf_quality_score()
        except Exception as exc:
            pytest.fail(f"get_fcf_quality_score raised {type(exc).__name__}: {exc}")
        assert math.isfinite(out["fcf_quality_score"])

    def test_capex_stored_as_positive_in_output(self):
        """Output capex should always be the absolute (positive) value."""
        pa = FCFQualityAnalyzer("X", _sec(op_cf=80_000, capex=-20_000))
        out = pa.get_fcf_quality_score()
        assert out["capex"] == pytest.approx(20_000, abs=1)

    def test_strong_company_scores_above_65(self):
        """High-quality FCF profile should yield HIGH_CASH_QUALITY or better."""
        pa = FCFQualityAnalyzer(
            "GOOD",
            _sec(
                op_cf_list   =[200e9, 190e9, 180e9, 170e9, 160e9, 150e9, 140e9],
                capex_list   =[15e9,  14e9,  13e9,  12e9,  11e9,  10e9,  9e9  ],
                revenue_list =[500e9, 470e9, 440e9, 410e9, 380e9, 350e9, 320e9],
                net_inc_list =[100e9, 95e9,  90e9,  85e9,  80e9,  75e9,  70e9 ],
                total_assets_list=[350e9, 330e9],
            ),
        )
        out = pa.get_fcf_quality_score()
        assert out["fcf_quality_score"] >= 65

    def test_weak_company_scores_below_40(self):
        """Negative FCF, poor conversion → low score."""
        pa = FCFQualityAnalyzer(
            "WEAK",
            _sec(
                op_cf=10_000, capex=80_000,   # FCF = -70k
                net_inc=50_000, revenue=200_000,
                total_assets=300_000,
            ),
        )
        out = pa.get_fcf_quality_score()
        assert out["fcf_quality_score"] < 40


# ══════════════════════════════════════════════════════════════════════════════
# 5. scorer.enhanced_composite integration
# ══════════════════════════════════════════════════════════════════════════════

class TestScorerIntegration:
    def test_weights_sum_to_one(self):
        from codes.engine.scorer import ENHANCED_WEIGHTS
        total = sum(ENHANCED_WEIGHTS.values())
        assert math.isclose(total, 1.0, abs_tol=1e-9), \
            f"ENHANCED_WEIGHTS sum = {total:.10f}, expected 1.0"

    def test_fcf_quality_key_in_weights(self):
        from codes.engine.scorer import ENHANCED_WEIGHTS
        assert "fcf_quality" in ENHANCED_WEIGHTS
        assert ENHANCED_WEIGHTS["fcf_quality"] == pytest.approx(0.10)

    def test_fcf_quality_pct_in_return_dict(self):
        result = scorer.enhanced_composite(**_make_base_scorer_args())
        assert "fcf_quality_pct" in result

    def test_omitting_fcf_quality_result_gives_neutral_50(self):
        result = scorer.enhanced_composite(**_make_base_scorer_args())
        assert result["fcf_quality_pct"] == pytest.approx(50.0)

    def test_fcf_quality_signal_in_return_dict_when_provided(self):
        fcf = {"fcf_quality_score": 75.0, "signal": "HIGH_CASH_QUALITY",
               "total_score": 75.0, "total_max": 100.0}
        result = scorer.enhanced_composite(
            **_make_base_scorer_args(), fcf_quality_result=fcf
        )
        assert result["fcf_quality_signal"] == "HIGH_CASH_QUALITY"

    def test_fcf_quality_signal_none_when_not_provided(self):
        result = scorer.enhanced_composite(**_make_base_scorer_args())
        assert result.get("fcf_quality_signal") is None

    def test_high_fcf_score_increases_composite(self):
        args = _make_base_scorer_args()
        without_fcf = scorer.enhanced_composite(**args)
        fcf_strong = {"fcf_quality_score": 90.0, "total_score": 90.0,
                      "total_max": 100.0, "signal": "STRONG_CASH_GENERATOR"}
        with_strong_fcf = scorer.enhanced_composite(**args, fcf_quality_result=fcf_strong)
        assert with_strong_fcf["composite_score"] > without_fcf["composite_score"]

    def test_low_fcf_score_decreases_composite(self):
        args = _make_base_scorer_args()
        without_fcf = scorer.enhanced_composite(**args)
        fcf_weak = {"fcf_quality_score": 10.0, "total_score": 10.0,
                    "total_max": 100.0, "signal": "EARNINGS_QUALITY_RISK"}
        with_weak_fcf = scorer.enhanced_composite(**args, fcf_quality_result=fcf_weak)
        assert with_weak_fcf["composite_score"] < without_fcf["composite_score"]

    def test_fcf_impact_proportional_to_weight(self):
        """Δcomposite ≈ Δfcf_pct × weight(fcf_quality), all others at 50."""
        from codes.engine.scorer import ENHANCED_WEIGHTS
        w_fcf = ENHANCED_WEIGHTS["fcf_quality"]
        args = _make_base_scorer_args()

        fcf_60 = {"fcf_quality_score": 60.0, "total_score": 60.0, "total_max": 100.0}
        fcf_40 = {"fcf_quality_score": 40.0, "total_score": 40.0, "total_max": 100.0}

        res_60 = scorer.enhanced_composite(**args, fcf_quality_result=fcf_60)
        res_40 = scorer.enhanced_composite(**args, fcf_quality_result=fcf_40)

        expected_delta = (60.0 - 40.0) * w_fcf
        actual_delta   = res_60["composite_score"] - res_40["composite_score"]
        assert math.isclose(actual_delta, expected_delta, abs_tol=0.15)

    def test_existing_tests_not_broken_by_new_param(self):
        """Callers not passing fcf_quality_result must still work (backward compat)."""
        args = _make_base_scorer_args()
        try:
            result = scorer.enhanced_composite(**args)
        except TypeError as exc:
            pytest.fail(f"enhanced_composite raised TypeError: {exc}")
        assert "composite_score" in result

    def test_greenblatt_still_not_in_composite(self):
        """Greenblatt remains display-only after adding fcf_quality."""
        args = _make_base_scorer_args()
        without_gb = scorer.enhanced_composite(**args)
        gb = {"earnings_yield": 99.0, "roic": 99.0, "fcf_yield": 99.0,
              "magic_score": None}
        with_gb = scorer.enhanced_composite(**args, greenblatt_result=gb)
        assert math.isclose(
            without_gb["composite_score"], with_gb["composite_score"]
        ), "Greenblatt must not affect composite_score"


if __name__ == "__main__":
    import pytest as _pytest
    _pytest.main([__file__, "-v"])
