"""Rendering helpers for the stock analysis view and shared charts."""

from dash import dcc, html
import pandas as pd
import plotly.graph_objects as go

from .config import AMBER, BLUE, BORDER, CARD, GREEN, MUTED, RED, TEXT, WHITE, _MOAT_TOOLTIPS

def _composite_banner(data: dict) -> html.Div:
    """
    Smart composite banner: shows enhanced orthogonal composite when available,
    falls back to original 3-pillar composite for older cached results.
    """
    enhanced = data.get("enhanced") or {}
    comp     = data.get("composite") or {}
    has_enh  = bool(enhanced.get("composite_score") is not None)
    src      = enhanced if has_enh else comp
    verdict       = src.get("verdict",      "N/A")
    verdict_label = src.get("verdict_label","pending")
    verdict_desc  = src.get("verdict_desc", "")
    score         = src.get("composite_score", 0) or 0
    # Pillar list
    if has_enh:
        pillars = [
            ("IVE",    enhanced.get("graham_pct",    0), "10%"),
            ("Quality",   enhanced.get("quality_pct",   0), "18%"),
            ("Momentum",  enhanced.get("momentum_pct",  0), "10%"),
            ("Risk",      enhanced.get("risk_pct",      0), " 8%"),
            ("Altman",    enhanced.get("altman_pct",    0), " 3%"),
            ("E.Rev",     enhanced.get("earnings_revision_pct", 0), "12%"),
            ("Profit.",   enhanced.get("profitability_pct", 0), "12%"),
            ("FCF Qual.", enhanced.get("fcf_quality_pct", 0), "10%"),
            ("Cap.Alloc", enhanced.get("capital_allocation_pct", 0), " 8%"),
            ("Growth Q.", enhanced.get("growth_quality_pct", 0), " 9%"),
        ]
        score_label = "Enhanced Score"
    else:
        pillars = [
            ("Graham",   comp.get("graham_pct",   0), "40%"),
            ("Quality",  comp.get("quality_pct",  0), "35%"),
            ("Momentum", comp.get("momentum_pct") or 0, "25%"),
        ]
        score_label = "Composite"
    pillar_els = [_pillar(l, round(v) if isinstance(v, float) else v, w)
                  for l, v, w in pillars]
    pillar_els.append(html.Div([
        html.Div(f"{score:.0f}", className="pillar-value text-4xl"),
        html.Div(score_label, className="pillar-label"),
    ]))
    # Flags row
    flags = []
    if enhanced.get("value_trap_warning") or comp.get("value_trap_warning"):
        flags.append(html.Span("⚠️ Value Trap Risk",
                               style={"background": "#3a2800", "color": AMBER,
                                      "borderRadius": "6px", "padding": "3px 10px",
                                      "fontSize": "12px", "fontWeight": "600"}))
    if enhanced.get("compounder_flag"):
        flags.append(html.Span("🚀 Compounder Signal",
                               style={"background": "#003a1a", "color": GREEN,
                                      "borderRadius": "6px", "padding": "3px 10px",
                                      "fontSize": "12px", "fontWeight": "600"}))
    if enhanced.get("altman_cap_applied"):
        flags.append(html.Span("🔴 Altman Distress Cap Active",
                               style={"background": "#3a0000", "color": RED,
                                      "borderRadius": "6px", "padding": "3px 10px",
                                      "fontSize": "12px", "fontWeight": "600"}))
    if (data.get("growth_quality") or {}).get("acquisition_driven_growth"):
        flags.append(html.Span("🟠 Acquisition-Driven Growth",
                               style={"background": "#3a2000", "color": AMBER,
                                      "borderRadius": "6px", "padding": "3px 10px",
                                      "fontSize": "12px", "fontWeight": "600"}))
    return html.Div(className="composite-banner", children=[
        html.Div([
            html.Div(verdict, className="composite-banner-verdict",
                     style={"color": _verdict_color(verdict_label)}),
            html.Div(verdict_desc, className="composite-banner-desc"),
            html.Div(flags, style={"display": "flex", "gap": "8px",
                                   "flexWrap": "wrap", "marginTop": "8px"})
            if flags else html.Div(),
        ]),
        html.Div(className="pillar-scores", children=pillar_els),
    ])

def _fcf_quality_card(data: dict) -> html.Div:
    """FCF Quality card: key metrics + scorecard criteria."""
    fcf = data.get("fcf_quality") or {}
    if not fcf:
        return html.Div()

    score  = fcf.get("fcf_quality_score")
    signal = fcf.get("signal", "")
    if score is None:
        return html.Div()

    sig_color = {
        "STRONG_CASH_GENERATOR": GREEN,
        "HIGH_CASH_QUALITY":     BLUE,
        "NEUTRAL":               AMBER,
        "WEAK_CASH_QUALITY":     MUTED,
        "EARNINGS_QUALITY_RISK": RED,
    }.get(signal, MUTED)

    def _fmt(v, fmt=",.2f", prefix="", suffix=""):
        if v is None:
            return "N/A"
        try:
            return f"{prefix}{v:{fmt}}{suffix}"
        except (ValueError, TypeError):
            return "N/A"

    metrics = [
        ("FCF",              _fmt(fcf.get("fcf"), ",.0f", "$")),
        ("Operating CF",     _fmt(fcf.get("operating_cash_flow"), ",.0f", "$")),
        ("CapEx",            _fmt(fcf.get("capex"), ",.0f", "$")),
        ("FCF Margin",       _fmt(fcf.get("fcf_margin"), ".1f", suffix="%")),
        ("FCF Conversion",   _fmt(fcf.get("fcf_conversion"), ".1f", suffix="%")),
        ("FCF Stability CV", _fmt(fcf.get("fcf_stability"), ".3f")),
        ("Growth Consist.",  _fmt(fcf.get("fcf_growth_consistency"), ".0%") if fcf.get("fcf_growth_consistency") is not None else "N/A"),
        ("Accrual Ratio",    _fmt(fcf.get("accrual_ratio"), ".4f")),
        ("FCF CAGR 5yr",     _fmt(fcf.get("fcf_cagr_5y"), ".1f", suffix="%")),
    ]

    metric_rows = [
        html.Div(style={
            "display": "flex", "justifyContent": "space-between",
            "padding": "4px 0", "borderBottom": f"1px solid {BORDER}",
            "fontSize": "12px",
        }, children=[
            html.Span(lbl, className="text-muted"),
            html.Span(val, style={"color": TEXT, "fontWeight": "600"}),
        ])
        for lbl, val in metrics
    ]

    return html.Div(className="scorecard", children=[
        html.Div(style={"display": "flex", "alignItems": "center",
                        "gap": "10px", "padding": "14px 18px 10px"}, children=[
            html.Span("FCF Quality",
                      style={"fontSize": "14px", "fontWeight": "700", "color": TEXT}),
            html.Span(f"{score:.0f}/100",
                      style={"fontSize": "22px", "fontWeight": "800", "color": sig_color}),
            html.Span(f"— {signal.replace('_', ' ').title()}",
                      style={"fontSize": "13px", "color": sig_color}),
        ]),
        html.Div(metric_rows, className="px-xl pb-2xl"),
    ])
