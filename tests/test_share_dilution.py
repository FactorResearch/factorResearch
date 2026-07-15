"""
Tests for ISSUE-004: Share dilution handling consistency.

Verifies:
1. piotroski.DILUTION_TOLERANCE constant exists and equals 0.01
2. graham.DILUTION_TOLERANCE constant exists and equals 0.01
3. Both constants are identical (single source of truth)
4. Piotroski F7 uses the constant (not a hardcoded 1.01)
5. F7=1 when shares grow exactly at tolerance boundary
6. F7=0 when shares grow just above tolerance
7. F7=1 when shares are flat or decrease (buyback)
"""

import sys
import os
import math
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from codes.models import graham, piotroski


# ── Helper ────────────────────────────────────────────────────────────────────

def _rec(v):
    return [{"value": v, "end": "2024-12-31"}] if v is not None else []


def _make_sec_piotroski(shares_cur, shares_prior,
                        net_inc=100_000, op_cf=80_000,
                        total_assets=1_000_000, total_assets_prior=950_000,
                        cur_ast=200_000, cur_ast_prior=180_000,
                        cur_lib=100_000, cur_lib_prior=110_000,
                        lt_debt=300_000, lt_debt_prior=350_000,
                        gross_profit=400_000, gross_profit_prior=380_000,
                        revenue=600_000, revenue_prior=580_000):
    """Minimal sec dict for piotroski.score() with two years of share data."""
    return {
        "net_inc":      [{"value": net_inc,      "end": "2024-12-31"},
                         {"value": net_inc*0.9,  "end": "2023-12-31"}],
        "op_cf":        [{"value": op_cf,        "end": "2024-12-31"}],
        "total_assets": [{"value": total_assets,       "end": "2024-12-31"},
                         {"value": total_assets_prior, "end": "2023-12-31"}],
        "cur_ast":      [{"value": cur_ast,       "end": "2024-12-31"},
                         {"value": cur_ast_prior, "end": "2023-12-31"}],
        "cur_lib":      [{"value": cur_lib,       "end": "2024-12-31"},
                         {"value": cur_lib_prior, "end": "2023-12-31"}],
        "lt_debt":      [{"value": lt_debt,       "end": "2024-12-31"},
                         {"value": lt_debt_prior, "end": "2023-12-31"}],
        "tot_lib":      [{"value": lt_debt*1.2,       "end": "2024-12-31"},
                         {"value": lt_debt_prior*1.2, "end": "2023-12-31"}],
        "shares":       [{"value": shares_cur,   "end": "2024-12-31"},
                         {"value": shares_prior, "end": "2023-12-31"}],
        "gross_profit": [{"value": gross_profit,       "end": "2024-12-31"},
                         {"value": gross_profit_prior, "end": "2023-12-31"}],
        "revenue":      [{"value": revenue,       "end": "2024-12-31"},
                         {"value": revenue_prior, "end": "2023-12-31"}],
    }


# ══════════════════════════════════════════════════════════════════════════════
# Constant existence and consistency
# ══════════════════════════════════════════════════════════════════════════════

class TestDilutionConstantExists:
    def test_piotroski_has_dilution_tolerance(self):
        assert hasattr(piotroski, "DILUTION_TOLERANCE"), \
            "piotroski.DILUTION_TOLERANCE constant is missing"

    def test_graham_has_dilution_tolerance(self):
        assert hasattr(graham, "DILUTION_TOLERANCE"), \
            "graham.DILUTION_TOLERANCE constant is missing"

    def test_constants_are_equal(self):
        assert piotroski.DILUTION_TOLERANCE == graham.DILUTION_TOLERANCE, (
            f"piotroski.DILUTION_TOLERANCE={piotroski.DILUTION_TOLERANCE} "
            f"!= graham.DILUTION_TOLERANCE={graham.DILUTION_TOLERANCE} — "
            "both files must use the same threshold"
        )

    def test_tolerance_value_is_one_percent(self):
        assert piotroski.DILUTION_TOLERANCE == pytest.approx(0.01), \
            "DILUTION_TOLERANCE should be 0.01 (1%)"


# ══════════════════════════════════════════════════════════════════════════════
# Piotroski F7 boundary tests
# ══════════════════════════════════════════════════════════════════════════════

