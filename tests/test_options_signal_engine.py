"""
Tests for Options Signal Engine (PROJECT_MAP.md P4 — Options Layer).

Covers:
  1. Directional bias (CALL/PUT/NEUTRAL) from regime + momentum
  2. IV regime classification (level + trend)
  3. Expected move sizing
  4. Strike/expiry recommendation direction
  5. Risk score (theta + IV + liquidity)
  6. Edge score and IV-favorability weighting
  7. get_options_signal() output schema and edge cases
"""

import math
import sys
import os
from datetime import date, timedelta

import pandas as pd
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from codes.models.options_signal_engine import (
    OptionsSignalEngine,
    calc_momentum,
    calc_monthly_volatility,
    _norm_momentum,
    _signal,
)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _hist(closes):
    dates = pd.date_range("2024-01-01", periods=len(closes), freq="MS")
    return pd.DataFrame({"Date": dates, "Close": closes})


def _hist_with_adj(closes, adj_closes):
    dates = pd.date_range("2024-01-01", periods=len(closes), freq="MS")
    return pd.DataFrame({"Date": dates, "Close": closes, "AdjClose": adj_closes})


def _rising(n=12, start=100.0, pct=1.02):
    prices = [start]
    for _ in range(n - 1):
        prices.append(prices[-1] * pct)
    return prices


def _falling(n=12, start=100.0, pct=0.98):
    prices = [start]
    for _ in range(n - 1):
        prices.append(prices[-1] * pct)
    return prices


def _contract(
    symbol,
    option_type,
    strike,
    days,
    *,
    iv=0.30,
    bid=2.0,
    ask=2.2,
    volume=250,
    open_interest=1200,
):
    expiration = date.today() + timedelta(days=days)
    mid = (bid + ask) / 2 if bid is not None and ask is not None else None
    spread_pct = ((ask - bid) / mid) if mid else None
    return {
        "contract_symbol": symbol,
        "option_type": option_type,
        "expiration_date": expiration.isoformat(),
        "days_to_expiry": days,
        "strike": strike,
        "bid": bid,
        "ask": ask,
        "mid": mid,
        "spread_pct": spread_pct,
        "last_price": mid,
        "volume": volume,
        "open_interest": open_interest,
        "implied_volatility": iv,
        "contract_size": "REGULAR",
        "contract_multiplier": 100,
        "currency": "USD",
        "in_the_money": False,
        "last_trade_at": None,
        "updated_at": None,
    }


def _chain(contracts, *, symbol="TEST", status="AVAILABLE"):
    return {
        "symbol": symbol,
        "provider": "FINNHUB",
        "status": status,
        "fetched_at": "2026-07-11T14:30:00+00:00",
        "exchange": "OPRA",
        "contract_count": len(contracts),
        "contracts": contracts,
        "error": None,
    }


def _rich_chain():
    contracts = []
    for strike in (95, 100, 105, 110):
        contracts.append(_contract(
            f"TEST30C{strike}", "CALL", strike, 30,
            iv=0.28, bid=max(0.5, 6 - (strike - 100) * 0.4),
            ask=max(0.7, 6.2 - (strike - 100) * 0.4),
        ))
    for strike in (90, 95, 100, 105):
        contracts.append(_contract(
            f"TEST30P{strike}", "PUT", strike, 30,
            iv=0.29, bid=max(0.5, 4 + (strike - 100) * 0.35),
            ask=max(0.7, 4.2 + (strike - 100) * 0.35),
        ))
    return _chain(contracts)


# ══════════════════════════════════════════════════════════════════════════════
# 1. Pure helpers
# ══════════════════════════════════════════════════════════════════════════════

class TestCalcMomentum:
    def test_rising_series_positive(self):
        m = calc_momentum(_hist(_rising(6)))
        assert m is not None and m > 0

    def test_falling_series_negative(self):
        m = calc_momentum(_hist(_falling(6)))
        assert m is not None and m < 0

    def test_insufficient_history_returns_none(self):
        assert calc_momentum(_hist([100, 102]), lookback_months=3) is None

    def test_none_input_returns_none(self):
        assert calc_momentum(None) is None

    def test_adjclose_preferred_for_momentum(self):
        # Raw Close simulates a split artifact; AdjClose shows true economic rise.
        m = calc_momentum(
            _hist_with_adj(
                [100, 102, 104, 106, 10, 11],
                [100, 102, 104, 106, 108, 110],
            ),
            lookback_months=3,
        )
        assert m is not None and m > 0


