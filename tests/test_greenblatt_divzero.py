"""
Tests for ISSUE-001: Division by zero in Greenblatt rank_universe.

When n == 1 the denominator `2 * n - 2` equals 0.
Verifies no ZeroDivisionError is raised and the single stock scores 100.
"""

import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from codes.models import greenblatt


def _entry(symbol, ey, roic):
    return {
        "symbol":          symbol,
        "earnings_yield":  ey,
        "roic":            roic,
        "magic_score":     None,
        "magic_rank":      None,
        "ey_percentile":   None,
        "roic_percentile": None,
    }


def test_single_stock_no_division_by_zero():
    """n==1 must not raise ZeroDivisionError."""
    result = greenblatt.rank_universe([_entry("ONLY", 12.0, 30.0)])
    assert result[0]["magic_score"] == pytest.approx(100.0)


def test_single_stock_percentiles_not_none():
    """n==1 percentiles should be computed (0.0 by formula), not None or an error."""
    result = greenblatt.rank_universe([_entry("ONLY", 12.0, 30.0)])
    assert result[0]["ey_percentile"]   is not None
    assert result[0]["roic_percentile"] is not None


def test_two_stocks_no_error():
    """n==2 denominator is 2; must not raise."""
    universe = [_entry("A", 15.0, 40.0), _entry("B", 5.0, 10.0)]
    result = greenblatt.rank_universe(universe)
    scores = [s["magic_score"] for s in result if s["magic_score"] is not None]
    assert len(scores) == 2
    assert all(0 <= s <= 100 for s in scores)


def test_zero_ev_stock_excluded_no_error():
    """Stock with None earnings_yield must not cause ZeroDivisionError."""
    universe = [_entry("GOOD", 10.0, 20.0), _entry("BAD", None, 15.0)]
    result = greenblatt.rank_universe(universe)
    good = next(s for s in result if s["symbol"] == "GOOD")
    bad  = next(s for s in result if s["symbol"] == "BAD")
    assert good["magic_score"] == pytest.approx(100.0)
    assert bad["magic_score"] is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
