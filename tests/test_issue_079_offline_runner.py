from datetime import date
from decimal import Decimal

import pytest

from codes.engine.issue_079 import (
    Issue079InputError,
    Prediction,
    ValidationConfig,
    _prediction_from_row,
    demo_rows,
    run_validation,
)
from codes.workers.generate_issue_079_data import generate
from codes.workers.issue_079_randomized_trial import public_markdown, run_trials


def _row(**changes):
    values = {
        "symbol": "AAA",
        "analysis_date": date(2020, 1, 1),
        "available_at": date(2019, 12, 20),
        "execution_date": date(2020, 1, 2),
        "score": Decimal("80"),
        "signal": "Attractive",
        "start_price": Decimal("100"),
        "end_price_1y": Decimal("120"),
        "spy_start_price": Decimal("100"),
        "spy_end_price_1y": Decimal("110"),
    }
    values.update(changes)
    return Prediction(**values)


def test_demo_run_is_deterministic_and_discloses_inconclusive_status():
    config = ValidationConfig(random_sample_size=17, random_seed=123)
    first = run_validation(demo_rows(), config)
    second = run_validation(demo_rows(), config)
    assert first == second
    assert first["status"] == "inconclusive"
    assert first["run"]["random_seed"] == 123


def test_future_available_data_is_rejected_before_scoring():
    with pytest.raises(Issue079InputError, match="available after"):
        run_validation([_row(available_at=date(2020, 1, 2))])


def test_benchmark_alignment_is_required_for_each_period():
    rows = [_row(), _row(symbol="BBB", spy_end_price_1y=Decimal("111"))]
    with pytest.raises(Issue079InputError, match="benchmark prices disagree"):
        run_validation(rows)


def test_portfolio_comparison_uses_same_starting_capital_and_excludes_low_scores():
    result = run_validation([_row(), _row(symbol="BBB", score=Decimal("20"), end_price_1y=Decimal("200"))])
    period = result["portfolio_periods"][0]
    assert period["holdings"] == ["AAA"]
    assert period["factor_value"] == "11976.00"
    assert period["spy_value"] == "10978.00"


def test_model_contributions_are_reported_without_replacing_score_inputs():
    result = run_validation([_row(model_contributions=(("quality", Decimal("7.5")),))])
    assert result["model_contributions"] == {"quality": {"sample_size": 1, "average_points": 7.5}}


@pytest.mark.parametrize(
    ("scenario", "diagnosis"),
    [
        ("strong", "strong-synthetic-signal"),
        ("null", "null-or-weak-synthetic-signal"),
        ("inverted", "inverted-synthetic-signal"),
    ],
)
def test_known_synthetic_scenarios_are_diagnosed(scenario, diagnosis):
    rows = [_prediction_from_row(row) for row in generate(scenario)]
    assert run_validation(rows)["diagnostic_assessment"]["diagnosis"] == diagnosis


def test_randomized_trial_reports_uncertainty_across_seeds():
    result = run_trials(7901, 5)
    assert result["status"] == "null-market-diagnostic"
    assert result["trials"] == 5
    assert len(result["spread_95pct_confidence_interval_pct"]) == 2
    report = public_markdown(result)
    assert "Lucky and failed runs are visible" in report
    assert "What this does not prove" in report