class TestNormMomentum:
    def test_plus_20_gives_100(self):
        assert _norm_momentum(0.20) == pytest.approx(100.0)

    def test_minus_20_gives_0(self):
        assert _norm_momentum(-0.20) == pytest.approx(0.0)

    def test_zero_gives_50(self):
        assert _norm_momentum(0.0) == pytest.approx(50.0)

    def test_none_gives_none(self):
        assert _norm_momentum(None) is None

    def test_extreme_clipped(self):
        assert _norm_momentum(1.0) == pytest.approx(100.0)
        assert _norm_momentum(-1.0) == pytest.approx(0.0)


class TestCalcMonthlyVolatility:
    def test_constant_prices_zero_vol(self):
        v = calc_monthly_volatility(_hist([100] * 6))
        assert v == pytest.approx(0.0, abs=1e-9)

    def test_varying_prices_positive_vol(self):
        v = calc_monthly_volatility(_hist([100, 105, 98, 110, 95, 103]))
        assert v is not None and v > 0

    def test_too_short_returns_none(self):
        assert calc_monthly_volatility(_hist([100, 101])) is None

    def test_none_returns_none(self):
        assert calc_monthly_volatility(None) is None

    def test_adjclose_preferred_for_volatility(self):
        raw_split_vol = calc_monthly_volatility(_hist([100, 102, 104, 106, 10, 11]))
        adj_vol = calc_monthly_volatility(
            _hist_with_adj(
                [100, 102, 104, 106, 10, 11],
                [100, 102, 104, 106, 108, 110],
            )
        )
        assert adj_vol is not None
        assert raw_split_vol is not None
        assert adj_vol < raw_split_vol


class TestSignalThresholds:
    def test_high_conviction_at_75(self):
        assert _signal(75) == "HIGH CONVICTION|high-conviction"
        assert _signal(100) == "HIGH CONVICTION|high-conviction"

    def test_balanced_midrange(self):
        assert _signal(45) == "BALANCED|balanced"
        assert _signal(59.9) == "BALANCED|balanced"

    def test_unfavorable_below_30(self):
        assert _signal(0) == "UNFAVORABLE|unfavorable"
        assert _signal(29.9) == "UNFAVORABLE|unfavorable"


# ══════════════════════════════════════════════════════════════════════════════
# 2. Directional bias
# ══════════════════════════════════════════════════════════════════════════════

class TestDirectionalBias:
    def test_bullish_regime_and_momentum_gives_call(self):
        eng = OptionsSignalEngine(
            "TEST", price_hist=_hist(_rising(6)),
            regime_result={"market_trend_score": 80},
        )
        bias, conf = eng.calc_directional_bias()
        assert bias == "CALL"
        assert conf > 0

    def test_bearish_regime_and_momentum_gives_put(self):
        eng = OptionsSignalEngine(
            "TEST", price_hist=_hist(_falling(6)),
            regime_result={"market_trend_score": 20},
        )
        bias, conf = eng.calc_directional_bias()
        assert bias == "PUT"
        assert conf > 0

    def test_midrange_gives_neutral(self):
        eng = OptionsSignalEngine(
            "TEST", price_hist=_hist([100] * 6),
            regime_result={"market_trend_score": 50},
        )
        bias, conf = eng.calc_directional_bias()
        assert bias == "NEUTRAL"

    def test_no_data_gives_neutral_zero_confidence(self):
        eng = OptionsSignalEngine("TEST")
        bias, conf = eng.calc_directional_bias()
        assert bias == "NEUTRAL"
        assert conf == 0.0

    def test_only_regime_available_still_works(self):
        eng = OptionsSignalEngine("TEST", regime_result={"market_trend_score": 90})
        bias, conf = eng.calc_directional_bias()
        assert bias == "CALL"
        assert conf > 0

    def test_only_momentum_available_still_works(self):
        eng = OptionsSignalEngine("TEST", price_hist=_hist(_rising(6, pct=1.05)))
        bias, conf = eng.calc_directional_bias()
        assert bias in ("CALL", "NEUTRAL")


