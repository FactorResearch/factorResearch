"""
TEST-002 — Buffett balance sheet quality sub-check.

Verifies goodwill concentration and inventory-vs-revenue growth scoring,
and that the total_score/total_max are always consistent (percentage-based
grading survives the new 8th criterion).
"""

import sys
import os

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from codes import buffett


def _rec(value, year):
    return {"value": value, "year": year}


def _base_sec(**overrides):
    sec = {
        "net_inc":   [_rec(1_000_000, 2024), _rec(900_000, 2023)],
        "equity":    [_rec(5_000_000, 2024), _rec(4_500_000, 2023)],
        "revenue":   [_rec(10_000_000, 2024), _rec(9_000_000, 2023)],
        "lt_debt":   [_rec(1_000_000, 2024)],
        "op_cf":     [_rec(1_200_000, 2024)],
        "capex":     [_rec(200_000, 2024)],
        "op_income": [_rec(1_100_000, 2024)],
        "eps":       [_rec(2.0, 2024)],
        "shares":    [_rec(500_000, 2024)],
        "cash":      [_rec(300_000, 2024)],
        "total_assets": [_rec(8_000_000, 2024)],
        "goodwill":  [],
        "inventory": [],
    }
    sec.update(overrides)
    return sec


def test_no_goodwill_no_inventory_scores_full_balance_sheet_points():
    sec = _base_sec()
    result = buffett.score(price=None, sec=sec)
    bs = next(c for c in result["criteria"] if c["label"] == "Balance Sheet Quality")
    # No goodwill (treated as 0) -> 5 pts; no inventory (asset-light) -> 5 pts
    assert bs["score"] == 10
    assert bs["max"] == 10


def test_high_goodwill_concentration_penalised():
    sec = _base_sec(goodwill=[_rec(4_000_000, 2024)])  # 50% of total_assets
    result = buffett.score(price=None, sec=sec)
    bs = next(c for c in result["criteria"] if c["label"] == "Balance Sheet Quality")
    assert bs["score"] <= 5  # goodwill component scores 0


def test_inventory_outpacing_revenue_flagged():
    sec = _base_sec(
        inventory=[_rec(2_000_000, 2024), _rec(500_000, 2023)],  # +300%
        revenue=[_rec(10_000_000, 2024), _rec(9_500_000, 2023)],  # ~+5%
    )
    result = buffett.score(price=None, sec=sec)
    bs = next(c for c in result["criteria"] if c["label"] == "Balance Sheet Quality")
    assert bs["score"] == 5  # goodwill 5 + inventory 0


def test_total_score_and_max_consistent():
    sec = _base_sec()
    result = buffett.score(price=None, sec=sec)
    assert result["total_max"] == sum(c["max"] for c in result["criteria"])
    assert result["total_score"] == sum(c["score"] for c in result["criteria"])
    assert result["total_max"] == 110  # 100 original + 10 new


def test_grade_uses_percentage_not_raw_score():
    # All criteria maxed except the new 10pt one being irrelevant to grade math —
    # verify grade threshold logic is percentage-based against the new total_max.
    sec = _base_sec()
    result = buffett.score(price=None, sec=sec)
    pct = result["total_score"] / result["total_max"] * 100
    if pct >= 75:
        assert result["grade"] == "A"
    elif pct >= 55:
        assert result["grade"] == "B"
    elif pct >= 35:
        assert result["grade"] == "C"
    else:
        assert result["grade"] == "D"
