"""
Tests for ISSUE-003: FCF Yield = FCF / EV with non-zero EV guard.

Verifies:
  1. fcf_yield = (op_cf − abs(capex)) / EV  (correct formula)
  2. fcf_yield is None when EV = 0 or EV <= 0  (no ZeroDivisionError)
  3. fcf_yield is None when op_cf is missing
  4. fcf_yield uses op_cf as proxy when capex is missing
  5. scorer.enhanced_composite passes greenblatt_fcf_yield through
"""

import math
import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from codes import greenblatt, scorer


# ── Helpers ───────────────────────────────────────────────────────────────────

def _rec(v):
    return [{"value": v}] if v is not None else []


def _sec(*, ebit=100_000, shares=1_000, lt_debt=200_000, cur_lib=50_000,
         cur_ast=150_000, ppe=300_000, cash=20_000, tot_ast=500_000,
         op_cf=80_000, capex=20_000):
    return {
        "op_income":    _rec(ebit),
        "shares":       _rec(shares),
        "lt_debt":      _rec(lt_debt),
        "cur_lib":      _rec(cur_lib),
        "cur_ast":      _rec(cur_ast),
        "ppe_net":      _rec(ppe),
        "cash":         _rec(cash),
        "total_assets": _rec(tot_ast),
        "op_cf":        _rec(op_cf),
        "capex":        _rec(capex),
    }


def _make_result(score=50, max_=100, **extra):
    base = {"total_score": score, "total_max": max_}
    base.update(extra)
    return base


# ══════════════════════════════════════════════════════════════════════════════

class TestFcfYieldFormula:
    def test_correct_formula(self):
        """fcf_yield = (op_cf − abs(capex)) / EV × 100"""
        sec = _sec(op_cf=80_000, capex=20_000, shares=1_000, lt_debt=200_000, cash=20_000)
        result = greenblatt.compute_single(price=50.0, sec=sec)
        # EV = 50×1000 + 200000 − 20000 = 230000
        # FCF = 80000 − 20000 = 60000
        ev = 50 * 1_000 + 200_000 - 20_000
        expected = round(60_000 / ev * 100, 3)
        assert result["fcf_yield"] == pytest.approx(expected, abs=0.01)

    def test_capex_treated_as_positive_outflow(self):
        """Negative capex from SEC (stored as positive) is abs()-guarded."""
        sec = _sec(op_cf=80_000, capex=-20_000)   # some filers report capex negative
        result_neg = greenblatt.compute_single(price=50.0, sec=sec)
        sec2 = _sec(op_cf=80_000, capex=20_000)
        result_pos = greenblatt.compute_single(price=50.0, sec=sec2)
        # Both should give same FCF = 80000 - 20000 = 60000
        assert result_neg["fcf_yield"] == pytest.approx(result_pos["fcf_yield"], abs=0.01)

    def test_fcf_yield_present_in_return_dict(self):
        result = greenblatt.compute_single(price=50.0, sec=_sec())
        assert "fcf_yield" in result


class TestFcfYieldNonZeroEvGuard:
    def test_no_price_gives_none(self):
        """EV is None when price is None → fcf_yield must be None."""
        result = greenblatt.compute_single(price=None, sec=_sec(op_cf=50_000))
        assert result["fcf_yield"] is None

    def test_zero_ev_gives_none(self):
        """EV = mkt_cap + 0 - mkt_cap = 0 → no division by zero."""
        # lt_debt=0, cash = price×shares → EV = 0
        sec = _sec(lt_debt=0, cash=50_000, shares=1_000, op_cf=50_000, capex=10_000)
        result = greenblatt.compute_single(price=50.0, sec=sec)
        # EV = 50×1000 + 0 - 50000 = 0
        assert result["enterprise_value"] == pytest.approx(0.0, abs=0.01)
        assert result["fcf_yield"] is None

    def test_negative_ev_gives_none(self):
        """EV < 0 (cash > mkt_cap + debt) → fcf_yield is None."""
        sec = _sec(lt_debt=0, cash=100_000, shares=1_000, op_cf=50_000, capex=10_000)
        result = greenblatt.compute_single(price=50.0, sec=sec)
        # EV = 50000 + 0 - 100000 = -50000
        assert result["fcf_yield"] is None