# ══════════════════════════════════════════════════════════════════════════════
# 3. IV regime
# ══════════════════════════════════════════════════════════════════════════════

class TestIvRegime:
    def test_high_iv_level(self):
        eng = OptionsSignalEngine("TEST", regime_result={"volatility_percentile": 90})
        level, _ = eng.calc_iv_regime()
        assert level == "HIGH"

    def test_low_iv_level(self):
        eng = OptionsSignalEngine("TEST", regime_result={"volatility_percentile": 10})
        level, _ = eng.calc_iv_regime()
        assert level == "LOW"

    def test_normal_iv_level(self):
        eng = OptionsSignalEngine("TEST", regime_result={"volatility_percentile": 50})
        level, _ = eng.calc_iv_regime()
        assert level == "NORMAL"

    def test_unknown_iv_level_when_missing(self):
        eng = OptionsSignalEngine("TEST")
        level, _ = eng.calc_iv_regime()
        assert level == "UNKNOWN"

    def test_expanding_trend(self):
        eng = OptionsSignalEngine("TEST", regime_result={"vol_20d": 30, "vol_60d": 20})
        _, trend = eng.calc_iv_regime()
        assert trend == "EXPANDING"

    def test_contracting_trend(self):
        eng = OptionsSignalEngine("TEST", regime_result={"vol_20d": 10, "vol_60d": 20})
        _, trend = eng.calc_iv_regime()
        assert trend == "CONTRACTING"

    def test_stable_trend(self):
        eng = OptionsSignalEngine("TEST", regime_result={"vol_20d": 20, "vol_60d": 20})
        _, trend = eng.calc_iv_regime()
        assert trend == "STABLE"

    def test_unknown_trend_when_missing(self):
        eng = OptionsSignalEngine("TEST")
        _, trend = eng.calc_iv_regime()
        assert trend == "UNKNOWN"

    def test_nan_vol_inputs_are_unknown_not_stable(self):
        eng = OptionsSignalEngine(
            "TEST",
            regime_result={"volatility_percentile": float("nan"), "vol_20d": float("nan"), "vol_60d": 20},
        )
        level, trend = eng.calc_iv_regime()
        assert level == "UNKNOWN"
        assert trend == "UNKNOWN"

    def test_true_contract_iv_uses_absolute_level_when_realized_vol_missing(self):
        eng = OptionsSignalEngine("TEST")
        level, trend = eng.calc_iv_regime(implied_volatility=0.60)
        assert level == "HIGH"
        assert trend == "UNKNOWN"


# ══════════════════════════════════════════════════════════════════════════════
# 4. Expected move
# ══════════════════════════════════════════════════════════════════════════════

class TestExpectedMove:
    def test_none_when_no_history(self):
        eng = OptionsSignalEngine("TEST", current_price=100.0)
        pct, dollar = eng.calc_expected_move(30)
        assert pct is None and dollar is None

    def test_positive_move_for_volatile_series(self):
        eng = OptionsSignalEngine(
            "TEST", price_hist=_hist([100, 105, 98, 110, 95, 103]),
            current_price=103.0,
        )
        pct, dollar = eng.calc_expected_move(30)
        assert pct is not None and pct > 0
        assert dollar is not None and dollar > 0

    def test_longer_horizon_scales_up_move(self):
        hist = _hist([100, 105, 98, 110, 95, 103])
        eng = OptionsSignalEngine("TEST", price_hist=hist, current_price=103.0)
        pct_30, _ = eng.calc_expected_move(30)
        pct_90, _ = eng.calc_expected_move(90)
        assert pct_90 > pct_30

    def test_zero_vol_gives_zero_move(self):
        eng = OptionsSignalEngine("TEST", price_hist=_hist([100] * 6), current_price=100.0)
        pct, dollar = eng.calc_expected_move(30)
        assert pct == pytest.approx(0.0, abs=1e-9)
        assert dollar == pytest.approx(0.0, abs=1e-6)

    def test_true_iv_expected_move_uses_annualized_sqrt_time(self):
        eng = OptionsSignalEngine("TEST", current_price=100.0)
        pct, dollar = eng.calc_expected_move(30, implied_volatility=0.30)
        expected = 0.30 * math.sqrt(30 / 365)
        assert pct == pytest.approx(expected, abs=5e-5)
        assert dollar == pytest.approx(expected * 100, abs=0.01)