def _options_signal_card(data: dict) -> html.Div:
    """Options Signal card: directional bias, IV regime, strike/expiry, risk/edge."""
    os_data = data.get("options_signal") or {}
    if not os_data:
        return html.Div()

    bias   = os_data.get("bias", "NEUTRAL")
    signal = os_data.get("signal", "NO_TRADE")
    edge   = os_data.get("edge_score")
    risk   = os_data.get("risk_score")
    if edge is None:
        return html.Div()

    bias_color = {"CALL": GREEN, "PUT": RED, "NEUTRAL": MUTED}.get(bias, MUTED)
    sig_color = {
        "BUY_CALL": GREEN, "BUY_PUT": GREEN,
        "WATCH": AMBER, "AVOID": RED, "NO_TRADE": MUTED,
    }.get(signal, MUTED)

    def _fmt(v, fmt=".2f", prefix="", suffix=""):
        if v is None:
            return "N/A"
        try:
            return f"{prefix}{v:{fmt}}{suffix}"
        except (ValueError, TypeError):
            return "N/A"

    metrics = [
        ("Bias",             html.Span(bias, style={"color": bias_color, "fontWeight": "700"})),
        ("Confidence",       _fmt(os_data.get("bias_confidence"), ".0f", suffix="/100")),
        ("IV Level",         os_data.get("iv_level", "N/A")),
        ("IV Trend",         os_data.get("iv_trend", "N/A")),
        ("Expected Move",    _fmt((os_data.get("expected_move_pct") or 0) * 100, ".1f", suffix="%")),
        ("Expected Move $",  _fmt(os_data.get("expected_move_dollar"), ",.2f", "$")),
        ("Suggested Strike", _fmt(os_data.get("recommended_strike"), ",.2f", "$")),
        ("Expiry (days)",    str(os_data.get("recommended_expiry_days", "N/A"))),
        ("Risk Score",       _fmt(risk, ".0f", suffix="/100")),
    ]

    metric_rows = [
        html.Div(style={
            "display": "flex", "justifyContent": "space-between",
            "padding": "4px 0", "borderBottom": f"1px solid {BORDER}",
            "fontSize": "12px",
        }, children=[
            html.Span(lbl, className="text-muted"),
            html.Span(val) if not isinstance(val, str) else
            html.Span(val, style={"color": TEXT, "fontWeight": "600"}),
        ])
        for lbl, val in metrics
    ]

    return html.Div(className="scorecard", children=[
        html.Div(style={"display": "flex", "alignItems": "center",
                        "gap": "10px", "padding": "14px 18px 10px"}, children=[
            html.Span("Options Signal",
                      style={"fontSize": "14px", "fontWeight": "700", "color": TEXT}),
            html.Span(f"{edge:.0f}/100",
                      style={"fontSize": "22px", "fontWeight": "800", "color": sig_color}),
            html.Span(f"— {signal.replace('_', ' ').title()}",
                      style={"fontSize": "13px", "color": sig_color}),
        ]),
        html.Div(
            "Models short-horizon option mark-to-market movement, not expiry payoff.",
            style={"fontSize": "11px", "color": MUTED, "padding": "0 18px 8px",
                   "fontStyle": "italic"},
        ),
        html.Div(metric_rows, className="px-xl pb-2xl"),
    ])

def _capital_allocation_card(data: dict) -> html.Div:
    """Capital Allocation card: key metrics display."""
    ca = data.get("capital_allocation") or {}
    if not ca:
        return html.Div()

    score  = ca.get("capital_allocation_score")
    signal = ca.get("signal", "")
    if score is None:
        return html.Div()

    sig_color = {
        "EXCELLENT_ALLOCATOR": GREEN,
        "GOOD_ALLOCATOR":      BLUE,
        "AVERAGE_ALLOCATOR":   AMBER,
        "POOR_ALLOCATOR":      MUTED,
        "CAPITAL_DESTROYER":   RED,
    }.get(signal, MUTED)

    def _fmt(v, fmt=".2f", prefix="", suffix=""):
        if v is None:
            return "N/A"
        try:
            return f"{prefix}{v:{fmt}}{suffix}"
        except (ValueError, TypeError):
            return "N/A"

    roic_spread_color = GREEN if (ca.get("roic_spread") or 0) > 0 else RED
    dilution_color    = GREEN if (ca.get("dilution_rate") or 1) <= 0 else (
        AMBER if (ca.get("dilution_rate") or 0) < 3 else RED
    )
    debt_color        = GREEN if (ca.get("debt_trend") or 1) <= 0 else AMBER

    metrics = [
        ("ROIC",              _fmt(ca.get("roic"), ".1f", suffix="%")),
        ("ROIC Spread (−10%)", html.Span(_fmt(ca.get("roic_spread"), "+.1f", suffix="%"),
                                          style={"color": roic_spread_color, "fontWeight": "600"})),
        ("Incremental ROIC",  _fmt(ca.get("incremental_roic"), ".1f", suffix="%")),
        ("Reinvestment Rate", _fmt(ca.get("reinvestment_rate"), ".1%") if ca.get("reinvestment_rate") is not None else "N/A"),
        ("Reinvest Method",   ca.get("reinvestment_method", "N/A")),
        ("Buyback Yield",     _fmt(ca.get("buyback_yield"), ".2f", suffix="%")),
        ("Dividend Yield",    _fmt(ca.get("dividend_yield_implied"), ".2f", suffix="%")),
        ("Shareholder Yield", _fmt(ca.get("shareholder_yield"), ".2f", suffix="%")),
        ("Dilution Rate",     html.Span(_fmt(ca.get("dilution_rate"), "+.2f", suffix="%"),
                                         style={"color": dilution_color, "fontWeight": "600"})),
        ("Debt Trend (Δ D/E)", html.Span(_fmt(ca.get("debt_trend"), "+.3f"),
                                           style={"color": debt_color, "fontWeight": "600"})),
    ]

    metric_rows = [
        html.Div(style={
            "display": "flex", "justifyContent": "space-between",
            "padding": "4px 0", "borderBottom": f"1px solid {BORDER}",
            "fontSize": "12px",
        }, children=[
            html.Span(lbl if isinstance(lbl, str) else lbl, className="text-muted"),
            html.Span(val) if isinstance(val, str) else val,
        ])
        for lbl, val in metrics
    ]

    return html.Div(className="scorecard", children=[
        html.Div(style={"display": "flex", "alignItems": "center",
                        "gap": "10px", "padding": "14px 18px 10px"}, children=[
            html.Span("Capital Allocation",
                      style={"fontSize": "14px", "fontWeight": "700", "color": TEXT}),
            html.Span(f"{score:.0f}/100",
                      style={"fontSize": "22px", "fontWeight": "800", "color": sig_color}),
            html.Span(f"— {signal.replace('_', ' ').title()}",
                      style={"fontSize": "13px", "color": sig_color}),
        ]),
        html.Div(metric_rows, className="px-xl pb-2xl"),
    ])