class TestFcfYieldMissingInputs:
    def test_no_op_cf_returns_none(self):
        sec = _sec()
        sec["op_cf"] = []
        result = greenblatt.compute_single(price=50.0, sec=sec)
        assert result["fcf_yield"] is None

    def test_no_capex_uses_op_cf_as_proxy(self):
        """When capex is missing, FCF = op_cf (conservative proxy)."""
        sec = _sec(op_cf=60_000)
        sec["capex"] = []
        result = greenblatt.compute_single(price=50.0, sec=sec)
        assert result["fcf_yield"] is not None
        ev = 50 * 1_000 + 200_000 - 20_000
        expected = round(60_000 / ev * 100, 3)
        assert result["fcf_yield"] == pytest.approx(expected, abs=0.01)

    def test_no_shares_gives_none(self):
        """No shares → EV = None → fcf_yield = None."""
        sec = _sec(op_cf=50_000)
        sec["shares"] = []
        result = greenblatt.compute_single(price=50.0, sec=sec)
        assert result["fcf_yield"] is None


class TestScorerPassthrough:
    def test_greenblatt_fcf_yield_in_enhanced_composite(self):
        gb = {"earnings_yield": 10.0, "roic": 20.0, "fcf_yield": 5.5, "magic_score": None}
        result = scorer.enhanced_composite(
            graham_result    = _make_result(50),
            quality_result   = _make_result(50, roe=12),
            momentum_result  = _make_result(50),
            piotroski_result = {"f_score": 5, "f_score_max": 9},
            risk_result      = {"risk_score": 50, "risk_score_max": 100, "risk_criteria": []},
            altman_result    = {"risk_score": 50, "zone": "grey"},
            buffett_result   = _make_result(50),
            greenblatt_result = gb,
        )
        assert result.get("greenblatt_fcf_yield") == pytest.approx(5.5)

    def test_greenblatt_fcf_yield_none_when_no_greenblatt_result(self):
        result = scorer.enhanced_composite(
            graham_result    = _make_result(50),
            quality_result   = _make_result(50, roe=12),
            momentum_result  = _make_result(50),
            piotroski_result = {"f_score": 5, "f_score_max": 9},
            risk_result      = {"risk_score": 50, "risk_score_max": 100, "risk_criteria": []},
            altman_result    = {"risk_score": 50, "zone": "grey"},
            buffett_result   = _make_result(50),
        )
        assert result.get("greenblatt_fcf_yield") is None

    def test_fcf_yield_not_in_composite_score(self):
        """FCF yield must not alter composite_score (display-only per ISSUE-008)."""
        base_args = dict(
            graham_result    = _make_result(50),
            quality_result   = _make_result(50, roe=12),
            momentum_result  = _make_result(50),
            piotroski_result = {"f_score": 5, "f_score_max": 9},
            risk_result      = {"risk_score": 50, "risk_score_max": 100, "risk_criteria": []},
            altman_result    = {"risk_score": 50, "zone": "grey"},
            buffett_result   = _make_result(50),
        )
        without_gb = scorer.enhanced_composite(**base_args)
        gb = {"earnings_yield": 99.0, "roic": 99.0, "fcf_yield": 99.0, "magic_score": None}
        with_gb = scorer.enhanced_composite(**base_args, greenblatt_result=gb)
        assert math.isclose(
            without_gb["composite_score"], with_gb["composite_score"]
        ), "fcf_yield must not affect composite_score"


if __name__ == "__main__":
    import pytest as _pytest
    _pytest.main([__file__, "-v"])