# ══════════════════════════════════════════════════════════════════════════════
# 5. Strike / expiry recommendation
# ══════════════════════════════════════════════════════════════════════════════

class TestStrikeExpiryRecommendation:
    def test_call_strike_above_current_price(self):
        eng = OptionsSignalEngine("TEST", current_price=100.0)
        rec = eng.recommend_strike_expiry("CALL", move_pct=0.10, horizon_days=30)
        assert rec["strike"] > 100.0
        assert rec["expiry_days"] == 30

    def test_put_strike_below_current_price(self):
        eng = OptionsSignalEngine("TEST", current_price=100.0)
        rec = eng.recommend_strike_expiry("PUT", move_pct=0.10, horizon_days=30)
        assert rec["strike"] < 100.0

    def test_neutral_gives_atm_strike(self):
        eng = OptionsSignalEngine("TEST", current_price=100.0)
        rec = eng.recommend_strike_expiry("NEUTRAL", move_pct=0.10, horizon_days=30)
        assert rec["strike"] == pytest.approx(100.0)

    def test_missing_price_gives_none_strike(self):
        eng = OptionsSignalEngine("TEST")
        rec = eng.recommend_strike_expiry("CALL", move_pct=0.10, horizon_days=30)
        assert rec["strike"] is None

    def test_missing_move_pct_gives_atm(self):
        eng = OptionsSignalEngine("TEST", current_price=100.0)
        rec = eng.recommend_strike_expiry("CALL", move_pct=None, horizon_days=30)
        assert rec["strike"] == pytest.approx(100.0)


class TestContractSelection:
    def test_selects_matching_type_nearest_expiry_and_strike(self):
        chain = _chain([
            _contract("TEST14C100", "CALL", 100, 14),
            _contract("TEST35C105", "CALL", 105, 35),
            _contract("TEST35C110", "CALL", 110, 35),
            _contract("TEST35P095", "PUT", 95, 35),
        ])
        eng = OptionsSignalEngine("TEST", current_price=100, option_chain=chain)
        selected = eng.select_contract("CALL", target_strike=106, horizon_days=30)
        assert selected["contract_symbol"] == "TEST35C105"

    def test_liquidity_breaks_equal_strike_ties(self):
        chain = _chain([
            _contract("ILLIQUID", "CALL", 105, 30, bid=1.0, ask=2.0, volume=0, open_interest=2),
            _contract("LIQUID", "CALL", 105, 30, bid=1.45, ask=1.55, volume=500, open_interest=2000),
        ])
        eng = OptionsSignalEngine("TEST", current_price=100, option_chain=chain)
        selected = eng.select_contract("CALL", target_strike=105, horizon_days=30)
        assert selected["contract_symbol"] == "LIQUID"

    def test_equal_expiry_distance_prefers_contract_after_horizon(self):
        chain = _chain([
            _contract("TEST20C100", "CALL", 100, 20),
            _contract("TEST40C100", "CALL", 100, 40),
        ])
        eng = OptionsSignalEngine("TEST", current_price=100, option_chain=chain)
        selected = eng.select_contract("CALL", target_strike=100, horizon_days=30)
        assert selected["contract_symbol"] == "TEST40C100"

    def test_wrong_underlying_chain_is_ignored(self):
        chain = _chain([_contract("OTHER30C100", "CALL", 100, 30)], symbol="OTHER")
        eng = OptionsSignalEngine("TEST", current_price=100, option_chain=chain)
        assert eng.select_contract("CALL", target_strike=100, horizon_days=30) is None


# ══════════════════════════════════════════════════════════════════════════════
# 6. Risk score
# ══════════════════════════════════════════════════════════════════════════════