def _growth_quality_card(data: dict) -> html.Div:
    """Growth Quality card: 10-year growth quality and reinvestment durability."""
    gq = data.get("growth_quality") or {}
    if not gq:
        return html.Div()

    score = gq.get("growth_quality_score")
    signal = gq.get("signal", "Neutral")
    if score is None:
        return html.Div()

    sig_color = {
        "Bullish": GREEN,
        "Neutral": AMBER,
        "Bearish": RED,
    }.get(signal, MUTED)

    def _fmt(v, decimals=1, suffix="%"):
        return f"{v:.{decimals}f}{suffix}" if v is not None else "N/A"

    metrics = [
        ("Revenue CAGR 10Y", _fmt(gq.get("rev_cagr_10y"))),
        ("EPS CAGR 10Y", _fmt(gq.get("eps_cagr_10y"))),
        ("FCF CAGR 10Y", _fmt(gq.get("fcf_cagr_10y"))),
        ("Margin Stability", _fmt(gq.get("margin_stability"), 2, " pp")),
        ("Incremental ROIC", _fmt(gq.get("incremental_roic"))),
        ("Reinvestment Efficiency", _fmt(gq.get("reinvestment_efficiency"), 2, "")),
        ("Organic Rev CAGR 10Y", _fmt(gq.get("organic_revenue_cagr_10y"))),
    ]   

    metric_rows = [
        html.Div(style={
            "display": "flex", "justifyContent": "space-between",
            "padding": "4px 0", "borderBottom": f"1px solid {BORDER}",
            "fontSize": "12px",
        }, children=[
            html.Span(lbl, className="text-muted"),
            html.Span(val, style={"color": TEXT, "fontWeight": "600"}),
        ])
        for lbl, val in metrics
    ]

    return html.Div(className="scorecard", children=[
        html.Div(style={"display": "flex", "alignItems": "center",
                        "gap": "10px", "padding": "14px 18px 10px"}, children=[
            html.Span("Growth Quality",
                      style={"fontSize": "14px", "fontWeight": "700", "color": TEXT}),
            html.Span(f"{score:.0f}/100",
                      style={"fontSize": "22px", "fontWeight": "800", "color": sig_color}),
            html.Span(f"\u2014 {signal}",
                      style={"fontSize": "13px", "color": sig_color}),
        ]),
        html.Div(metric_rows, className="px-xl pb-2xl"),
    ])


def _insider_activity_card(data: dict) -> html.Div:
    """Insider buying/selling activity card."""
    ia = data.get("insider_activity") or {}
    if not ia or ia.get("low_coverage"):
        return html.Div()
    score  = ia.get("insider_confidence_score")
    signal = ia.get("signal", "NEUTRAL")
    if score is None:
        return html.Div()
    sig_color = {"BULLISH": GREEN, "NEUTRAL": AMBER, "BEARISH": RED}.get(signal, MUTED)

    def _fmt(v, fmt=".2f", suffix=""):
        return f"{v:{fmt}}{suffix}" if v is not None else "N/A"

    cluster_txt = "\u2705 Detected" if ia.get("cluster_detected") else "\u2014"
    metrics = [
        ("Net Insider Buying",  _fmt(ia.get("net_insider_buying"),  "+.2f", "%")),
        ("Cluster Buying",      cluster_txt),
        ("Type Quality Score",  _fmt(ia.get("insider_type_quality"), ".1f", "/100")),
        ("Buy Transactions",    str(ia.get("n_buy_transactions",  0))),
        ("Sell Transactions",   str(ia.get("n_sell_transactions", 0))),
        ("Distinct Buyers",     str(ia.get("n_distinct_buyers",   0))),
    ]
    rows = [
        html.Div(style={
            "display": "flex", "justifyContent": "space-between",
            "padding": "4px 0", "borderBottom": f"1px solid {BORDER}", "fontSize": "12px",
        }, children=[
            html.Span(lbl, className="text-muted"),
            html.Span(val, style={"color": TEXT, "fontWeight": "600"}),
        ])
        for lbl, val in metrics
    ]
    return html.Div(className="scorecard", children=[
        html.Div(style={
            "display": "flex", "alignItems": "center",
            "gap": "10px", "padding": "14px 18px 10px",
        }, children=[
            html.Span("Insider Activity",
                      style={"fontSize": "14px", "fontWeight": "700", "color": TEXT}),
            html.Span(f"{score:.0f}/100",
                      style={"fontSize": "22px", "fontWeight": "800", "color": sig_color}),
            html.Span(f"\u2014 {signal}",
                      style={"fontSize": "13px", "color": sig_color}),
        ]),
        html.Div(rows, className="px-xl pb-2xl"),
    ])


def _factor_momentum_card(data: dict) -> html.Div:
    """Factor Momentum card: price momentum plus fundamental trend signals."""
    fm = data.get("factor_momentum") or {}
    if not fm:
        return html.Div()

    score = fm.get("factor_momentum_score")
    signal = fm.get("signal", "Neutral")
    if score is None:
        return html.Div()

    sig_color = {
        "Bullish": GREEN,
        "Neutral": AMBER,
        "Bearish": RED,
    }.get(signal, MUTED)

    def _fmt(v, decimals=1, suffix="%"):
        return f"{v:.{decimals}f}{suffix}" if v is not None else "N/A"

    metrics = [
        ("3M Return", _fmt(fm.get("return_3m"))),
        ("6M Return", _fmt(fm.get("return_6m"))),
        ("12M Return", _fmt(fm.get("return_12m"))),
        ("Earnings Momentum", _fmt(fm.get("earnings_momentum"))),
        ("ROIC Trend Slope", _fmt(fm.get("roic_trend_slope"), 2, " pp/yr")),
    ]

    metric_rows = [
        html.Div(style={
            "display": "flex", "justifyContent": "space-between",
            "padding": "4px 0", "borderBottom": f"1px solid {BORDER}", "fontSize": "12px",
        }, children=[
            html.Span(lbl, className="text-muted"),
            html.Span(val, style={"color": TEXT, "fontWeight": "600"}),
        ])
        for lbl, val in metrics
    ]

    return html.Div(className="scorecard", children=[
        html.Div(style={
            "display": "flex", "alignItems": "center",
            "gap": "10px", "padding": "14px 18px 10px",
        }, children=[
            html.Span("Factor Momentum",
                      style={"fontSize": "14px", "fontWeight": "700", "color": TEXT}),
            html.Span(f"{score:.0f}/100",
                      style={"fontSize": "22px", "fontWeight": "800", "color": sig_color}),
            html.Span(f"\u2014 {signal}",
                      style={"fontSize": "13px", "color": sig_color}),
        ]),
        html.Div(metric_rows, className="px-xl pb-2xl"),
    ])


def _alternative_data_card(data: dict) -> html.Div:
    """Alternative Data card: provider-ready Phase E signals."""
    ad = data.get("alternative_data") or {}
    if not ad:
        return html.Div()

    score = ad.get("alternative_data_score")
    signal = ad.get("signal", "NEUTRAL")
    status = ad.get("status", "STUB")
    if score is None:
        return html.Div()

    sig_color = {"BULLISH": GREEN, "NEUTRAL": AMBER, "BEARISH": RED}.get(signal, MUTED)
    signals = ad.get("signals") or []

    rows = [
        html.Div(style={
            "display": "flex", "justifyContent": "space-between",
            "gap": "12px", "padding": "5px 0", "borderBottom": f"1px solid {BORDER}",
            "fontSize": "12px",
        }, children=[
            html.Div([
                html.Div(s.get("label", s.get("name", "Signal")),
                         style={"color": TEXT, "fontWeight": "600"}),
                html.Div(s.get("description", ""),
                         style={"color": MUTED, "fontSize": "11px", "marginTop": "1px"}),
            ]),
            html.Span(s.get("status", status),
                      style={"color": MUTED, "fontWeight": "700", "whiteSpace": "nowrap"}),
        ])
        for s in signals
    ]

    return html.Div(className="scorecard", children=[
        html.Div(style={
            "display": "flex", "alignItems": "center",
            "gap": "10px", "padding": "14px 18px 10px",
        }, children=[
            html.Span("Alternative Data",
                      style={"fontSize": "14px", "fontWeight": "700", "color": TEXT}),
            html.Span(f"{score:.0f}/100",
                      style={"fontSize": "22px", "fontWeight": "800", "color": sig_color}),
            html.Span(f"\u2014 {status}",
                      style={"fontSize": "13px", "color": MUTED}),
        ]),
        html.Div(rows, className="px-xl pb-2xl"),
    ])


