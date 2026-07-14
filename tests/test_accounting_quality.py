import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from codes.models.accounting_quality import (
    AccountingQualityAnalyzer,
    _norm_accrual_ratio,
    _norm_dso_change,
    _norm_receivables_gap,
)


def _recs(values):
    return [{"value": v} for v in values]


def _sec(
    *,
    revenue=None,
    receivables=None,
    inventory=None,
    net_inc=None,
    op_cf=None,
    total_assets=None,
    goodwill=None,
    intangible_assets=None,
):
    def _r(values):
        return _recs(values) if values is not None else []

    return {
        "revenue": _r(revenue),
        "receivables": _r(receivables),
        "inventory": _r(inventory),
        "net_inc": _r(net_inc),
        "op_cf": _r(op_cf),
        "total_assets": _r(total_assets),
        "goodwill": _r(goodwill),
        "intangible_assets": _r(intangible_assets),
    }


def test_norm_helpers_cover_key_forensic_thresholds():
    assert _norm_receivables_gap(0.0) == pytest.approx(100.0)
    assert _norm_receivables_gap(25.0) == pytest.approx(0.0)
    assert _norm_dso_change(0.0) == pytest.approx(100.0)
    assert _norm_dso_change(20.0) == pytest.approx(0.0)
    assert _norm_accrual_ratio(-0.05) == pytest.approx(100.0)
    assert _norm_accrual_ratio(0.10) == pytest.approx(0.0)


def test_clean_company_scores_high_with_low_risk():
    sec = _sec(
        revenue=[1_200, 1_000, 900, 820, 760],
        receivables=[90, 80],
        inventory=[100, 95],
        net_inc=[180, 150, 130, 120, 110],
        op_cf=[210, 170],
        total_assets=[1_000, 920],
        goodwill=[80],
        intangible_assets=[40],
    )
    piotroski = {"signals": [{"id": "F4", "signal": 1}]}
    fcf_quality = {"accrual_ratio": -0.03}
    growth_quality = {"rev_cagr_10y": 12.0, "organic_revenue_cagr_10y": 11.0}

    out = AccountingQualityAnalyzer(
        "ACME",
        sec,
        piotroski_result=piotroski,
        fcf_quality_result=fcf_quality,
        growth_quality_result=growth_quality,
    ).get_accounting_quality_score()

    assert out["ticker"] == "ACME"
    assert out["accounting_quality_score"] >= 80
    assert out["accounting_grade"] in {"A", "B"}
    assert out["manipulation_risk"] == "Low"
    assert out["warning_flags"] == []


def test_warning_heavy_company_scores_poorly_and_sets_flags():
    sec = _sec(
        revenue=[1_050, 1_000, 900, 850, 800],
        receivables=[220, 120],
        inventory=[250, 120],
        net_inc=[150, 100, 160, 70, 180],
        op_cf=[20, 10],
        total_assets=[1_000, 900],
        goodwill=[250],
        intangible_assets=[250],
    )
    piotroski = {"signals": [{"id": "F4", "signal": 0}]}
    growth_quality = {"rev_cagr_10y": 14.0, "organic_revenue_cagr_10y": 6.0}

    out = AccountingQualityAnalyzer(
        "RISK",
        sec,
        piotroski_result=piotroski,
        growth_quality_result=growth_quality,
    ).get_accounting_quality_score()

    assert out["accounting_quality_score"] < 45
    assert out["manipulation_risk"] == "High"
    assert "receivables_outpacing_revenue" in out["warning_flags"]
    assert "inventory_build" in out["warning_flags"]
    assert "aggressive_accruals" in out["warning_flags"]
    assert "weak_piotroski_accrual_signal" in out["warning_flags"]


def test_reuses_existing_model_outputs_when_available():
    sec = _sec(
        revenue=[1000, 900, 850],
        net_inc=[90, 80, 75],
        op_cf=[120, 110],
        total_assets=[700, 650],
    )
    out = AccountingQualityAnalyzer(
        "CTX",
        sec,
        piotroski_result={"signals": [{"id": "F4", "signal": 0}]},
        fcf_quality_result={"accrual_ratio": 0.09},
        growth_quality_result={"rev_cagr_10y": 10.0, "organic_revenue_cagr_10y": 3.0},
    ).get_accounting_quality_score()

    assert out["accrual_ratio"] == pytest.approx(0.09)
    assert out["piotroski_accrual_confirmed"] is False
    assert out["acquisition_growth_gap"] == pytest.approx(7.0)
    assert "aggressive_accruals" in out["warning_flags"]
    assert "acquisition_fueled_growth" in out["warning_flags"]