class TestRiskScore:
    def test_short_expiry_high_iv_high_risk(self):
        eng = OptionsSignalEngine("TEST")
        score = eng.calc_risk_score("HIGH", horizon_days=7)
        assert score >= 60

    def test_long_expiry_low_iv_lower_risk(self):
        eng = OptionsSignalEngine("TEST")
        score = eng.calc_risk_score("LOW", horizon_days=60)
        assert score <= 40

    def test_risk_score_bounded(self):
        eng = OptionsSignalEngine("TEST")
        for iv in ("HIGH", "NORMAL", "LOW", "UNKNOWN"):
            for days in (7, 30, 60):
                score = eng.calc_risk_score(iv, horizon_days=days)
                assert 0 <= score <= 100

    def test_underlying_risk_result_changes_risk_score(self):
        low_quality = OptionsSignalEngine(
            "TEST", risk_result={"risk_score": 20, "risk_score_max": 100}
        ).calc_risk_score("NORMAL", horizon_days=30)
        high_quality = OptionsSignalEngine(
            "TEST", risk_result={"risk_score": 90, "risk_score_max": 100}
        ).calc_risk_score("NORMAL", horizon_days=30)
        assert low_quality > high_quality

    def test_live_liquidity_changes_risk_score(self):
        liquid = _contract(
            "LIQUID", "CALL", 100, 30,
            bid=1.48, ask=1.52, volume=700, open_interest=2500,
        )
        illiquid = _contract(
            "ILLIQUID", "CALL", 100, 30,
            bid=0.50, ask=2.50, volume=0, open_interest=0,
        )
        eng = OptionsSignalEngine("TEST")
        assert eng.calc_risk_score("NORMAL", 30, illiquid) > eng.calc_risk_score("NORMAL", 30, liquid)


# ══════════════════════════════════════════════════════════════════════════════
# 7. Edge score
# ══════════════════════════════════════════════════════════════════════════════

class TestEdgeScore:
    def test_low_iv_boosts_edge(self):
        eng = OptionsSignalEngine("TEST")
        edge_low = eng.calc_edge_score(50.0, "LOW", "STABLE")
        edge_normal = eng.calc_edge_score(50.0, "NORMAL", "STABLE")
        assert edge_low > edge_normal

    def test_high_iv_reduces_edge(self):
        eng = OptionsSignalEngine("TEST")
        edge_high = eng.calc_edge_score(50.0, "HIGH", "STABLE")
        edge_normal = eng.calc_edge_score(50.0, "NORMAL", "STABLE")
        assert edge_high < edge_normal

    def test_contracting_iv_boosts_edge(self):
        eng = OptionsSignalEngine("TEST")
        edge_contract = eng.calc_edge_score(50.0, "NORMAL", "CONTRACTING")
        edge_stable = eng.calc_edge_score(50.0, "NORMAL", "STABLE")
        assert edge_contract > edge_stable

    def test_edge_bounded_0_100(self):
        eng = OptionsSignalEngine("TEST")
        edge = eng.calc_edge_score(100.0, "LOW", "CONTRACTING")
        assert 0 <= edge <= 100


# ══════════════════════════════════════════════════════════════════════════════
# 8. get_options_signal() — schema & integration
# ══════════════════════════════════════════════════════════════════════════════