def _piotroski_card(data: dict) -> html.Div:
    """Piotroski F-Score card: 9 binary signals in 3 category blocks."""
    p = data.get("piotroski") or {}
    if not p:
        return html.Div()
    f_score  = p.get("f_score", 0)
    label    = p.get("label", "neutral")
    interp   = p.get("interpretation", "")
    signals  = p.get("signals", [])
    lc = {"strong": GREEN, "neutral": AMBER, "weak": RED}.get(label, MUTED)
    # Group signals by category
    cats: dict = {}
    for s in signals:
        cats.setdefault(s.get("category", "Other"), []).append(s)
    cat_blocks = []
    for cat_name, sigs in cats.items():
        rows = []
        for s in sigs:
            on = s["signal"] == 1
            rows.append(html.Div(style={
                "display": "flex", "gap": "10px", "alignItems": "flex-start",
                "padding": "6px 0", "borderBottom": f"1px solid {BORDER}"
            }, children=[
                html.Span("✅" if on else "❌",
                          style={"fontSize": "15px", "minWidth": "20px", "marginTop": "1px"}),
                html.Div([
                    html.Div(f"{s['id']}: {s['label']}",
                             style={"fontSize": "13px", "fontWeight": "600",
                                    "color": TEXT if on else MUTED}),
                    html.Div(s["note"],
                             style={"fontSize": "11px", "color": MUTED, "marginTop": "2px"}),
                ]),
            ]))
        cat_blocks.append(html.Div(className="flex-1 min-w-240", children=[
            html.Div(cat_name.upper(),
                     style={"fontSize": "10px", "fontWeight": "700", "color": MUTED,
                            "letterSpacing": "0.08em", "marginBottom": "6px",
                            "paddingBottom": "4px", "borderBottom": f"2px solid {BORDER}"}),
            *rows,
        ]))
    return html.Div(className="scorecard", children=[
        html.Div(style={"display": "flex", "alignItems": "center",
                        "gap": "10px", "padding": "14px 18px 10px"}, children=[
            html.Span("Financial Health",
                      style={"fontSize": "14px", "fontWeight": "700", "color": TEXT}),
            html.Span(f"{f_score}/9",
                      style={"fontSize": "22px", "fontWeight": "800", "color": lc}),
            html.Span(f"— {label.title()}",
                      style={"fontSize": "13px", "color": lc}),
        ]),
        html.Div(interp, style={"fontSize": "12px", "color": MUTED,
                                "padding": "0 18px 12px", "fontStyle": "italic"}),
        html.Div(cat_blocks,
                 style={"display": "flex", "gap": "20px", "flexWrap": "wrap",
                        "padding": "0 18px 16px"}),
    ])

def _altman_card(data: dict) -> html.Div:
    """Altman Z-Score card: zone badge + component breakdown."""
    a = data.get("altman") or {}
    if not a:
        return html.Div()
    z_score    = a.get("z_score")
    zone       = a.get("zone", "unknown")
    zone_label = a.get("zone_label", "Unknown")
    note       = a.get("note", "")
    model      = a.get("model", "")
    n_avail    = a.get("n_available", 0)
    comps      = a.get("components") or {}
    zc = {"safe": GREEN, "grey": AMBER, "distress": RED, "unknown": MUTED}.get(zone, MUTED)
    zbg = {"safe": "#001a0a", "grey": "#2a2000", "distress": "#2a0000",
           "unknown": CARD}.get(zone, CARD)
    comp_labels = [
        ("x1_working_capital",    "X1 — Working Capital / Assets"),
        ("x2_retained_earnings",  "X2 — Retained Earnings / Assets"),
        ("x3_ebit_ratio",         "X3 — EBIT / Assets"),
        ("x4_equity_liabilities", "X4 — Market Cap / Liabilities"),
        ("x5_asset_turnover",     "X5 — Revenue / Assets"),
    ]
    comp_rows = []
    for key, lbl in comp_labels:
        v = comps.get(key)
        comp_rows.append(html.Div(style={
            "display": "flex", "justifyContent": "space-between",
            "padding": "4px 0", "borderBottom": f"1px solid {BORDER}",
            "fontSize": "12px",
        }, children=[
            html.Span(lbl, className="text-muted"),
            html.Span(f"{v:.3f}" if v is not None else "N/A",
                      style={"color": TEXT if v is not None else MUTED,
                             "fontWeight": "600"}),
        ]))
    return html.Div(className="scorecard", children=[
        html.Div("Stability Score (Bankruptcy Risk)",
                 style={"fontSize": "14px", "fontWeight": "700", "color": TEXT,
                        "padding": "14px 18px 10px"}),
        # Zone badge
        html.Div(style={"background": zbg, "borderRadius": "10px",
                        "margin": "0 16px 14px", "padding": "14px 18px",
                        "border": f"1px solid {zc}33"}, children=[
            html.Div(f"Z = {z_score:.2f}" if z_score is not None else "N/A",
                     style={"fontSize": "34px", "fontWeight": "800", "color": zc}),
            html.Div(zone_label,
                     style={"fontSize": "16px", "fontWeight": "700",
                            "color": zc, "marginTop": "2px"}),
            html.Div(note,
                     style={"fontSize": "11px", "color": MUTED, "marginTop": "6px"}),
            html.Div(f"Model: {model} · {n_avail}/5 components",
                     style={"fontSize": "10px", "color": MUTED, "marginTop": "3px"}),
        ]),
        # Components
        html.Div(comp_rows, className="px-xl pb-2xl"),
    ])

def _risk_card(data: dict) -> html.Div:
    """Risk & performance metrics dashboard."""
    r = data.get("risk") or {}
    if not r or r.get("error") and not r.get("sharpe"):
        return html.Div()
    n_yrs = r.get("n_years", 0)
    if not n_yrs:
        return html.Div()
    def _fv(val, decimals=2, suffix=""):
        return f"{val:.{decimals}f}{suffix}" if val is not None else "N/A"
    def _mc(val, good_above=None, bad_below=None, good_below=None, bad_above=None):
        if val is None:
            return MUTED
        if good_above is not None and val >= good_above:
            return GREEN
        if good_below is not None and val <= good_below:
            return GREEN
        if bad_above is not None and val >= bad_above:
            return RED
        if bad_below is not None and val <= bad_below:
            return RED
        return AMBER
    metrics = [
        ("Sharpe Ratio (≥1.0 good)",       _fv(r.get("sharpe")),
         _mc(r.get("sharpe"), good_above=1.0, bad_below=0)),
        ("Sortino Ratio (≥1.5 good)",      _fv(r.get("sortino")),
         _mc(r.get("sortino"), good_above=1.5, bad_below=0)),
        ("Beta vs SPY (<1.0 defensive)",   _fv(r.get("beta")),
         _mc(r.get("beta"), good_below=1.0, bad_above=1.5)),
        ("Alpha (>0 outperforms)",         _fv(r.get("alpha"), 1, "%"),
         _mc(r.get("alpha"), good_above=0, bad_below=-5)),
        ("Max Drawdown (>-30% ok)",        _fv(r.get("max_drawdown"), 1, "%"),
         _mc(r.get("max_drawdown"), bad_below=-30)),
        ("Ann. Volatility (<25% ok)",      _fv(r.get("volatility_annual"), 1, "%"),
         _mc(r.get("volatility_annual"), good_below=25, bad_above=40)),
        ("VaR 95% (monthly)",  _fv(r.get("var_95"), 1, "%"), MUTED),
        ("CVaR 95% (monthly)", _fv(r.get("cvar_95"), 1, "%"), MUTED),
        ("Ann. Return (≥10% good)",        _fv(r.get("annual_return"), 1, "%"),
         _mc(r.get("annual_return"), good_above=10, bad_below=0)),
        ("Calmar Ratio (≥1.0 good)",       _fv(r.get("calmar")),
         _mc(r.get("calmar"), good_above=1.0, bad_below=0)),
    ]
    metric_cells = [
        html.Div(style={}, children=[
            html.P(lbl, style={"color": MUTED, "fontSize": "12px", "margin": "0"}),
            html.P(val, style={"color": col, "fontWeight": "600", "margin": "0"}),
        ])
        for lbl, val, col in metrics
    ]
    risk_criteria = r.get("risk_criteria") or []
    return html.Div(className="risk-row",children=[
            
            html.Div( className="metric_cell scorecard",children=[
                    html.P(
                    f"Risk & Performance — {n_yrs:.0f}yr History", className="scorecard-header"
                ),
                *metric_cells
            ]),_render_scorecard("Risk Score Breakdown", risk_criteria, "risk")
        ])
        
    
