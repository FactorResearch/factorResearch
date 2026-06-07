"""
Tests for ISSUE-001: Margin of Safety guard in enhanced_composite.

Verifies:
1. Both Graham + Buffett MoS negative → composite capped at 44.9 → max HOLD/WEAK
2. Only Graham MoS negative → composite capped at 59.9 → no BUY, warning="graham"
3. Only Buffett MoS negative → composite capped at 59.9 → no BUY, warning="buffett"
4. Both positive → no cap, verdict can reach BUY
5. Both None (no price data) → no cap applied
6. One None + one negative → partial cap applies
"""

import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from codes import scorer


def _base_args(**overrides):
    """High-quality stock: all scores 80/100, both MoS positive by default."""
    base = dict(
        graham_result    = {"total_score": 80, "total_max": 100, "margin_of_safety":  20.0},
        quality_result   = {"total_score": 80, "total_max": 100, "roe": 20},
        momentum_result  = {"total_score": 80, "total_max": 100},
        piotroski_result = {"f_score": 8, "f_score_max": 9},
        risk_result      = {"risk_score": 80, "risk_score_max": 100, "risk_criteria": []},
        altman_result    = {"risk_score": 70, "zone": "safe"},
        buffett_result   = {"total_score": 80, "total_max": 100, "margin_of_safety":  20.0},
    )
    base.update(overrides)
    return base


# ══════════════════════════════════════════════════════════════════════════════
# Both MoS negative
# ══════════════════════════════════════════════════════════════════════════════

class TestBothMosNegative:
    def test_score_capped_at_hold_weak(self):
        """Both negative MoS → composite ≤ 44.9 → HOLD/WEAK at most."""
        args = _base_args(
            graham_result  = {"total_score": 80, "total_max": 100, "margin_of_safety": -10.0},
            buffett_result = {"total_score": 80, "total_max": 100, "margin_of_safety": -15.0},
        )
        result = scorer.enhanced_composite(**args)
        assert result["composite_score"] <= 44.9, (
            f"Both negative MoS: expected ≤ 44.9, got {result['composite_score']}"
        )

    def test_verdict_not_buy(self):
        args = _base_args(
            graham_result  = {"total_score": 80, "total_max": 100, "margin_of_safety": -5.0},
            buffett_result = {"total_score": 80, "total_max": 100, "margin_of_safety": -5.0},
        )
        result = scorer.enhanced_composite(**args)
        assert result["verdict_label"] not in ("buy", "strong-buy"), (
            f"Both negative MoS must not produce BUY/STRONG BUY: got {result['verdict_label']}"
        )

    def test_dual_mos_warning_true(self):
        args = _base_args(
            graham_result  = {"total_score": 80, "total_max": 100, "margin_of_safety": -5.0},
            buffett_result = {"total_score": 80, "total_max": 100, "margin_of_safety": -5.0},
        )
        result = scorer.enhanced_composite(**args)
        assert result["dual_mos_warning"] is True

    def test_partial_warning_none_when_both(self):
        args = _base_args(
            graham_result  = {"total_score": 80, "total_max": 100, "margin_of_safety": -5.0},
            buffett_result = {"total_score": 80, "total_max": 100, "margin_of_safety": -5.0},
        )
        result = scorer.enhanced_composite(**args)
        assert result["partial_mos_warning"] is None


# ══════════════════════════════════════════════════════════════════════════════
# Only Graham MoS negative
# ══════════════════════════════════════════════════════════════════════════════

class TestOnlyGrahamMosNegative:
    def test_score_capped_at_watch(self):
        args = _base_args(
            graham_result  = {"total_score": 80, "total_max": 100, "margin_of_safety": -10.0},
            buffett_result = {"total_score": 80, "total_max": 100, "margin_of_safety":  15.0},
        )
        result = scorer.enhanced_composite(**args)
        assert result["composite_score"] <= 59.9

    def test_verdict_not_buy(self):
        args = _base_args(
            graham_result  = {"total_score": 80, "total_max": 100, "margin_of_safety": -10.0},
            buffett_result = {"total_score": 80, "total_max": 100, "margin_of_safety":  15.0},
        )
        result = scorer.enhanced_composite(**args)
        assert result["verdict_label"] not in ("buy", "strong-buy")

    def test_partial_mos_warning_is_graham(self):
        args = _base_args(
            graham_result  = {"total_score": 80, "total_max": 100, "margin_of_safety": -10.0},
            buffett_result = {"total_score": 80, "total_max": 100, "margin_of_safety":  15.0},
        )
        result = scorer.enhanced_composite(**args)
        assert result["partial_mos_warning"] == "graham"
        assert result["dual_mos_warning"] is False


