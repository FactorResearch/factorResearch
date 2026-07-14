import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from codes.models import fraud_dashboard


def test_dashboard_aggregates_forensic_models():
    result = fraud_dashboard.build(
        accounting_quality_result={
            "accounting_quality_score": 35,
            "warning_flags": ["aggressive_accruals", "inventory_build"],
        },
        beneish_result={
            "m_score": -1.5,
            "risk_score": 82,
            "risk_label": "High",
            "stressed_indices": ["DSRI", "TATA"],
        },
        dechow_result={
            "f_score": 74,
            "risk_label": "High",
            "flags": ["share_issuance"],
        },
    )
    assert result["fraud_risk_level"] == "High"
    assert result["red_flag_count"] >= 4
    assert result["dechow_f_score"] == 74