def _regime_card(data: dict) -> html.Div:
    """Regime model card: market condition + portfolio risk overlay."""
    r = data.get("regime") or {}
    ov = data.get("regime_overlay") or {}
    if not r or r.get("error"):
        return html.Div()

    regime        = r.get("regime", "N/A")
    risk_level    = r.get("risk_level", "N/A")
    risk_alert    = r.get("risk_alert", False)
    multiplier    = ov.get("regime_multiplier", 1.0)
    exposure      = ov.get("max_equity_exposure", 1.0)
    adjusted      = ov.get("adjusted_score")
    trend_score   = r.get("market_trend_score")
    vol_pct       = r.get("volatility_percentile")
    drawdown      = r.get("drawdown_depth")

    regime_colors = {
        "BULL_LOW_VOL":  GREEN,
        "BULL_HIGH_VOL": AMBER,
        "SIDEWAYS":      MUTED,
        "BEAR_LOW_VOL":  AMBER,
        "BEAR_HIGH_VOL": RED,
        "CRISIS":        RED,
    }
    risk_colors = {"NORMAL": GREEN, "ELEVATED": AMBER, "HIGH": RED, "CRISIS": RED}
    rc = regime_colors.get(regime, MUTED)
    rlc = risk_colors.get(risk_level, MUTED)

    def _fmt(v, suffix="", decimals=1):
        return f"{v:.{decimals}f}{suffix}" if v is not None else "N/A"

    metrics = [
        ("Trend Score",       _fmt(trend_score, "/100", 0),   AMBER if trend_score and trend_score < 40 else GREEN if trend_score and trend_score >= 60 else MUTED),
        ("Vol Percentile",    _fmt(vol_pct, "%", 0),           RED if vol_pct and vol_pct >= 75 else AMBER if vol_pct and vol_pct >= 50 else GREEN),
        ("Drawdown (252D)",   _fmt(drawdown, "%"),              RED if drawdown and drawdown <= -20 else AMBER if drawdown and drawdown <= -10 else GREEN),
        ("SMA 50",            f"${r.get('sma_50'):.2f}" if r.get("sma_50") else "N/A",  TEXT),
        ("SMA 200",           f"${r.get('sma_200'):.2f}" if r.get("sma_200") else "N/A", TEXT),
        ("Vol 20D (ann.)",    _fmt(r.get("vol_20d"), "%"),     TEXT),
        ("Vol 60D (ann.)",    _fmt(r.get("vol_60d"), "%"),     TEXT),
        ("Regime Multiplier", f"×{multiplier:.2f}",             GREEN if multiplier >= 1.0 else AMBER if multiplier >= 0.8 else RED),
        ("Max Equity Exp.",   f"{exposure*100:.0f}%",           GREEN if exposure >= 1.0 else AMBER if exposure >= 0.7 else RED),
        ("Adjusted Score",    f"{adjusted:.1f}/100" if adjusted is not None else "N/A",
                              GREEN if adjusted and adjusted >= 60 else AMBER if adjusted and adjusted >= 40 else RED),
    ]

    metric_rows = [
        html.Div(style={
            "display": "flex", "justifyContent": "space-between",
            "padding": "4px 0", "borderBottom": f"1px solid {BORDER}", "fontSize": "12px",
        }, children=[
            html.Span(lbl, className="text-muted"),
            html.Span(val, style={"color": col, "fontWeight": "600"}),
        ])
        for lbl, val, col in metrics
    ]

    alert_banner = html.Div(
        "⚡ Fast Deterioration Alert — reduce position sizes",
        style={
            "background": "#3a0000", "color": RED, "borderRadius": "6px",
            "padding": "6px 12px", "margin": "0 0 10px 0", "fontSize": "12px",
            "fontWeight": "700", "border": f"1px solid {RED}",
        }
    ) if risk_alert else html.Div()

    return html.Div(className="scorecard", children=[
        html.Div(style={"display": "flex", "alignItems": "center",
                        "gap": "10px", "padding": "14px 18px 10px"}, children=[
            html.Span("Market Regime",
                      style={"fontSize": "14px", "fontWeight": "700", "color": TEXT}),
            html.Span(regime.replace("_", " "),
                      style={"fontSize": "18px", "fontWeight": "800", "color": rc}),
            html.Span(f"· {risk_level}",
                      style={"fontSize": "13px", "color": rlc, "fontWeight": "600"}),
        ]),
        html.Div(style={"padding": "0 18px 14px"}, children=[
            alert_banner,
            *metric_rows,
            html.Div(
                "Regime multiplier adjusts final score; max equity exposure governs position sizing. "
                "Based on SPY price history.",
                style={"fontSize": "11px", "color": MUTED, "marginTop": "8px",
                       "fontStyle": "italic", "lineHeight": "1.5"},
            ),
        ]),
    ])


def _market_fear_card(data: dict) -> html.Div:
    """Display-only VIX/VIXEQ Market Fear Gauge."""
    fear = data.get("market_fear") or {}
    if not fear or fear.get("error"):
        return html.Div()

    color_map = {
        "green": GREEN,
        "blue": BLUE,
        "amber": AMBER,
        "orange": "#f97316",
        "red": RED,
    }
    accent = color_map.get(fear.get("color"), MUTED)

    def _fmt(v, suffix="", decimals=1):
        return f"{v:.{decimals}f}{suffix}" if v is not None else "N/A"

    metrics = [
        ("VIX", _fmt(fear.get("vix"))),
        ("VIXEQ", _fmt(fear.get("vixeq"))),
        ("Spread", _fmt(fear.get("spread"), decimals=1)),
        ("Ratio", _fmt(fear.get("ratio"), "x", 2)),
        ("Z-Score", _fmt(fear.get("z_score"), decimals=2)),
        ("Fear Score", _fmt(fear.get("market_fear_score"), "/100", 0)),
    ]
    metric_rows = [
        html.Div(style={
            "display": "flex", "justifyContent": "space-between",
            "padding": "4px 0", "borderBottom": f"1px solid {BORDER}", "fontSize": "12px",
        }, children=[
            html.Span(label, className="text-muted"),
            html.Span(value, style={"color": TEXT, "fontWeight": "600"}),
        ])
        for label, value in metrics
    ]

    return html.Div(className="scorecard", children=[
        html.Div(style={"display": "flex", "alignItems": "center",
                        "gap": "10px", "padding": "14px 18px 10px",
                        "flexWrap": "wrap"}, children=[
            html.Span("Market Fear Gauge",
                      style={"fontSize": "14px", "fontWeight": "700", "color": TEXT}),
            html.Span(fear.get("badge", "Market Conditions"),
                      style={"fontSize": "18px", "fontWeight": "800", "color": accent}),
        ]),
        html.Div(style={"padding": "0 18px 14px"}, children=[
            *metric_rows,
            html.P(
                fear.get("interpretation"),
                style={"fontSize": "12px", "color": TEXT, "lineHeight": "1.5",
                       "margin": "10px 0 0"},
            ),
            html.Div(
                "Informational only. Intrinsic value, quality scores, rankings, "
                "and portfolio sizing are unchanged by market fear.",
                style={"fontSize": "11px", "color": MUTED, "marginTop": "8px",
                       "fontStyle": "italic", "lineHeight": "1.5"},
            ),
        ]),
    ])

