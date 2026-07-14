import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from codes.models import beneish


def _recs(values):
    return [{"value": v} for v in values]


def test_beneish_full_inputs_flags_elevated_risk_case():
    sec = {
        "revenue": _recs([1200, 1000]),
        "receivables": _recs([180, 100]),
        "gross_profit": _recs([420, 400]),
        "cur_ast": _recs([520, 420]),
        "ppe_net": _recs([260, 250]),
        "marketable_securities": _recs([20, 20]),
        "total_assets": _recs([1000, 900]),
        "depreciation": _recs([12, 20]),
        "sga_expense": _recs([180, 120]),
        "cur_lib": _recs([240, 180]),
        "lt_debt": _recs([220, 160]),
        "income_from_continuing_operations": _recs([120]),
        "op_cf": _recs([35]),
    }

    result = beneish.score(sec)

    assert result["n_available"] == 8
    assert result["likely_manipulator"] is True
    assert result["signal"] == "ELEVATED_MANIPULATION_RISK"
    assert result["risk_label"] == "High"
    assert result["m_score"] > -1.78


def test_beneish_partial_inputs_still_returns_partial_score_for_legacy_rows():
    sec = {
        "revenue": _recs([1200, 1000]),
        "gross_profit": _recs([550, 500]),
        "cur_ast": _recs([500, 460]),
        "ppe_net": _recs([260, 255]),
        "total_assets": _recs([1000, 950]),
        "cur_lib": _recs([220, 210]),
        "lt_debt": _recs([180, 170]),
        "net_inc": _recs([110]),
        "op_cf": _recs([120]),
    }

    result = beneish.score(sec)

    assert result["m_score"] is not None
    assert result["n_available"] < 8
    assert result["available_fraction"] < 1.0
    assert "Partial Beneish coverage" in result["note"]
    assert result["signal"] in {"LOW_MANIPULATION_RISK", "WATCH", "ELEVATED_MANIPULATION_RISK"}