class TestPiotroskiF7Boundary:
    def _f7(self, shares_cur, shares_prior) -> int:
        sec = _make_sec_piotroski(shares_cur=shares_cur, shares_prior=shares_prior)
        result = piotroski.score(sec)
        f7 = next(s for s in result["signals"] if s["id"] == "F7")
        return f7["signal"]

    def test_f7_passes_when_shares_flat(self):
        assert self._f7(1_000_000, 1_000_000) == 1

    def test_f7_passes_when_shares_decrease_buyback(self):
        assert self._f7(950_000, 1_000_000) == 1

    def test_f7_passes_at_exact_tolerance_boundary(self):
        # Exactly 1% growth → should still pass (<=)
        shares_prior = 1_000_000
        shares_cur   = int(shares_prior * (1 + piotroski.DILUTION_TOLERANCE))
        assert self._f7(shares_cur, shares_prior) == 1

    def test_f7_fails_just_above_tolerance(self):
        # 1.01% growth → just over the 1% threshold → dilution detected
        shares_prior = 1_000_000
        shares_cur   = int(shares_prior * (1 + piotroski.DILUTION_TOLERANCE) * 1.0001) + 1
        assert self._f7(shares_cur, shares_prior) == 0

    def test_f7_fails_clear_dilution(self):
        # 5% dilution — clearly fails
        assert self._f7(1_050_000, 1_000_000) == 0

    def test_f7_neutral_when_shares_missing(self):
        sec = _make_sec_piotroski(shares_cur=None, shares_prior=1_000_000)
        sec["shares"] = []
        result = piotroski.score(sec)
        f7 = next(s for s in result["signals"] if s["id"] == "F7")
        assert f7["signal"] == 0  # can't confirm no dilution → conservative


# ══════════════════════════════════════════════════════════════════════════════
# Tolerance value drives behaviour (not hardcoded 1.01)
# ══════════════════════════════════════════════════════════════════════════════

class TestToleranceIsNotHardcoded:
    def test_f7_note_references_tolerance(self):
        """F7 note should not contain a raw '1.01' literal."""
        sec = _make_sec_piotroski(shares_cur=1_010_000, shares_prior=1_000_000)
        result = piotroski.score(sec)
        f7 = next(s for s in result["signals"] if s["id"] == "F7")
        assert "1.01" not in f7["note"], (
            "F7 note contains hardcoded '1.01' — should reference DILUTION_TOLERANCE"
        )

    def test_f7_result_consistent_with_constant(self):
        """
        Whatever DILUTION_TOLERANCE is set to, F7 must behave consistently.
        Growth == tolerance → pass; growth == tolerance + epsilon → fail.
        """
        tol = piotroski.DILUTION_TOLERANCE
        prior = 1_000_000

        at_boundary = int(prior * (1 + tol))
        just_over   = at_boundary + 1

        sec_pass = _make_sec_piotroski(shares_cur=at_boundary, shares_prior=prior)
        sec_fail = _make_sec_piotroski(shares_cur=just_over,   shares_prior=prior)

        res_pass = piotroski.score(sec_pass)
        res_fail = piotroski.score(sec_fail)

        f7_pass = next(s for s in res_pass["signals"] if s["id"] == "F7")["signal"]
        f7_fail = next(s for s in res_fail["signals"] if s["id"] == "F7")["signal"]

        assert f7_pass == 1, f"Expected F7=1 at boundary ({at_boundary} vs {prior})"
        assert f7_fail == 0, f"Expected F7=0 just over boundary ({just_over} vs {prior})"


# ══════════════════════════════════════════════════════════════════════════════
# Graham DILUTION_TOLERANCE import is usable
# ══════════════════════════════════════════════════════════════════════════════

class TestGrahamDilutionTolerance:
    def test_graham_tolerance_is_float(self):
        assert isinstance(graham.DILUTION_TOLERANCE, float)

    def test_graham_tolerance_matches_piotroski(self):
        """Single source of truth — both must be identical at runtime."""
        assert math.isclose(graham.DILUTION_TOLERANCE,
                            piotroski.DILUTION_TOLERANCE, rel_tol=1e-9)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
