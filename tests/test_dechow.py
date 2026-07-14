import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from codes.models import dechow


def _recs(values):
    return [{"value": v} for v in values]


def test_dechow_flags_high_misstatement_risk_case():
    sec = {
        "revenue": _recs([1200, 1000]),
        "receivables": _recs([180, 90]),
        "inventory": _recs([220, 120]),
        "total_assets": _recs([1000, 850]),
        "cash": _recs([40, 55]),
        "ppe_net": _recs([180, 220]),
        "shares": _recs([110, 100]),
        "net_inc": _recs([70, 120]),
        "op_cf": _recs([10]),
    }
    result = dechow.score(sec)
    assert result["f_score"] > 25
    assert result["risk_label"] in {"Moderate", "High"}
    assert result["n_available"] == 7


def test_dechow_partial_coverage_still_returns_score():
    sec = {
        "revenue": _recs([1200, 1000]),
        "total_assets": _recs([1000, 900]),
        "net_inc": _recs([110, 100]),
        "op_cf": _recs([120]),
    }
    result = dechow.score(sec)
    assert result["f_score"] is not None
    assert result["n_available"] < 7
    assert "Partial Dechow coverage" in result["note"]

