from codes.engine import factor_engine


def test_extract_factor_scores_skips_missing():
    result = {
        "graham": {"total_score": 70, "total_max": 100},
        "quality": None,
        "piotroski": {"f_score": 7, "f_score_max": 9},
    }
    scores = factor_engine.extract_factor_scores(result)
    assert scores["graham"] == (70, 100)
    assert scores["piotroski"] == (7, 9)
    assert "quality" not in scores


def test_extract_factor_scores_handles_zero_score():
    result = {"graham": {"total_score": 0, "total_max": 100}}
    scores = factor_engine.extract_factor_scores(result)
    assert scores["graham"] == (0, 100)  # 0 is valid, must not be droppedcompany_analysis.py 