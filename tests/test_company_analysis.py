from unittest.mock import patch
from codes.engine import company_analysis


def test_get_company_analysis_none_when_missing():
    with patch("codes.engine.company_analysis.db.get_analysis_entry", return_value=None):
        assert company_analysis.get_company_analysis("ZZZZ") is None


def test_get_company_analysis_none_on_error_entry():
    with patch("codes.engine.company_analysis.db.get_analysis_entry",
               return_value={"data": {"error": "no data"}, "updated_at": "x"}):
        assert company_analysis.get_company_analysis("ZZZZ") is None


def test_get_company_analysis_has_no_weighting_keys():
    fake_entry = {"data": {"name": "Acme", "sector": "Tech", "price": 10.0,
                            "market_cap": 500.0}, "updated_at": "2026-01-01"}
    with patch("codes.engine.company_analysis.db.get_analysis_entry", return_value=fake_entry), \
         patch("codes.engine.company_analysis.factor_engine.get_factor_scores", return_value={}):
        result = company_analysis.get_company_analysis("ACME")
    assert result["symbol"] == "ACME"
    assert "composite_score" not in result
    assert "weighted_score" not in result