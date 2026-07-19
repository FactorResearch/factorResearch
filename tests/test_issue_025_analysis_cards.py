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
        analysis_ui._greenblatt_card({"greenblatt": {"earnings_yield": 8.2, "roic": 17.5}}),
        analysis_ui._profitability_card({"profitability": {"profitability_score": 72, "signal": "STRONG"}}),
        analysis_ui._benchmark_bias_card({
            "spy_benchmark": {"probability_outperform": 0.64, "cagr_target": 12, "cagr_spy": 9},
            "bias": {"bias": "outperform", "confidence": 0.7},
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
        analysis_ui._comomentum_card({
            "regime": {"comomentum_percentile": 82.4},
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
    assert "analysis-divider" in first_row.className


def test_comomentum_card_explains_legacy_cache_state():
    card = analysis_ui._comomentum_card({"regime": {}})

    assert "Unavailable" in str(card)
    assert "fresh analysis" in str(card)


def test_comomentum_card_formats_percentile_and_signal():
    card = analysis_ui._comomentum_card({"regime": {"comomentum_percentile": 82.4}})

    assert "82nd pct" in str(card)
    assert "HIGH" in str(card)


def test_market_fear_card_does_not_leave_an_empty_grid_slot():
    card = analysis_ui._market_fear_card({"market_fear": {"error": "provider unavailable"}})

    assert "Market Fear Gauge" in str(card)
    assert "Unavailable" in str(card)


def test_risk_card_omits_empty_breakdown_column():
    card = analysis_ui._risk_card({
        "risk": {"n_years": 10, "sharpe": 0.8, "beta": 1.1},
    })

    rendered = str(card)
    assert "Risk & Performance — 10yr History" in rendered
    assert "Risk Score Breakdown" not in rendered