class TestGetOptionsSignal:
    REQUIRED_KEYS = {
        "ticker", "bias", "bias_confidence", "iv_level", "iv_trend",
        "implied_volatility", "iv_vs_realized_ratio",
        "vol_proxy_level", "vol_proxy_trend", "volatility_source", "iv_source",
        "expected_move_source", "expected_move_pct", "expected_move_dollar",
        "target_horizon_days", "recommended_strike", "recommended_expiry_days",
        "recommended_expiration_date", "recommended_contract_symbol",
        "contract_role", "selected_contract", "chain_provider", "chain_status",
        "chain_fetched_at", "contract_count", "liquidity_risk",
        "selected_contract_analytics", "pricing_assumptions",
        "strategy_candidates", "strategy_count", "top_strategy",
        "recommended_strategy", "strategy_signal", "strategy_ranking_method",
        "calibration_status", "event_risk", "event_coverage",
        "event_entry_suppressed", "event_suppression_reasons",
        "greeks", "breakevens", "max_loss", "max_profit",
        "max_profit_unbounded", "expected_value_risk_neutral",
        "probability_profit_risk_neutral",
        "risk_score", "edge_score", "signal",
        "data_quality_score", "total_score", "total_max",
    }

    def test_output_has_required_keys(self):
        eng = OptionsSignalEngine(
            "aapl", price_hist=_hist(_rising(6)),
            regime_result={"market_trend_score": 75, "volatility_percentile": 20,
                           "vol_20d": 15, "vol_60d": 20},
            current_price=150.0,
        )
        out = eng.get_options_signal()
        assert self.REQUIRED_KEYS == set(out.keys())

    def test_ticker_uppercased(self):
        eng = OptionsSignalEngine("aapl")
        out = eng.get_options_signal()
        assert out["ticker"] == "AAPL"

    def test_neutral_bias_gives_no_trade(self):
        eng = OptionsSignalEngine("TEST", regime_result={"market_trend_score": 50},
                                  price_hist=_hist([100] * 6))
        out = eng.get_options_signal()
        assert out["bias"] == "NEUTRAL"
        assert out["signal"] == "NO_TRADE"

    def test_strong_bullish_low_iv_gives_high_conviction_call(self):
        eng = OptionsSignalEngine(
            "TEST", price_hist=_hist(_rising(6, pct=1.05)),
            regime_result={"market_trend_score": 90, "volatility_percentile": 10,
                           "vol_20d": 10, "vol_60d": 20},
            current_price=120.0,
        )
        out = eng.get_options_signal()
        assert out["bias"] == "CALL"
        assert out["signal"] == "HIGH_CONVICTION_CALL"

    def test_strong_bearish_gives_high_conviction_put(self):
        eng = OptionsSignalEngine(
            "TEST", price_hist=_hist(_falling(6, pct=0.95)),
            regime_result={"market_trend_score": 10, "volatility_percentile": 10,
                           "vol_20d": 10, "vol_60d": 20},
            current_price=80.0,
        )
        out = eng.get_options_signal()
        assert out["bias"] == "PUT"
        assert out["signal"] == "HIGH_CONVICTION_PUT"

    def test_total_score_equals_edge_score(self):
        eng = OptionsSignalEngine("TEST")
        out = eng.get_options_signal()
        assert out["total_score"] == out["edge_score"]
        assert out["total_max"] == 100.0

    def test_no_data_does_not_crash(self):
        eng = OptionsSignalEngine("X")
        try:
            out = eng.get_options_signal()
        except Exception as exc:
            pytest.fail(f"get_options_signal raised {type(exc).__name__}: {exc}")
        assert out["bias"] == "NEUTRAL"
        assert out["signal"] == "NO_TRADE"
        assert math.isfinite(out["risk_score"])
        assert math.isfinite(out["edge_score"])
        assert math.isfinite(out["data_quality_score"])

    def test_custom_horizon_reflected_in_expiry(self):
        eng = OptionsSignalEngine("TEST", current_price=100.0,
                                  price_hist=_hist([100, 102, 99, 105, 101, 103]))
        out = eng.get_options_signal(horizon_days=60)
        assert out["recommended_expiry_days"] == 60

    def test_output_exposes_realized_vol_proxy_source(self):
        eng = OptionsSignalEngine("TEST")
        out = eng.get_options_signal()
        assert out["volatility_source"] == "REALIZED_VOL_PROXY"
        assert out["iv_source"] == "REALIZED_VOL_PROXY"
        assert out["implied_volatility"] is None
        assert out["strategy_candidates"] == []
        assert out["top_strategy"] is None
        assert out["greeks"] is None

    def test_data_quality_higher_when_inputs_available(self):
        empty = OptionsSignalEngine("TEST").get_options_signal()["data_quality_score"]
        full = OptionsSignalEngine(
            "TEST",
            price_hist=_hist(_rising(6)),
            regime_result={"market_trend_score": 80, "volatility_percentile": 40, "vol_20d": 15, "vol_60d": 20},
            risk_result={"risk_score": 70, "risk_score_max": 100},
        ).get_options_signal()["data_quality_score"]
        assert full > empty

    def test_live_chain_replaces_proxy_iv_and_theoretical_contract(self):
        contract = _contract("TEST30C105", "CALL", 105, 30, iv=0.32)
        eng = OptionsSignalEngine(
            "TEST",
            price_hist=_hist([100, 108, 97, 111, 99, 104]),
            regime_result={
                "market_trend_score": 90,
                "volatility_percentile": 10,
                "vol_20d": 10,
                "vol_60d": 20,
            },
            risk_result={"risk_score": 70, "risk_score_max": 100},
            current_price=100,
            option_chain=_chain([contract]),
        )
        out = eng.get_options_signal(horizon_days=30)
        assert out["iv_source"] == "FINNHUB_OPTION_CHAIN"
        assert out["volatility_source"] == "FINNHUB_OPTION_CHAIN"
        assert out["expected_move_source"] == "IMPLIED_VOLATILITY"
        assert out["implied_volatility"] == pytest.approx(0.32)
        assert out["vol_proxy_level"] == "LOW"
        assert out["iv_trend"] == "UNKNOWN"
        assert out["recommended_contract_symbol"] == "TEST30C105"
        assert out["recommended_strike"] == pytest.approx(105)
        assert out["recommended_expiry_days"] == 30
        assert out["selected_contract"]["bid"] == pytest.approx(2.0)
        assert out["selected_contract"]["open_interest"] == 1200

    def test_chain_without_contract_iv_keeps_proxy_source(self):
        contract = _contract("TEST30C100", "CALL", 100, 30, iv=None)
        out = OptionsSignalEngine(
            "TEST",
            current_price=100,
            regime_result={"market_trend_score": 90, "volatility_percentile": 10},
            option_chain=_chain([contract]),
        ).get_options_signal()
        assert out["selected_contract"] is not None
        assert out["iv_source"] == "REALIZED_VOL_PROXY"
        assert out["implied_volatility"] is None

    def test_stale_chain_iv_is_explicitly_labeled(self):
        contract = _contract("TEST30C100", "CALL", 100, 30, iv=0.25)
        out = OptionsSignalEngine(
            "TEST",
            current_price=100,
            regime_result={"market_trend_score": 90},
            option_chain=_chain([contract], status="STALE"),
        ).get_options_signal()
        assert out["iv_source"] == "FINNHUB_OPTION_CHAIN_STALE"
        assert out["chain_status"] == "STALE"

    def test_phase3_exposes_selected_contract_greeks_and_payoff_metrics(self):
        out = OptionsSignalEngine(
            "TEST",
            price_hist=_hist([92, 96, 94, 99, 101, 100]),
            current_price=100,
            regime_result={"market_trend_score": 85, "volatility_percentile": 45},
            risk_result={"risk_score": 70, "risk_score_max": 100, "risk_free_rate": 0.04},
            option_chain=_rich_chain(),
            dividend_yield=0.01,
        ).get_options_signal()
        analytics = out["selected_contract_analytics"]
        assert analytics["calculation_status"] == "COMPLETE"
        assert analytics["greeks"]["delta"] > 0
        assert analytics["greeks"]["theta_per_day"] < 0
        assert analytics["max_loss"] > 0
        assert len(analytics["breakevens"]) == 1
        assert analytics["expected_value_model"] == "RISK_NEUTRAL_LOGNORMAL"
        assert out["pricing_assumptions"]["risk_free_rate"] == pytest.approx(0.04)
        assert out["pricing_assumptions"]["dividend_yield"] == pytest.approx(0.01)

    def test_phase3_ranks_multiple_strategies_and_promotes_top_fields(self):
        out = OptionsSignalEngine(
            "TEST",
            price_hist=_hist([90, 93, 95, 98, 101, 104]),
            current_price=100,
            regime_result={"market_trend_score": 90, "volatility_percentile": 50},
            risk_result={"risk_score": 75, "risk_score_max": 100},
            option_chain=_rich_chain(),
        ).get_options_signal()
        assert out["strategy_count"] >= 5
        assert out["top_strategy"] == out["strategy_candidates"][0]
        assert out["recommended_strategy"] == out["top_strategy"]["strategy_type"]
        assert out["top_strategy"]["direction"] == "BULLISH"
        assert out["strategy_candidates"][0]["rank"] == 1
        assert out["total_score"] == out["top_strategy"]["ranking_score"]
        assert out["greeks"] == out["top_strategy"]["greeks"]
        assert out["max_loss"] == out["top_strategy"]["max_loss"]
        assert out["strategy_ranking_method"] == "PHASE_3_HEURISTIC_UNCALIBRATED"

    def test_strategy_signal_remains_legal_safe(self):
        out = OptionsSignalEngine(
            "TEST",
            current_price=100,
            regime_result={"market_trend_score": 10},
            option_chain=_rich_chain(),
        ).get_options_signal()
        assert all(term not in out["strategy_signal"] for term in ("BUY", "SELL", "HOLD"))


