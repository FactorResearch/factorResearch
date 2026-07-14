import os
import sys
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from codes.app_modules import analysis as stock_analysis


def _recs(values):
    return [{"value": v} for v in values]


def _sec():
    return {
        "revenue": _recs([1_200, 1_000, 900, 820, 760]),
        "receivables": _recs([90, 80]),
        "inventory": _recs([100, 95]),
        "net_inc": _recs([180, 150, 130, 120, 110]),
        "op_cf": _recs([210, 170]),
        "total_assets": _recs([1_000, 920]),
        "goodwill": _recs([80]),
        "intangible_assets": _recs([40]),
    }


def test_enrich_cached_analysis_if_needed_adds_new_model_and_persists():
    cached = {
        "symbol": "ACME",
        "name": "Acme Inc.",
        "sector": "Technology",
        "beneish": None,
        "piotroski": {"signals": [{"id": "F4", "signal": 1}]},
        "fcf_quality": {"accrual_ratio": -0.03, "total_score": 80, "total_max": 100},
        "growth_quality": {
            "rev_cagr_10y": 12.0,
            "organic_revenue_cagr_10y": 11.0,
            "total_score": 75,
            "total_max": 100,
        },
    }
    sec = _sec()

    with patch("codes.app_modules.analysis.scoring_facts_for_symbol", return_value=sec), \
         patch("codes.app_modules.analysis.db.upsert_analysis") as upsert_analysis, \
         patch("codes.app_modules.analysis.factor_engine.persist_factor_scores") as persist_scores:
        result = stock_analysis.enrich_cached_analysis_if_needed("ACME", cached)

    assert result["accounting_quality"]["accounting_quality_score"] >= 80
    assert result["accounting_quality"]["manipulation_risk"] == "Low"
    assert "beneish" in result and result["beneish"]["m_score"] is not None
    assert "dechow" in result and result["dechow"]["f_score"] is not None
    assert "fraud_dashboard" in result and result["fraud_dashboard"]["fraud_risk_score"] is not None
    upsert_analysis.assert_called_once()
    persist_scores.assert_called_once()
    persisted_payload = persist_scores.call_args.args[1]
    assert "accounting_quality" in persisted_payload


def test_enrich_cached_analysis_if_needed_builds_missing_dependencies():
    cached = {
        "symbol": "ACME",
        "name": "Acme Inc.",
        "sector": "Technology",
    }
    sec = {
        **_sec(),
        "shares": _recs([100]),
        "cur_ast": _recs([300, 260]),
        "cur_lib": _recs([120, 110]),
        "lt_debt": _recs([80, 85]),
        "tot_lib": _recs([220, 210]),
        "gross_profit": _recs([720, 590]),
        "cash": _recs([50, 45]),
        "op_income": _recs([240, 200]),
        "equity": _recs([500, 460]),
        "acquisitions": _recs([0] * 11),
        "capex": _recs([20] * 11),
    }
    sec["revenue"] = _recs([1_200, 1_000, 900, 820, 760, 700, 650, 600, 560, 520, 480])
    sec["net_inc"] = _recs([180, 150, 130, 120, 110, 100, 90, 80, 70, 60, 50])
    sec["op_cf"] = _recs([210, 170, 160, 150, 140, 130, 120, 110, 100, 90, 80])

    with patch("codes.app_modules.analysis.scoring_facts_for_symbol", return_value=sec), \
         patch("codes.app_modules.analysis.db.upsert_analysis"), \
         patch("codes.app_modules.analysis.factor_engine.persist_factor_scores") as persist_scores:
        result = stock_analysis.enrich_cached_analysis_if_needed("ACME", cached)

    assert "piotroski" in result
    assert "fcf_quality" in result
    assert "growth_quality" in result
    assert "beneish" in result
    assert "dechow" in result
    assert "accounting_quality" in result
    assert "fraud_dashboard" in result
    payload = persist_scores.call_args.args[1]
    assert {"piotroski", "fcf_quality", "growth_quality", "beneish", "accounting_quality"} <= set(payload)


def test_backfill_cached_analysis_models_updates_only_missing_rows():
    rows = {
        "MISS": {"symbol": "MISS", "name": "Missing", "sector": "Tech"},
        "DONE": {
            "symbol": "DONE",
            "accounting_quality": {"accounting_quality_score": 70},
            "beneish": {"m_score": -2.4},
            "dechow": {"f_score": 18},
        },
    }
    sec = {
        **_sec(),
        "shares": _recs([100]),
        "cur_ast": _recs([300, 260]),
        "cur_lib": _recs([120, 110]),
        "lt_debt": _recs([80, 85]),
        "tot_lib": _recs([220, 210]),
        "gross_profit": _recs([720, 590]),
        "cash": _recs([50, 45]),
        "op_income": _recs([240, 200]),
        "equity": _recs([500, 460]),
        "acquisitions": _recs([0] * 11),
        "capex": _recs([20] * 11),
    }
    sec["revenue"] = _recs([1_200, 1_000, 900, 820, 760, 700, 650, 600, 560, 520, 480])
    sec["net_inc"] = _recs([180, 150, 130, 120, 110, 100, 90, 80, 70, 60, 50])
    sec["op_cf"] = _recs([210, 170, 160, 150, 140, 130, 120, 110, 100, 90, 80])

    with patch("codes.app_modules.analysis.db.list_analysis_tickers", return_value=["MISS", "DONE"]), \
         patch("codes.app_modules.analysis.db.get_analysis", side_effect=lambda symbol: rows[symbol]), \
         patch("codes.app_modules.analysis.scoring_facts_for_symbol", return_value=sec), \
         patch("codes.app_modules.analysis.db.upsert_analysis"), \
         patch("codes.app_modules.analysis.factor_engine.persist_factor_scores"):
        updated = stock_analysis.backfill_cached_analysis_models()

    assert updated == 1
    assert "beneish" in rows["MISS"]
    assert "dechow" in rows["MISS"]
    assert "fraud_dashboard" in rows["MISS"]
    assert "accounting_quality" in rows["MISS"]
