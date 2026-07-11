"""ISSUE_030 Phase 3 pricing, payoff, and strategy-ranking tests."""

import math
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from codes.models.options_pricing import (
    analyze_debit_spread,
    analyze_long_contract,
    analyze_long_volatility,
    black_scholes_metrics,
    contract_entry_price,
    expected_option_payoff,
    terminal_probability,
)
from codes.models.options_strategy import (
    CALIBRATED_RANKING_METHOD,
    build_ranked_strategy_candidates,
    calibrate_strategy_thresholds,
)


def _contract(
    symbol,
    option_type,
    strike,
    *,
    days=365,
    iv=0.20,
    bid=5.0,
    ask=5.2,
    expiration="2027-07-11",
    volume=500,
    open_interest=2000,
):
    mid = (bid + ask) / 2.0
    return {
        "contract_symbol": symbol,
        "option_type": option_type,
        "expiration_date": expiration,
        "days_to_expiry": days,
        "strike": strike,
        "bid": bid,
        "ask": ask,
        "mid": mid,
        "spread_pct": (ask - bid) / mid,
        "last_price": mid,
        "volume": volume,
        "open_interest": open_interest,
        "implied_volatility": iv,
        "contract_multiplier": 100,
        "currency": "USD",
    }


class TestBlackScholesMetrics:
    def test_known_atm_one_year_call_values(self):
        result = black_scholes_metrics("CALL", 100, 100, 1.0, 0.20, 0.05, 0.0)
        assert result["theoretical_value"] == pytest.approx(10.4506, abs=1e-4)
        assert result["delta"] == pytest.approx(0.63683, abs=1e-5)
        assert result["gamma"] == pytest.approx(0.018762, abs=1e-6)
        assert result["vega_per_vol_point"] == pytest.approx(0.37524, abs=1e-5)
        assert result["theta_per_day"] == pytest.approx(-0.01757, abs=2e-5)
        assert result["rho_per_rate_point"] == pytest.approx(0.53232, abs=1e-5)

    def test_put_call_parity(self):
        call = black_scholes_metrics("CALL", 100, 105, 0.5, 0.25, 0.04, 0.01)
        put = black_scholes_metrics("PUT", 100, 105, 0.5, 0.25, 0.04, 0.01)
        parity = 100 * math.exp(-0.01 * 0.5) - 105 * math.exp(-0.04 * 0.5)
        assert call["theoretical_value"] - put["theoretical_value"] == pytest.approx(parity, abs=2e-6)

    def test_put_delta_is_negative(self):
        result = black_scholes_metrics("PUT", 100, 100, 1.0, 0.20, 0.05)
        assert result["delta"] == pytest.approx(-0.36317, abs=1e-5)
        assert result["rho_per_rate_point"] < 0

    @pytest.mark.parametrize("bad", [None, 0, -1, float("nan")])
    def test_invalid_volatility_returns_none(self, bad):
        assert black_scholes_metrics("CALL", 100, 100, 1, bad) is None


class TestDistributionAnalytics:
    def test_risk_neutral_payoff_matches_forward_value_of_bs_price(self):
        metrics = black_scholes_metrics("CALL", 100, 100, 0.5, 0.25, 0.04)
        payoff = expected_option_payoff("CALL", 100, 100, 0.5, 0.25, 0.04)
        assert payoff == pytest.approx(metrics["theoretical_value"] * math.exp(0.04 * 0.5), abs=2e-6)

    def test_terminal_probabilities_are_complements(self):
        above = terminal_probability(
            spot=100, threshold=110, time_years=0.5,
            volatility=0.25, drift=0.04, above=True,
        )
        below = terminal_probability(
            spot=100, threshold=110, time_years=0.5,
            volatility=0.25, drift=0.04, above=False,
        )
        assert above + below == pytest.approx(1.0)