class TestPhase4EventAwareness:
    def test_event_coverage_unavailable_without_calendar(self):
        out = OptionsSignalEngine("TEST", current_price=100).get_options_signal()
        assert out["event_coverage"] == "UNAVAILABLE"
        assert out["event_entry_suppressed"] is False
        assert out["event_risk"]["risk_level"] == "UNKNOWN"

    def test_near_earnings_suppresses_directional_entry(self):
        out = OptionsSignalEngine(
            "TEST",
            price_hist=_hist(_rising(6, pct=1.05)),
            current_price=100,
            regime_result={"market_trend_score": 90},
            option_chain=_rich_chain(),
            event_calendar={"earnings_date": (date.today() + timedelta(days=2)).isoformat()},
        ).get_options_signal()
        assert out["event_coverage"] == "AVAILABLE"
        assert out["event_entry_suppressed"] is True
        assert out["signal"] == "EVENT_RISK_SUPPRESSED"
        assert out["strategy_signal"] == "EVENT_RISK_SUPPRESSED"
        assert out["total_score"] <= 39
        assert "EARNINGS within 2d" in out["event_suppression_reasons"]

    def test_ex_dividend_suppresses_near_call_entries(self):
        out = OptionsSignalEngine(
            "TEST",
            price_hist=_hist(_rising(6, pct=1.05)),
            current_price=100,
            regime_result={"market_trend_score": 90},
            option_chain=_rich_chain(),
            event_calendar={"ex_dividend_date": (date.today() + timedelta(days=1)).isoformat()},
        ).get_options_signal()
        assert out["bias"] == "CALL"
        assert out["event_entry_suppressed"] is True
        assert "EX_DIVIDEND within 1d" in out["event_suppression_reasons"]

    def test_major_macro_event_suppresses_short_window_entries(self):
        out = OptionsSignalEngine(
            "TEST",
            price_hist=_hist(_falling(6, pct=0.95)),
            current_price=100,
            regime_result={"market_trend_score": 10},
            option_chain=_rich_chain(),
            event_calendar={
                "major_macro_events": [
                    {
                        "date": (date.today() + timedelta(days=1)).isoformat(),
                        "name": "FOMC",
                        "severity": "MAJOR",
                    }
                ],
            },
        ).get_options_signal()
        assert out["bias"] == "PUT"
        assert out["event_risk"]["events"][0]["name"] == "FOMC"
        assert out["event_entry_suppressed"] is True
        assert "MACRO within 1d" in out["event_suppression_reasons"]

    def test_later_known_event_is_reported_without_suppression(self):
        out = OptionsSignalEngine(
            "TEST",
            price_hist=_hist(_rising(6, pct=1.05)),
            current_price=100,
            regime_result={"market_trend_score": 90},
            option_chain=_rich_chain(),
            event_calendar={"earnings_date": (date.today() + timedelta(days=14)).isoformat()},
        ).get_options_signal()
        assert out["event_coverage"] == "AVAILABLE"
        assert out["event_risk"]["risk_level"] == "MODERATE"
        assert out["event_entry_suppressed"] is False


class TestPhase4Calibration:
    def test_calibrated_profile_flows_to_signal_output(self):
        profile = {
            "calibration_status": "CALIBRATED",
            "thresholds": {"favorable": 50, "high_conviction": 65, "unfavorable": 35},
        }
        out = OptionsSignalEngine(
            "TEST",
            price_hist=_hist(_rising(6, pct=1.05)),
            current_price=100,
            regime_result={"market_trend_score": 90},
            option_chain=_rich_chain(),
            calibration_profile=profile,
        ).get_options_signal()
        assert out["calibration_status"] == "CALIBRATED"
        assert out["strategy_ranking_method"] == "PHASE_4_WALK_FORWARD_CALIBRATED"
        assert out["pricing_assumptions"]["calibration_status"] == "CALIBRATED"


if __name__ == "__main__":
    import pytest as _pytest
    _pytest.main([__file__, "-v"])
