from unittest.mock import patch
from codes.engine import user_strategy


def test_normalize_weights_sums_to_one():
    w = user_strategy.normalize_weights({"graham": 2, "quality": 2})
    assert abs(sum(w.values()) - 1.0) < 1e-9
    assert w["momentum"] == 0.0  # unset factor present, zero weight


def test_normalize_weights_all_zero_falls_back_equal():
    w = user_strategy.normalize_weights({"graham": -5})
    n = len(user_strategy.FACTOR_SOURCES)
    assert abs(w["graham"] - 1.0 / n) < 1e-9


def test_compute_weighted_score_missing_analysis():
    with patch("codes.engine.user_strategy.company_analysis.get_company_analysis", return_value=None):
        result = user_strategy.compute_weighted_score("ZZZZ")
    assert "error" in result


def test_compute_weighted_score_renormalizes_missing_factors():
    fake_analysis = {
        "symbol": "ACME", "updated_at": "2026-01-01",
        "factor_scores": {"graham": {"score": 80, "max_score": 100}},
    }
    with patch("codes.engine.user_strategy.company_analysis.get_company_analysis",
               return_value=fake_analysis), \
         patch("codes.engine.user_strategy.db.get_user_weights", return_value={}):
        result = user_strategy.compute_weighted_score("ACME", user_id="u1")
    assert result["weighted_score"] == 80.0  # only scorable factor drives the result