def _build_analysis_content(data: dict) -> list:
    """Render analysis data into Dash components. Pure function, no side effects."""
    if not data or "error" in data:
        return []
    symbol = data["symbol"]
    name   = data["name"]
    sector = data["sector"]
    g      = data["graham"]
    q      = data["quality"]
    m      = data["momentum"]
    comp = (
        data.get("composite_score")
        or data.get("composite", {}).get("composite_score", 0)
    )
    price = data.get("price")
    er    = data.get("earnings_revision") or {}
    # ── Color Logic ──────────────────────────────────────────────────────────
    def _score_color(val, rule):
        """
        rule:
            {
                "direction": "high" | "low",
                "good_threshold": float,
                "bad_threshold": float | None
            }
        """
        if val is None:
            return MUTED
        direction = rule.get("direction", "high")
        good = rule.get("good_threshold")
        bad = rule.get("bad_threshold")
        if direction == "high":
            if good is not None and val >= good:
                return GREEN
            if bad is not None and val <= bad:
                return RED
            return AMBER
        else:  # low is better
            if good is not None and val <= good:
                return GREEN
            if bad is not None and val >= bad:
                return RED
            return AMBER
    
    # Earnings Revision Color + Display
    er_color = MUTED
    er_signal = er.get("signal", "NEUTRAL")
    if er and er.get("signal"):
        color_map = {
            "STRONG_UP": GREEN, "UP": GREEN,
            "NEUTRAL": AMBER,
            "DOWN": RED, "STRONG_DOWN": RED,
        }
        er_color = color_map.get(er_signal, MUTED)
    er_display = html.Span(
        f"{er.get('total_score', 0):.0f}/100 ({er_signal.replace('_', ' ')})",
        style={"color": er_color, "fontWeight": "700"}
    )
    # ── Extra stat row items ──────────────────────────────────────────────────
    p_data = data.get("piotroski") or {}
    a_data = data.get("altman") or {}
    r_data = data.get("risk") or {}
    b_data = data.get("buffett") or {}
    RULES = {
    "pe": {"direction": "low", "good_threshold": 15, "bad_threshold": 25},
    "pb": {"direction": "low", "good_threshold": 1.5, "bad_threshold": 3},
    "roe": {"direction": "high", "good_threshold": 15, "bad_threshold": 8},
    "op_margin": {"direction": "high", "good_threshold": 15, "bad_threshold": 5},
    "sharpe": {"direction": "high", "good_threshold": 1.0, "bad_threshold": 0.5},
    "beta": {"direction": "low", "good_threshold": 1.0, "bad_threshold": 1.5},
    "f_score": {"direction": "high", "good_threshold": 7, "bad_threshold": 4},
    }
    header = html.Div(
        className="company-header",
        children=[
            html.Div(
                className="company-header-left",
                children=[
                    html.H2(name),
                    html.Div(f"{symbol} · {sector}", className="company-meta"),
                    html.Div(
                        className="stats-row",
                        children=[
                            _stat(
                                "Price",
                                f"${price:.2f}" if price else "N/A",
                                "Current market price per share."
                            ),
                           _stat(
    "P/E",
    html.Span(
        f"{g.get('pe') or 0:.1f}×",
        style={"color": _score_color(g.get("pe"), RULES["pe"])}
    ),
    "Price-to-Earnings (P/E) Ratio. Compares share price to earnings per share. Lower values generally indicate a lower valuation. Traditional value investing often uses 15× as a reference threshold."
),
_stat(
    "P/B",
    html.Span(
        f"{g.get('pb') or 0:.2f}×",
        style={"color": _score_color(g.get("pb"), RULES["pb"])}
    ),
    "Price-to-Book (P/B) Ratio. Compares market price to book value per share. Lower values generally indicate a lower valuation. Traditional value investing often uses 1.5× as a reference threshold."
),
_stat(
    "ROE",
    html.Span(
        f"{q.get('roe') or 0:.1f}%",
        style={"color": _score_color(q.get("roe"), RULES["roe"])}
    ),
    "Return on Equity. Target: ≥15%."
),
_stat(
    "Op Margin",
    html.Span(
        f"{q.get('op_margin') or 0:.1f}%",
        style={"color": _score_color(q.get("op_margin"), RULES["op_margin"])}
    ),
    "Operating Margin. Target: ≥15%."
),
_stat(
    "Sharpe",
    html.Span(
        f"{r_data.get('sharpe') or 0:.2f}",
        style={"color": _score_color(r_data.get('sharpe'), RULES["sharpe"])}
    ),
    "Sharpe Ratio. ≥1.0 = good, ≥1.5 = excellent."
),
_stat(
    "Beta",
    html.Span(
        f"{r_data.get('beta') or 0:.2f}",
        style={"color": _score_color(r_data.get('beta'), RULES["beta"])}
    ),
    "Beta vs SPY. <1.0 = defensive, >1.0 = more volatile."
),
_stat(
    "F-Score",
    html.Span(
        f"{p_data.get('f_score') or 0}/9",
        style={"color": _score_color(p_data.get('f_score'), RULES["f_score"])}
    ),
    "Piotroski F-Score. 8–9 = strong."
),
                            _stat(
                                "Economic Moat Rating",
                                html.Span(
                                    f"${b_data.get('intrinsic_value'):.2f}"
                                    if b_data.get("intrinsic_value") else "N/A",
                                    style={
                                        "color": GREEN
                                        if (price and b_data.get("intrinsic_value") and price <= b_data["intrinsic_value"])
                                        else RED if b_data.get("intrinsic_value") else MUTED
                                    }
                                ),
                                "Intrinsic Value. Green = Price below IV (margin of safety)."
                            ),
                            _stat(
                                "Moat",
                                html.Span(
                                    f"{b_data.get('grade')} ({b_data.get('grade_label', '')})"
                                    if b_data.get("grade") else "N/A",
                                    style={
                                        "color": {
                                            "A": GREEN,
                                            "B": BLUE,
                                            "C": AMBER,
                                            "D": RED
                                        }.get(b_data.get("grade"), MUTED)
                                    }
                                ),
                                "Economic Moat Rating: A=Wide Moat (best), D=Avoid."
                            ),
                            _stat(
                                "Comp",
                                html.Span(
                                    f"{comp:.0f}/100",
                                    style={
                                        "fontWeight": "700",
                                        "color": _verdict_color(
                                            data.get("enhanced", {}).get("verdict_label")
                                            or data.get("composite", {}).get("verdict_label", "pending")
                                        )
                                    }
                                ),
                                "Overall Composite Score (higher = better)."
                            ),
                            _stat(
                                "E. Rev",
                                er_display,
                                "Earnings Revision Score (0–100) — Measures analyst revisions."
                            ),
                        ]
                    ),
                ]
            ),
            html.Div(
                className="badges",
                children=[
                    html.Div(
                        className="grade-badge",
                        children=[
                            html.Div(
                                g["grade"],
                                className="grade-letter",
                                style={"color": _grade_color(g["grade"])}
                            ),
                            html.Div("Intrinsic Value Estimate", className="grade-label"),
                            html.Div(
                                f"{g['total_score']}/{g['total_max']}",
                                className="grade-score"
                            ),
                        ]
                    ),
                    html.Div(
                        className="grade-badge",
                        style={"borderLeft": f"1px solid {BORDER}"},
                        children=[
                            html.Div(
                                f"${b_data.get('intrinsic_value', 0):.0f}"
                                if b_data.get("intrinsic_value") else "—",
                                className="grade-letter",
                                style={
                                    "color": (
                                        GREEN
                                        if (price and b_data.get("intrinsic_value") and price <= b_data["intrinsic_value"])
                                        else RED if b_data.get("intrinsic_value") and price
                                        else MUTED
                                    ),
                                    "fontSize": "22px",
                                },
                            ),
                            html.Div("Economic Moat Rating", className="grade-label"),
                            html.Span(
                                f"{b_data.get('grade')} — {b_data.get('grade_label')}"
                                if b_data.get("grade") else "N/A",
                                className="grade-score",
                                style={
                                    "color": {
                                        "A": GREEN,
                                        "B": BLUE,
                                        "C": AMBER,
                                        "D": RED
                                    }.get(b_data.get("grade", ""), MUTED),
                                    "cursor": "help",
                                    "borderBottom": f"1px dashed {MUTED}",
                                },
                                title=_MOAT_TOOLTIPS.get(b_data.get("grade", ""), ""),
                            ),
                        ]
                    ),
                ]
            ),
        ]
    )
    banner = _composite_banner(data)
    graham_card  = _render_scorecard("Intrinsic Value Analysis", g["criteria"], "graham")
    quality_card = _render_scorecard("Moat Rating Analysis", q["criteria"], "quality")
    
    buffett_card = (
        _render_scorecard("Economic Moat Quality & Value", b_data.get("criteria", []), "buffett")
        if b_data.get("criteria") else html.Div()
    )
    momentum_card = (
        _render_scorecard("Momentum Analysis", m.get("criteria", []), "momentum")
        if m.get("criteria") else html.Div()
    )
    
    piotroski_card = _piotroski_card(data)
    altman_card = _altman_card(data)
    risk_card = _risk_card(data)
    fcf_quality_card = _fcf_quality_card(data)
    market_fear_card = _market_fear_card(data)
    regime_card = _regime_card(data)
    capital_allocation_card = _capital_allocation_card(data)
    growth_quality_card = _growth_quality_card(data)
    factor_momentum_card = _factor_momentum_card(data)
    alternative_data_card = _alternative_data_card(data)
    div_chart = _div_chart(g.get("div_history", []), symbol)
    graham_details = _graham_details_card(g, b_data)
    buffett_details = _buffett_details_card(data)
    row=(
        html.Div(className="card-row bg", children=[graham_details, buffett_details]),
        html.Div(className="moment_quality_row",children=[buffett_card, momentum_card]),
        risk_card,
        html.Div(className="card-row", children=[quality_card, graham_card]),
        html.Div(className="quant_row", children=[piotroski_card, altman_card])
        if p_data and a_data else html.Div(),
        html.Div(className="card-row", children=[market_fear_card, regime_card]),
        html.Div(className="card-row", children=[fcf_quality_card]),
        html.Div(className="card-row", children=[capital_allocation_card, growth_quality_card]),
        html.Div(className="card-row", children=[_insider_activity_card(data), alternative_data_card]),
        html.Div(className="card-row", children=[factor_momentum_card,_options_signal_card(data)]),
        html.Div(className="charts-grid",children=[_eps_chart(g.get("eps_history", []), symbol), _price_chart(data.get("price_history"), data.get("spy_history"), symbol),])
        )
    
  
   
    return [
        header,
        banner,

        *row,
        div_chart
    ]