class TestContractAndPayoffAnalytics:
    def test_entry_prices_are_conservative(self):
        contract = _contract("C", "CALL", 100, bid=4.8, ask=5.2)
        assert contract_entry_price(contract, "LONG") == (5.2, "ASK")
        assert contract_entry_price(contract, "SHORT") == (4.8, "BID")

    def test_long_call_has_greeks_breakeven_and_bounded_loss(self):
        contract = _contract("C", "CALL", 100, bid=10.3, ask=10.5)
        result = analyze_long_contract(
            contract, spot=100, risk_free_rate=0.05, dividend_yield=0,
        )
        assert result["calculation_status"] == "COMPLETE"
        assert result["breakevens"] == [pytest.approx(110.5)]
        assert result["max_loss"] == pytest.approx(1050)
        assert result["max_profit"] is None
        assert result["max_profit_unbounded"] is True
        assert result["greeks"]["delta"] > 0
        assert result["greeks"]["theta_per_day"] < 0
        assert 0 <= result["probability_profit_risk_neutral"] <= 1
        assert result["expected_value_model"] == "RISK_NEUTRAL_LOGNORMAL"

    def test_long_put_max_profit_is_bounded_at_zero_underlying(self):
        contract = _contract("P", "PUT", 100, bid=5.8, ask=6.0)
        result = analyze_long_contract(
            contract, spot=100, risk_free_rate=0.05, dividend_yield=0,
        )
        assert result["breakevens"] == [pytest.approx(94)]
        assert result["max_loss"] == pytest.approx(600)
        assert result["max_profit"] == pytest.approx(9400)
        assert result["greeks"]["delta"] < 0

    def test_bull_call_spread_payoff_is_bounded(self):
        long_call = _contract("C100", "CALL", 100, bid=5.8, ask=6.0)
        short_call = _contract("C110", "CALL", 110, bid=2.0, ask=2.2)
        result = analyze_debit_spread(
            long_call, short_call, spot=100,
            risk_free_rate=0.04, dividend_yield=0,
        )
        assert result["strategy_type"] == "BULL_CALL_SPREAD"
        assert result["net_debit"] == pytest.approx(400)
        assert result["max_loss"] == pytest.approx(400)
        assert result["max_profit"] == pytest.approx(600)
        assert result["breakevens"] == [pytest.approx(104)]
        assert len(result["legs"]) == 2
        assert result["legs"][0]["position"] == "LONG"
        assert result["legs"][1]["position"] == "SHORT"

    def test_debit_spread_rejects_debit_at_or_above_width(self):
        long_call = _contract("C100", "CALL", 100, bid=11.8, ask=12.0)
        short_call = _contract("C110", "CALL", 110, bid=1.0, ask=1.2)
        assert analyze_debit_spread(
            long_call, short_call, spot=100,
            risk_free_rate=0.04, dividend_yield=0,
        ) is None

    def test_long_straddle_has_two_breakevens_and_combined_greeks(self):
        call = _contract("C100", "CALL", 100, bid=4.9, ask=5.0)
        put = _contract("P100", "PUT", 100, bid=4.7, ask=4.8)
        result = analyze_long_volatility(
            call, put, spot=100, risk_free_rate=0.04, dividend_yield=0,
        )
        assert result["strategy_type"] == "LONG_STRADDLE"
        assert result["net_debit"] == pytest.approx(980)
        assert result["breakevens"] == [pytest.approx(90.2), pytest.approx(109.8)]
        assert result["max_loss"] == pytest.approx(980)
        assert result["greeks"]["gamma"] > 0
        assert result["greeks"]["vega_per_vol_point"] > 0


def _strategy_chain():
    expiration = "2026-08-21"
    contracts = []
    for strike, bid, ask in [
        (95, 8.0, 8.2), (100, 5.3, 5.5), (105, 3.1, 3.3), (110, 1.6, 1.8),
    ]:
        contracts.append(_contract(
            f"C{strike}", "CALL", strike, days=41, iv=0.24,
            bid=bid, ask=ask, expiration=expiration,
        ))
    for strike, bid, ask in [
        (90, 1.2, 1.4), (95, 2.4, 2.6), (100, 4.5, 4.7), (105, 7.5, 7.8),
    ]:
        contracts.append(_contract(
            f"P{strike}", "PUT", strike, days=41, iv=0.25,
            bid=bid, ask=ask, expiration=expiration,
        ))
    return contracts


