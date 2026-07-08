from unittest.mock import patch
from codes.engine import factor_snapshot


def test_snapshot_today_extracts_and_records():
    analysis = {"graham": {"total_score": 65, "total_max": 100}}
    with patch("codes.engine.factor_snapshot.db.record_factor_snapshot") as rec_mock:
        scores = factor_snapshot.snapshot_today("ACME", analysis, as_of="2026-01-15")
    assert scores["graham"] == (65, 100)
    rec_mock.assert_called_once_with("ACME", "2026-01-15", scores)


def test_get_factor_scores_asof_omits_unavailable_factors():
    def fake_get(ticker, factor_name, as_of):
        if factor_name == "graham":
            return {"score": 70, "max_score": 100, "snapshot_date": "2026-01-01"}
        return None
    with patch("codes.engine.factor_snapshot.db.get_factor_score_asof", side_effect=fake_get):
        result = factor_snapshot.get_factor_scores_asof("ACME", "2026-01-15")
    assert "graham" in result
    assert "quality" not in result  # no snapshot available — not backfilled


def test_has_sufficient_history():
    with patch("codes.engine.factor_snapshot.db.list_snapshot_dates",
               return_value=["2026-01-01", "2026-02-01"]):
        assert factor_snapshot.has_sufficient_history("ACME", min_dates=2)
    with patch("codes.engine.factor_snapshot.db.list_snapshot_dates", return_value=["2026-01-01"]):
        assert not factor_snapshot.has_sufficient_history("ACME", min_dates=2)