def _stat(label, value, tooltip=None):
    return html.Div([
        html.Div(label, className="stat-label",
                 title=tooltip or "",
                 style={"cursor": "help", "borderBottom": f"1px dashed {MUTED}"} if tooltip else {}),
        html.Div(value, className="stat-value")
    ], className="stat-item")

def _pillar(label, score, weight):
    return html.Div([
        html.Div(f"{score}%", className="pillar-value") if isinstance(score, (int, float)) else html.Div(score, className="pillar-value"),
        html.Div(label, className="pillar-label"),
        html.Div(f"({weight})", className="pillar-weight"),
    ])

def _grade_color(grade: str) -> str:
    return {"A": GREEN, "B": BLUE, "C": AMBER, "D": RED}.get(grade, MUTED)
def format_currency(val) -> str:
    if val is None:
        return "N/A"
    elif val >= 1e9:
        return f"${val/1e9:.2f}B"
    elif val >= 1e6:
        return f"${val/1e6:.2f}M"
    elif val >= 1e3:
        return f"${val/1e3:.2f}K"
    else:
        return f"${val:.2f}"
def _fmt_market_cap(v) -> str:
    if v is None:
        return "—"
    # v is stored in $M
    if v >= 1e6:
        return f"${v/1e6:.2f}T"
    if v >= 1e3:
        return f"${v/1e3:.2f}B"
    return f"${v:,.0f}M"

def _fmt_updated(v) -> str:
    if not v:
        return "—"
    try:
        return v[:10]  # ISO date portion
    except Exception:
        return "—"
def _verdict_color(label: str) -> str:
    return {
        "strong-buy": GREEN,
        "buy": BLUE,
        "watch": AMBER,
        "hold": MUTED,
        "avoid": RED,
        "pending": MUTED,
    }.get(label, MUTED)

def _render_scorecard(title: str, criteria: list, card_type: str) -> html.Div:
    rows = []
    for c in criteria:
        score = c["score"]
        max_s = c["max"]
        pct = score / max_s * 100 if max_s else 0
        color = GREEN if pct >= 66 else AMBER if pct >= 33 else RED
        rows.append(html.Div(className="criterion-row", children=[
            html.Div([
                html.Div(c["label"], className="criterion-label"),
                html.Div(c["note"], className="criterion-note"),
                html.Div(className="score-bar", children=[
                    html.Div(className="score-bar-fill", style={
                        "width": f"{pct}%", "background": color
                    })
                ])
            ]),
            html.Div(f"{score}/{max_s}", className="criterion-pts", style={"color": color}),
        ]))
    return html.Div(className="scorecard", children=[
        html.Div(title, className="scorecard-header"),
        html.Div(rows)
    ])

def _eps_chart(eps_history: list, symbol: str) -> html.Div:
    if not eps_history:
        return html.Div(className="empty-card", children=[
            html.Div("EPS History", className="empty-card-title"),
            html.Div("No EPS data", className="empty-title"),
            html.Div("Insufficient data available", className="empty-msg"),
        ])
    df = pd.DataFrame(eps_history).sort_values("year")
    colors = [GREEN if v >= 0 else RED for v in df["value"]]
    fig = go.Figure(go.Bar(
        x=df["year"].astype(str), y=df["value"],
        marker_color=colors,
        text=[format_currency(v) for v in df["value"]],
        textposition="outside",
        textfont=dict(size=12, color=WHITE) 
    ))
    fig.update_layout(**_chart_layout(f"{symbol} EPS History (10yr)"))
    return dcc.Graph(figure=fig, config={"displayModeBar": False})