class TestStrategyRanking:
    def test_builds_and_ranks_multiple_contract_and_spread_candidates(self):
        ranked = build_ranked_strategy_candidates(
            _strategy_chain(),
            spot=100,
            horizon_days=40,
            expected_move_dollar=8,
            bias="CALL",
            confidence=90,
            iv_level="NORMAL",
            risk_free_rate=0.045,
            dividend_yield=0.01,
            liquidity_risk=lambda contract: 10.0,
        )
        strategy_types = {candidate["strategy_type"] for candidate in ranked}
        assert {"LONG_CALL", "LONG_PUT", "BULL_CALL_SPREAD", "BEAR_PUT_SPREAD"} <= strategy_types
        assert len(ranked) >= 5
        assert [candidate["rank"] for candidate in ranked] == list(range(1, len(ranked) + 1))
        assert ranked == sorted(ranked, key=lambda candidate: (-candidate["ranking_score"], candidate["strategy_type"]))
        assert ranked[0]["direction"] == "BULLISH"
        assert ranked[0]["ranking_method"] == "PHASE_3_HEURISTIC_UNCALIBRATED"

    def test_neutral_low_iv_prefers_volatility_candidate(self):
        ranked = build_ranked_strategy_candidates(
            _strategy_chain(),
            spot=100,
            horizon_days=40,
            expected_move_dollar=8,
            bias="NEUTRAL",
            confidence=0,
            iv_level="LOW",
            risk_free_rate=0.045,
            dividend_yield=0,
            liquidity_risk=lambda contract: 10.0,
        )
        assert ranked[0]["direction"] == "VOLATILITY"

    def test_ranking_labels_remain_legal_safe(self):
        ranked = build_ranked_strategy_candidates(
            _strategy_chain(), spot=100, horizon_days=40,
            expected_move_dollar=8, bias="PUT", confidence=80,
            iv_level="HIGH", risk_free_rate=0.045, dividend_yield=0,
            liquidity_risk=lambda contract: 10.0,
        )
        for candidate in ranked:
            assert all(
                term not in candidate["ranking_verdict"]
                for term in ("BUY", "SELL", "HOLD")
            )

    def test_zero_liquidity_risk_scores_as_best_liquidity(self):
        ranked = build_ranked_strategy_candidates(
            _strategy_chain(), spot=100, horizon_days=40,
            expected_move_dollar=8, bias="CALL", confidence=80,
            iv_level="NORMAL", risk_free_rate=0.045, dividend_yield=0,
            liquidity_risk=lambda contract: 0.0,
        )
        assert ranked
        assert all(
            candidate["ranking_components"]["liquidity"] == 100.0
            for candidate in ranked
        )

    def test_calibration_requires_enough_walk_forward_samples(self):
        profile = calibrate_strategy_thresholds(
            [{"ranking_score": 80, "outcome_return": 0.10}],
            min_samples=5,
        )
        assert profile["calibration_status"] == "INSUFFICIENT_DATA"
        assert profile["thresholds"] is None

    def test_calibration_derives_thresholds_from_outcomes(self):
        samples = []
        for score in range(20, 95, 5):
            for _ in range(3):
                samples.append({
                    "ranking_score": score,
                    "outcome_return": 0.05 if score >= 60 else -0.03,
                })
        profile = calibrate_strategy_thresholds(samples, min_samples=20, min_bucket_samples=3)
        assert profile["calibration_status"] == "CALIBRATED"
        assert profile["ranking_method"] == CALIBRATED_RANKING_METHOD
        assert profile["thresholds"]["favorable"] >= 55
        assert profile["thresholds"]["high_conviction"] >= profile["thresholds"]["favorable"]

    def test_calibrated_profile_changes_ranking_method(self):
        profile = {
            "calibration_status": "CALIBRATED",
            "thresholds": {"favorable": 50, "high_conviction": 65, "unfavorable": 35},
        }
        ranked = build_ranked_strategy_candidates(
            _strategy_chain(), spot=100, horizon_days=40,
            expected_move_dollar=8, bias="CALL", confidence=90,
            iv_level="NORMAL", risk_free_rate=0.045, dividend_yield=0,
            liquidity_risk=lambda contract: 10.0,
            calibration_profile=profile,
        )
        assert ranked
        assert ranked[0]["ranking_method"] == CALIBRATED_RANKING_METHOD
        assert ranked[0]["calibration_status"] == "CALIBRATED"