# ══════════════════════════════════════════════════════════════════════════════
# Only Buffett MoS negative
# ══════════════════════════════════════════════════════════════════════════════

class TestOnlyBuffettMosNegative:
    def test_score_capped_at_watch(self):
        args = _base_args(
            graham_result  = {"total_score": 80, "total_max": 100, "margin_of_safety":  15.0},
            buffett_result = {"total_score": 80, "total_max": 100, "margin_of_safety": -10.0},
        )
        result = scorer.enhanced_composite(**args)
        assert result["composite_score"] <= 59.9

    def test_partial_mos_warning_is_buffett(self):
        args = _base_args(
            graham_result  = {"total_score": 80, "total_max": 100, "margin_of_safety":  15.0},
            buffett_result = {"total_score": 80, "total_max": 100, "margin_of_safety": -10.0},
        )
        result = scorer.enhanced_composite(**args)
        assert result["partial_mos_warning"] == "buffett"
        assert result["dual_mos_warning"] is False


# ══════════════════════════════════════════════════════════════════════════════
# Both MoS positive → no cap
# ══════════════════════════════════════════════════════════════════════════════

class TestBothMosPositive:
    def test_no_cap_applied(self):
        args = _base_args(
            graham_result  = {"total_score": 80, "total_max": 100, "margin_of_safety": 20.0},
            buffett_result = {"total_score": 80, "total_max": 100, "margin_of_safety": 15.0},
        )
        result = scorer.enhanced_composite(**args)
        assert result["dual_mos_warning"] is False
        assert result["partial_mos_warning"] is None

    def test_verdict_can_be_buy(self):
        """High-quality stock with positive MoS on both → BUY is reachable."""
        args = _base_args(
            graham_result  = {"total_score": 80, "total_max": 100, "margin_of_safety": 20.0},
            buffett_result = {"total_score": 80, "total_max": 100, "margin_of_safety": 15.0},
        )
        result = scorer.enhanced_composite(**args)
        assert result["verdict_label"] in ("buy", "strong-buy")


# ══════════════════════════════════════════════════════════════════════════════
# Missing MoS data (None)
# ══════════════════════════════════════════════════════════════════════════════

class TestMissingMosData:
    def test_both_none_no_cap(self):
        """No MoS data on either side → no cap, no warnings."""
        args = _base_args(
            graham_result  = {"total_score": 80, "total_max": 100},
            buffett_result = {"total_score": 80, "total_max": 100},
        )
        result = scorer.enhanced_composite(**args)
        assert result["dual_mos_warning"] is False
        assert result["partial_mos_warning"] is None

    def test_graham_none_buffett_negative_partial_cap(self):
        """Graham no data + Buffett negative → partial cap on Buffett side."""
        args = _base_args(
            graham_result  = {"total_score": 80, "total_max": 100},
            buffett_result = {"total_score": 80, "total_max": 100, "margin_of_safety": -10.0},
        )
        result = scorer.enhanced_composite(**args)
        assert result["partial_mos_warning"] == "buffett"
        assert result["dual_mos_warning"] is False
        assert result["composite_score"] <= 59.9

    def test_buffett_none_graham_negative_partial_cap(self):
        """Buffett no data + Graham negative → partial cap on Graham side."""
        args = _base_args(
            graham_result  = {"total_score": 80, "total_max": 100, "margin_of_safety": -5.0},
            buffett_result = {"total_score": 80, "total_max": 100},
        )
        result = scorer.enhanced_composite(**args)
        assert result["partial_mos_warning"] == "graham"
        assert result["composite_score"] <= 59.9


# ══════════════════════════════════════════════════════════════════════════════
# Return dict shape
# ══════════════════════════════════════════════════════════════════════════════

class TestReturnShape:
    def test_new_keys_always_present(self):
        """dual_mos_warning and partial_mos_warning must always appear in output."""
        result = scorer.enhanced_composite(**_base_args())
        assert "dual_mos_warning"    in result
        assert "partial_mos_warning" in result


if __name__ == "__main__":
    import pytest as _pytest
    _pytest.main([__file__, "-v"])