def _price_chart(price_history_dict, spy_history_dict, symbol: str) -> html.Div:
    # Convert stored dict data back to DataFrames
    hist = pd.DataFrame(price_history_dict) if price_history_dict else pd.DataFrame()
    spy_hist = pd.DataFrame(spy_history_dict) if spy_history_dict else pd.DataFrame()
    if hist.empty:
        return html.Div(className="empty-card", children=[
            html.Div("Price History", className="empty-card-title"),
            html.Div("No price data", className="empty-title"),
            html.Div("Insufficient history available", className="empty-msg"),
        ])
    fig = go.Figure()
    def _normalise(df):
        df = df.copy()
        df["Close"] = pd.to_numeric(df["Close"], errors="coerce")
        df = df.dropna()
        if df.empty or df["Close"].iloc[0] <= 0:
            return df
        df["norm"] = df["Close"] / df["Close"].iloc[0] * 100
        return df
    hist = _normalise(hist)
    if not hist.empty:
        fig.add_trace(go.Scatter(
            x=hist["Date"], y=hist["norm"], name=symbol,
            line=dict(color=BLUE, width=2)
        ))
    if not spy_hist.empty:
        spy_hist = _normalise(spy_hist)
        if not spy_hist.empty:
            fig.add_trace(go.Scatter(
                x=spy_hist["Date"], y=spy_hist["norm"], name="SPY",
                line=dict(color=MUTED, width=1.5, dash="dot")
            ))
    fig.update_layout(**_chart_layout(f"{symbol} vs SPY (10yr normalised)"))
    fig.update_yaxes(title_text="Index (100 = start)")
    return dcc.Graph(figure=fig, config={"displayModeBar": False})

def _div_chart(div_history: list, symbol: str) -> html.Div:
    if not div_history:
        return html.Div(className="empty-card", children=[
            html.Div("Dividend History", className="empty-card-title"),
            html.Div("No dividends", className="empty-title"),
            html.Div("This company has not paid dividends", className="empty-msg"),
        ])
    df = pd.DataFrame(div_history).sort_values("year")
    df = df[df["value"] > 0]
    if df.empty:
        return html.Div(className="empty-card", children=[
            html.Div("Dividend History", className="empty-card-title"),
            html.Div("No dividends", className="empty-title"),
            html.Div("No dividend payments on record", className="empty-msg"),
        ])
    fig = go.Figure(go.Bar(
        x=df["year"].astype(str),
        y=df["value"] / 1e6,
        marker_color=BLUE,
        text=[format_currency(v) for v in df["value"]],
        textposition="outside",
        textfont=dict(size=20, color=WHITE) 
    ))
    fig.update_layout(**_chart_layout(f"{symbol} Dividend Payments (USD Millions)"))
    return dcc.Graph(figure=fig, config={"displayModeBar": False})

def _graham_details_card(g_data: dict, b_data: dict | None = None) -> html.Div:
    gn    = g_data.get("graham_number")
    price = g_data.get("price")
    mos   = g_data.get("margin_of_safety")
    # Buffett IV fields
    b_data   = b_data or {}
    biv      = b_data.get("intrinsic_value")
    b_mos    = b_data.get("margin_of_safety")
    b_grade  = b_data.get("grade")
    b_glabel = b_data.get("grade_label", "")
    rows = [
        ("Fair Value",     f"${gn:.2f}"  if gn    else "N/A"),
        ("Margin of Safety",        f"{mos:.1f}%" if mos   else "N/A"),
        ("Current Price",     f"${price:.2f}" if price else "N/A"),
        ("EPS",               f"${g_data.get('eps', 0):.2f}" if g_data.get('eps') else "N/A"),
        ("Book Value/Share",  f"${g_data.get('bvps', 0):.2f}" if g_data.get('bvps') else "N/A"),
        ("Div Years",         str(g_data.get("div_years", 0))),
        ("EPS Years",         str(g_data.get("eps_years", 0))),
    ]
    gn_color  = GREEN if mos and mos > 0 else RED
    biv_color = GREEN if b_mos and b_mos > 0 else RED
    grade_color = {"A": GREEN, "B": BLUE, "C": AMBER, "D": RED}.get(b_grade or "", MUTED)
    def _row_color(label):
        if label == "Margin of Safety":       return gn_color
        if label == "Margin of Safety":      return biv_color
        if label == "Economic Moat Rating":    return grade_color
        return TEXT
    detail_rows = [
        html.Div(className="detail-row", children=[
            html.Span(label, className="detail-label"),
            html.Span(value, className="detail-value",
                      style={"color": _row_color(label)}),
        ])
        for label, value in rows
    ]
    return html.Div(className="scorecard", children=[
        html.Div("Intrinsic Value Estimate", className="card-header"),
        *detail_rows
    ])

def _buffett_details_card(data: dict) -> html.Div:
    b = data.get("buffett") or {}
    iv  = b.get("intrinsic_value")
    mos = b.get("margin_of_safety")
    price = b.get("price")
    rows = [
        ("Grade",             f"{b.get('grade', 'N/A')} — {b.get('grade_label', '')}"),
        ("Intrinsic Value",   f"${iv:.2f} ({b.get('iv_base', '')})" if iv else "N/A"),
        ("Margin of Safety",  f"{mos:.1f}%" if mos is not None else "N/A"),
        ("ROE (latest)",      f"{b.get('roe_latest', 0):.1f}%" if b.get("roe_latest") else "N/A"),
        ("ROE ≥15% years",    f"{b.get('n_roe_above15', 0)}/{b.get('n_roe_years', 0)}"),
        ("Net Margin",        f"{b.get('net_margin', 0):.1f}%" if b.get("net_margin") else "N/A"),
        ("EPS CAGR",          f"{b.get('eps_cagr', 0):.1f}%/yr" if b.get("eps_cagr") is not None else "N/A"),
        ("FCF",               f"${b.get('fcf_latest', 0):.1f}B" if b.get("fcf_latest") is not None else "N/A"),
        ("ROIC",              f"{b.get('roic', 0):.1f}%" if b.get("roic") else "N/A"),
        ("Debt Payback",      f"{b.get('de_years', 0):.1f}yr" if b.get("de_years") is not None else "N/A"),
    ]
    iv_color = GREEN if mos and mos > 0 else RED
    detail_rows = [
        html.Div(className="detail-row", children=[
            html.Span(label, className="detail-label"),
            html.Span(value, className="detail-value",
                      style={"color": iv_color if label == "Margin of Safety" else TEXT}),
        ])
        for label, value in rows
    ]
    return html.Div(className="scorecard", children=[
        html.Div("Economic Moat Rating Details", className="card-header"),
        html.Div(detail_rows)
    ])

def _chart_layout(title: str, many_traces: bool = False) -> dict:
    """
    many_traces=True: vertical legend anchored top-right outside the plot.
    Used for portfolio charts which have 4-6 traces and would otherwise
    collide with the title.
    """
    if many_traces:
        legend = dict(
            bgcolor="rgba(26,29,39,0.88)",
            bordercolor=BORDER,
            borderwidth=1,
            font=dict(size=11),
            orientation="v",
            x=1.01,
            y=1.0,
            xanchor="left",
            yanchor="top",
        )
        margin = dict(l=16, r=160, t=44, b=16)   # right margin makes room
    else:
        legend = dict(
            bgcolor="rgba(0,0,0,0)",
            font=dict(size=11),
            orientation="h",
            x=0,
            y=1.08,
            xanchor="left",
            yanchor="bottom",
        )
        margin = dict(l=16, r=16, t=44, b=16)
    return dict(
        title=dict(text=title, font=dict(size=13, color=MUTED), x=0),
        paper_bgcolor=CARD,
        plot_bgcolor=CARD,
        font=dict(color=TEXT, family="Inter, system-ui, sans-serif"),
        margin=margin,
        xaxis=dict(showgrid=False, zeroline=False),
        yaxis=dict(gridcolor=BORDER, zeroline=False),
        legend=legend,
    )
