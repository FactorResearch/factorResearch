import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from codes.app_modules import analysis_ui


def _header(card):
    return card.children[0]


def _body(card):
    return card.children[1]


def test_issue_025_financial_health_and_altman_use_shared_scorecard_structure():
    piotroski = analysis_ui._piotroski_card({
        "piotroski": {
            "f_score": 7,
            "label": "strong",
            "interpretation": "Healthy balance sheet.",
            "signals": [
                {"category": "Profitability", "signal": 1, "id": "F1", "label": "ROA positive", "note": "Pass"},
            ],
        }
    })
    altman = analysis_ui._altman_card({
        "altman": {
            "z_score": 3.2,
            "zone": "safe",
            "zone_label": "Safe",
            "note": "Low bankruptcy risk.",
            "model": "Original",
            "n_available": 5,
            "components": {"x1_working_capital": 0.1},
        }
    })

    assert piotroski.className == "scorecard"
    assert "scorecard-header" in _header(piotroski).className
    assert "analysis-card-body" in _body(piotroski).className

    assert altman.className == "scorecard stability-card"
    assert "scorecard-header" in _header(altman).className
    assert "analysis-card-body" in _body(altman).className


def test_issue_025_growth_signal_cards_use_shared_metric_rows():
    cards = [
        analysis_ui._fcf_quality_card({
            "fcf_quality": {"fcf_quality_score": 81, "signal": "HIGH_CASH_QUALITY", "fcf": 10, "operating_cash_flow": 12, "capex": 2}
        }),
        analysis_ui._capital_allocation_card({
            "capital_allocation": {"capital_allocation_score": 77, "signal": "GOOD_ALLOCATOR", "roic": 12.1}
        }),
        analysis_ui._growth_quality_card({
            "growth_quality": {"growth_quality_score": 74, "signal": "Bullish", "rev_cagr_10y": 12.3}
        }),
        analysis_ui._factor_momentum_card({
            "factor_momentum": {"factor_momentum_score": 68, "signal": "Bullish", "return_3m": 5.2}
        }),
        analysis_ui._alternative_data_card({
            "alternative_data": {
                "alternative_data_score": 55,
                "signal": "NEUTRAL",
                "status": "STUB",
                "signals": [{"label": "Web traffic", "description": "Pending provider", "status": "STUB"}],
            }
        }),
        analysis_ui._options_signal_card({
            "options_signal": {"bias": "CALL", "signal": "FAVORABLE_CALL", "edge_score": 65, "risk_score": 40}
        }),
        analysis_ui._regime_card({
            "regime": {
                "regime": "BULL_LOW_VOL",
                "risk_level": "NORMAL",
                "market_trend_score": 70,
                "volatility_percentile": 20,
                "drawdown_depth": -4.0,
            },
            "regime_overlay": {"regime_multiplier": 1.0, "max_equity_exposure": 1.0, "adjusted_score": 62},
        }),
    ]

    for card in cards:
        assert "scorecard-header" in _header(card).className
        assert "analysis-card-body" in _body(card).className
        assert "analysis-metric-row" in str(card)


def test_issue_025_metric_rows_use_visible_divider_color():
    card = analysis_ui._fcf_quality_card({
        "fcf_quality": {"fcf_quality_score": 81, "signal": "HIGH_CASH_QUALITY", "fcf": 10}
    })
    first_row = _body(card).children[0]
    assert first_row.style["borderBottom"] == "1px solid rgba(67, 52, 90, 0.65)"


def test_options_card_switches_to_true_iv_and_chain_quote_labels():
    card = analysis_ui._options_signal_card({
        "options_signal": {
            "bias": "CALL",
            "signal": "FAVORABLE_CALL",
            "edge_score": 68,
            "risk_score": 42,
            "iv_level": "NORMAL",
            "implied_volatility": 0.284,
            "iv_vs_realized_ratio": 1.08,
            "iv_source": "FINNHUB_OPTION_CHAIN",
            "chain_provider": "FINNHUB",
            "chain_status": "AVAILABLE",
            "recommended_contract_symbol": "AAPL260821C00200000",
            "recommended_expiration_date": "2026-08-21",
            "recommended_expiry_days": 41,
            "selected_contract": {
                "bid": 4.9,
                "ask": 5.1,
                "open_interest": 2450,
                "volume": 321,
            },
        }
    })
    rendered = str(card)
    assert "Implied Volatility" in rendered
    assert "Bid / Ask" in rendered
    assert "AAPL260821C00200000" in rendered
    assert "true contract IV" in rendered
    assert "Vol Proxy Level" not in rendered


def test_options_card_displays_ranked_strategy_payoff_and_greeks():
    top_strategy = {
        "strategy_type": "BULL_CALL_SPREAD",
        "strategy_name": "Bull Call Spread",
        "ranking_score": 73,
        "net_debit": 420,
        "max_loss": 420,
        "max_profit": 580,
        "max_profit_unbounded": False,
        "breakevens": [104.2],
        "expected_value_risk_neutral": -18.5,
        "probability_profit_risk_neutral": 0.43,
        "greeks": {
            "delta": 0.31,
            "gamma": 0.012,
            "theta_per_day": -0.021,
            "vega_per_vol_point": 0.08,
        },
    }
    card = analysis_ui._options_signal_card({
        "options_signal": {
            "bias": "CALL",
            "signal": "FAVORABLE_CALL",
            "edge_score": 66,
            "risk_score": 40,
            "top_strategy": top_strategy,
            "strategy_candidates": [
                top_strategy,
                {"strategy_name": "Long Call", "ranking_score": 65},
                {"strategy_name": "Long Straddle", "ranking_score": 48},
            ],
            "pricing_assumptions": {"risk_free_rate": 0.04, "dividend_yield": 0.01},
            "calibration_status": "CALIBRATED",
            "event_risk": {
                "coverage": "AVAILABLE",
                "risk_score": 95,
                "risk_level": "HIGH",
            },
            "event_entry_suppressed": True,
            "event_suppression_reasons": ["EARNINGS within 2d"],
        }
    })
    rendered = str(card)
    assert "Bull Call Spread" in rendered
    assert "Strategy Rank" in rendered
    assert "Max Loss" in rendered
    assert "Risk-Neutral EV" in rendered
    assert "Net Delta" in rendered
    assert "BSM (European approximation)" in rendered
    assert "4.00% / 1.00%" in rendered
    assert "Calibration" in rendered
    assert "CALIBRATED" in rendered
    assert "Event Coverage" in rendered
    assert "Suppressed" in rendered
    assert "EARNINGS within 2d" in rendered
    assert "Long Call (65)" in rendered
    assert "walk-forward calibration" in rendered
    assert "New option entries are suppressed" in rendered
