"""Rendering helpers for the stock analysis view and shared charts."""

from dash import dcc, html
import plotly.graph_objects as go
from urllib.parse import quote

from codes.services import chart_service

from .config import AMBER, BLUE, BORDER, CARD, GREEN, MUTED, RED, TEXT, WHITE, _MOAT_TOOLTIPS
from .css_classes import tone_class

_ANALYSIS_ROW_DIVIDER = "rgba(67, 52, 90, 0.65)"


def _clamp_pct(value) -> float:
    try:
        return min(max(float(value or 0), 0), 100)
    except (TypeError, ValueError):
        return 0.0


def _factor_hexagon(factors: list[tuple[str, float]], color: str) -> html.Figure:
    """Render a six-axis score profile; outward always means stronger."""
    import math

    center, radius = 180, 100
    angles = [math.radians(-90 + index * 60) for index in range(6)]

    def points(scale: float) -> str:
        return " ".join(
            f"{center + radius * scale * math.cos(angle):.1f},{center + radius * scale * math.sin(angle):.1f}"
            for angle in angles
        )

    values = [_clamp_pct(value) for _, value in factors]
    profile_points = " ".join(
        f"{center + radius * value / 100 * math.cos(angle):.1f},{center + radius * value / 100 * math.sin(angle):.1f}"
        for value, angle in zip(values, angles)
    )


    grid = "".join(
        f'<polygon points="{points(scale)}" fill="none" stroke="#4173a7" stroke-opacity="{0.32 + scale * 0.28:.2f}" stroke-width="{1.1 if scale < 1 else 1.7}" />'
        for scale in (0.2, 0.4, 0.6, 0.8, 1)
    )
    axes = "".join(
        f'<line x1="{center}" y1="{center}" x2="{center + radius * math.cos(angle):.1f}" y2="{center + radius * math.sin(angle):.1f}" stroke="#4f80b2" stroke-opacity="0.72" stroke-width="1.2" />'
        for angle in angles
    )
    vertices = "".join(
        f'<circle cx="{center + radius * value / 100 * math.cos(angle):.1f}" cy="{center + radius * value / 100 * math.sin(angle):.1f}" r="3.8" fill="{color}" stroke="#dcecff" stroke-width="1.3" />'
        for value, angle in zip(values, angles)
    )
    labels = "".join(
        f'<text x="{center + 138 * math.cos(angle):.1f}" y="{center + 138 * math.sin(angle):.1f}" fill="#f5f9ff" stroke="#07182e" stroke-width="2.2" paint-order="stroke" font-family="Inter,Arial,sans-serif" font-size="12" font-weight="700" text-anchor="middle">{label}<tspan x="{center + 138 * math.cos(angle):.1f}" dy="16" fill="{color}" font-size="14" font-weight="800">{value:.0f}</tspan></text>'
        for (label, _), value, angle in zip(factors, values, angles)
    )
    svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 360 350" role="img">'
        '<defs><filter id="hex-glow" x="-25%" y="-25%" width="150%" height="150%"><feGaussianBlur stdDeviation="2.5" result="blur"/><feMerge><feMergeNode in="blur"/><feMergeNode in="SourceGraphic"/></feMerge></filter>'
        f'<linearGradient id="hex-fill" x1="0" y1="0" x2="1" y2="1"><stop stop-color="{color}" stop-opacity="0.42"/><stop offset="1" stop-color="{color}" stop-opacity="0.10"/></linearGradient></defs>'
        f'<g>{grid}{axes}<line x1="80" y1="180" x2="280" y2="180" stroke="#4f80b2" stroke-opacity="0.72" stroke-width="1.2" />'
        f'<polygon points="{profile_points}" fill="url(#hex-fill)" stroke="{color}" stroke-width="2.6" filter="url(#hex-glow)" />{vertices}{labels}</g>'
        '</svg>'
    )
    description = ", ".join(f"{label} {value:.0f}" for (label, _), value in zip(factors, values))
    return html.Figure(
        className="factor-hexagon",
        children=[html.Img(src=f"data:image/svg+xml,{quote(svg)}", alt=f"Six-factor score profile: {description}")],
    )


def _composite_trend_chart(symbol: str, color: str):
    dataset = chart_service.get_composite_trend_dataset(symbol)
    series = (dataset.get("series") or [{}])[0]
    scores = series.get("y") or []
    dates = series.get("x") or []
    if len(scores) < 2:
        return html.Div("Composite trend will appear after the next score update.", className="composite-trend-empty")

    change = scores[-1] - scores[0]
    direction = "↑" if change > 0 else "↓" if change < 0 else "→"
    figure = go.Figure(go.Scatter(
        x=dates, y=scores, mode="lines+markers",
        line={"color": color, "width": 2.5}, marker={"color": color, "size": 5},
        hovertemplate="%{x}<br>Composite %{y:.1f}<extra></extra>",
    ))
    figure.update_layout(
        height=128, margin={"l": 4, "r": 4, "t": 4, "b": 4},
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        showlegend=False, hovermode="x unified",
        xaxis={"showgrid": False, "showticklabels": False, "zeroline": False},
        yaxis={"range": [0, 100], "showgrid": True, "gridcolor": "rgba(126, 157, 194, 0.18)", "showticklabels": False, "zeroline": False},
    )
    return html.Div(className="composite-trend", children=[
        html.Div(f"Score trend {direction} {abs(change):.1f} pts", className="composite-trend-label"),
        dcc.Graph(figure=figure, config={"displayModeBar": False, "responsive": True}, className="composite-trend-graph"),
    ])


def _metric_data_row(label, value) -> html.Div:
    return html.Div(
        className="analysis-metric-row analysis-divider d-flex jc-between gap-12 py-4 fs-12",
        style={"borderBottom": f"1px solid {_ANALYSIS_ROW_DIVIDER}"},
        children=[
            html.Span(label, className="analysis-metric-label text-muted"),
            value if not isinstance(value, str) else html.Span(value, className="analysis-metric-value clr-text fw-600"),
        ],
    )


def _metric_scorecard(
    *,
    title: str,
    score_text: str | None = None,
    score_color: str = MUTED,
    status_text: str | None = None,
    status_color: str | None = None,
    subtitle: str | None = None,
    body_children: list | None = None,
    card_class: str = "",
) -> html.Div:
    header_children = [
        html.Span(title, className="fs-14 fw-700 clr-text"),
    ]
    if score_text is not None:
        header_children.append(
            html.Span(score_text, className=f"fs-22 fw-800 {tone_class(score_color)}")
        )
    if status_text:
        header_children.append(
            html.Span(status_text, className=f"fs-13 {tone_class(status_color or score_color)}")
        )

    body = []
    if subtitle:
        body.append(
            html.Div(
                subtitle,
                className="analysis-card-subtitle analysis-subtitle fs-11 clr-muted fsi",
            )
        )
    body.extend(body_children or [])

    class_name = "scorecard"
    if card_class:
        class_name = f"{class_name} {card_class}"

    return html.Div(
        className=class_name,
        children=[
            html.Div(
                className="scorecard-header d-flex ai-center gap-10 pt-14 px-18 pb-10 flex-wrap",
                children=header_children,
            ),
            html.Div(className="analysis-card-body px-xl pb-2xl", children=body),
        ],
    )

def _composite_banner(data: dict) -> html.Div:
    """
    Smart composite banner: shows enhanced orthogonal composite when available,
    falls back to original 3-pillar composite for older cached results.
    Uses mockup-style layout: score / factor circles / stats.
    """
    enhanced = data.get("enhanced") or {}
    comp     = data.get("composite") or {}
    g        = data.get("graham") or {}
    b        = data.get("buffett") or {}
    q        = data.get("quality") or {}
    r        = data.get("risk") or {}
    p        = data.get("piotroski") or {}
    er       = data.get("earnings_revision") or {}
    has_enh  = bool(enhanced.get("composite_score") is not None)
    src      = enhanced if has_enh else comp
    verdict       = src.get("verdict",      "N/A")
    verdict_label = src.get("verdict_label","pending")
    verdict_desc  = src.get("verdict_desc", "")
    score         = src.get("composite_score", 0) or 0
    price         = data.get("price")

    # Map verdict labels to mockup CSS classes
    vcls_map = {
        "strong-buy": "hc", "admirable": "hc",
        "high-conviction": "hc",
        "buy": "fav", "favorable": "fav",
        "watch": "bal", "balanced": "bal",
        "hold": "cau", "cautious": "cau",
        "caution": "cau",
        "avoid": "unfav", "unfavorable": "unfav",
        "pending": "bal",
    }
    vcls = vcls_map.get(verdict_label, "bal")

    # Six-axis profile: all axes are normalized so outward always means stronger.
    if has_enh:
        factor_data = [
            ("Composite", score),
            ("Intrinsic",   enhanced.get("graham_pct", 0)),
            ("Quality",  enhanced.get("quality_pct", 0)),
            ("Momentum", enhanced.get("momentum_pct", 0)),
            ("Safety",   enhanced.get("risk_pct", 0)),
            ("Profit.",  enhanced.get("profitability_pct", 0)),
        ]
    else:
        factor_data = [
            ("Composite", score),
            ("Intrinsic",   comp.get("graham_pct", 0)),
            ("Quality",  comp.get("quality_pct", 0)),
            ("Momentum", comp.get("momentum_pct") or 0),
            ("Safety",   comp.get("safety_pct") or comp.get("altman_pct", 0)),
            ("Profit.",  comp.get("profitability_pct", 0)),
        ]
    verdict_colors = {"hc": GREEN, "fav": BLUE, "bal": AMBER, "cau": "#ff6d00", "unfav": RED}
    verdict_color = verdict_colors[vcls]
    hexagon = _factor_hexagon(factor_data, verdict_color)
    trend = _composite_trend_chart(data.get("symbol", ""), verdict_color)

    # Stats row (matching mockup)
    market_cap = g.get("market_cap")
    mcap_str = _fmt_market_cap(market_cap) if market_cap else "N/A"
    graham_score = g.get("total_score", 0)
    graham_max = g.get("total_max", 105)
    intrinsic_str = f"{g.get('grade', 'N/A')} {graham_score}/{graham_max}"
    moat_grade = b.get("grade", "N/A")
    moat_label = b.get("grade_label", "")
    moat_str = f"{moat_grade} — {moat_label}" if moat_label else moat_grade
    price_str = f"${price:.2f}" if price else "N/A"

    stat_values = [
        ("Market Cap", mcap_str), ("Price", price_str),
        ("Intrinsic", intrinsic_str), ("Buffett Moat", moat_str),
        ("P/E", f"{g.get('pe'):.1f}×" if g.get("pe") is not None else "N/A"),
        ("P/B", f"{g.get('pb'):.2f}×" if g.get("pb") is not None else "N/A"),
        ("ROE", f"{q.get('roe'):.1f}%" if q.get("roe") is not None else "N/A"),
        ("Op. Margin", f"{q.get('op_margin'):.1f}%" if q.get("op_margin") is not None else "N/A"),
        ("Sharpe", f"{r.get('sharpe'):.2f}" if r.get("sharpe") is not None else "N/A"),
        ("Beta", f"{r.get('beta'):.2f}" if r.get("beta") is not None else "N/A"),
        ("F-Score", f"{p.get('f_score')}/9" if p.get("f_score") is not None else "N/A"),
        ("E. Revision", f"{er.get('total_score'):.0f}/100" if er.get("total_score") is not None else "N/A"),
    ]
    stats = html.Div(className="composite-stats", children=[
        html.Div(className="composite-stat", children=[
            html.Div(label, className="composite-stat-label"),
            html.Div(value, className="composite-stat-value"),
        ])
        for label, value in stat_values
    ])

    # Flags row
    flags = []
    if enhanced.get("value_trap_warning") or comp.get("value_trap_warning"):
        flags.append(html.Span("⚠️ Value Trap Risk",
                               className="analysis-flag analysis-flag--value-trap br-6 fs-12 fw-600"))
    if enhanced.get("compounder_flag"):
        flags.append(html.Span("🚀 Compounder Signal",
                               className="analysis-flag analysis-flag--compounder br-6 fs-12 fw-600"))
    if enhanced.get("altman_cap_applied"):
        flags.append(html.Span("🔴 Altman Distress Cap Active",
                               className="analysis-flag analysis-flag--distress br-6 fs-12 fw-600"))
    if (data.get("growth_quality") or {}).get("acquisition_driven_growth"):
        flags.append(html.Span("🟠 Acquisition-Driven Growth",
                               className="analysis-flag analysis-flag--acquisition br-6 fs-12 fw-600"))

    return html.Div(className="composite-banner", children=[
        html.Div(className="composite-top", children=[
            html.Div(className="composite-score-wrap", children=[
                html.Div(f"{score:.0f}", className="composite-score"),
                html.Div("Composite Score", className="composite-label"),
                html.Div(verdict.upper(), className=f"composite-verdict {vcls}",
                         title=verdict_desc),
                trend,
            ]),
            html.Div(className="analysis-hexagon-wrap", children=[hexagon]),
            stats,
        ]),
        html.Div(flags, className="d-flex gap-8 flex-wrap") if flags else html.Div(),
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

    metric_rows = [_metric_data_row(lbl, val) for lbl, val in metrics]

    return _metric_scorecard(
        title="FCF Quality",
        score_text=f"{score:.0f}/100",
        score_color=sig_color,
        status_text=f"— {signal.replace('_', ' ').title()}",
        body_children=metric_rows,
    )
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
        "HIGH_CONVICTION_CALL": GREEN, "HIGH_CONVICTION_PUT": GREEN,
        "FAVORABLE_CALL": GREEN, "FAVORABLE_PUT": GREEN,
        "WATCH": AMBER, "AVOID": RED, "NO_TRADE": MUTED,
        "BALANCED": AMBER, "CAUTION": AMBER, "UNFAVORABLE": RED,
    }.get(signal, MUTED)

    def _fmt(v, fmt=".2f", prefix="", suffix=""):
        if v is None:
            return "N/A"
        try:
            return f"{prefix}{v:{fmt}}{suffix}"
        except (ValueError, TypeError):
            return "N/A"

    metrics = [
        ("Bias",             html.Span(bias, className=f"fw-700 {tone_class(bias_color)}")),
        ("Confidence",       _fmt(os_data.get("bias_confidence"), ".0f", suffix="/100")),
        ("IV Level",         os_data.get("iv_level", "N/A")),
        ("IV Trend",         os_data.get("iv_trend", "N/A")),
        ("Expected Move",    _fmt((os_data.get("expected_move_pct") or 0) * 100, ".1f", suffix="%")),
        ("Expected Move $",  _fmt(os_data.get("expected_move_dollar"), ",.2f", "$")),
        ("Suggested Strike", _fmt(os_data.get("recommended_strike"), ",.2f", "$")),
        ("Expiry (days)",    str(os_data.get("recommended_expiry_days", "N/A"))),
        ("Risk Score",       _fmt(risk, ".0f", suffix="/100")),
    ]

    metric_rows = [_metric_data_row(lbl, val) for lbl, val in metrics]

    return _metric_scorecard(
        title="Options Signal",
        score_text=f"{edge:.0f}/100",
        score_color=sig_color,
        status_text=f"— {signal.replace('_', ' ').title()}",
        subtitle="Models short-horizon option mark-to-market movement, not expiry payoff.",
        body_children=metric_rows,
    )

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
                                          className=f"fw-600 {tone_class(roic_spread_color)}")),
        ("Incremental ROIC",  _fmt(ca.get("incremental_roic"), ".1f", suffix="%")),
        ("Reinvestment Rate", _fmt(ca.get("reinvestment_rate"), ".1%") if ca.get("reinvestment_rate") is not None else "N/A"),
        ("Reinvest Method",   ca.get("reinvestment_method", "N/A")),
        ("Buyback Yield",     _fmt(ca.get("buyback_yield"), ".2f", suffix="%")),
        ("Dividend Yield",    _fmt(ca.get("dividend_yield_implied"), ".2f", suffix="%")),
        ("Shareholder Yield", _fmt(ca.get("shareholder_yield"), ".2f", suffix="%")),
        ("Dilution Rate",     html.Span(_fmt(ca.get("dilution_rate"), "+.2f", suffix="%"),
                                         className=f"fw-600 {tone_class(dilution_color)}")),
        ("Debt Trend (Δ D/E)", html.Span(_fmt(ca.get("debt_trend"), "+.3f"),
                                           className=f"fw-600 {tone_class(debt_color)}")),
    ]

    metric_rows = [_metric_data_row(lbl, val) for lbl, val in metrics]

    return _metric_scorecard(
        title="Capital Allocation",
        score_text=f"{score:.0f}/100",
        score_color=sig_color,
        status_text=f"— {signal.replace('_', ' ').title()}",
        body_children=metric_rows,
    )


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

    metric_rows = [_metric_data_row(lbl, val) for lbl, val in metrics]

    return _metric_scorecard(
        title="Growth Quality",
        score_text=f"{score:.0f}/100",
        score_color=sig_color,
        status_text=f"\u2014 {signal}",
        body_children=metric_rows,
    )


def _accounting_quality_card(data: dict) -> html.Div:
    """Accounting Quality card: forensic accounting and manipulation-risk diagnostics."""
    aq = data.get("accounting_quality") or {}
    if not aq:
        return html.Div()

    score = aq.get("accounting_quality_score")
    risk = aq.get("manipulation_risk", "Moderate")
    if score is None:
        return html.Div()

    sig_color = {
        "Low": GREEN,
        "Moderate": AMBER,
        "High": RED,
    }.get(risk, MUTED)

    def _fmt(v, decimals=1, suffix="%"):
        return f"{v:.{decimals}f}{suffix}" if v is not None else "N/A"

    metrics = [
        ("Grade", aq.get("accounting_grade", "N/A")),
        ("Risk Level", aq.get("accounting_risk_level", "N/A")),
        ("Accrual Ratio", _fmt(aq.get("accrual_ratio"), 2, "")),
        ("DSO Change", _fmt(aq.get("dso_change_days"), 1, " days")),
        (
            "Asset Composition",
            _fmt(
                aq.get("asset_composition_ratio") * 100
                if aq.get("asset_composition_ratio") is not None else None,
                1,
            ),
        ),
        ("Warning Flags", str(aq.get("warning_count", 0))),
    ]

    metric_rows = [_metric_data_row(lbl, val) for lbl, val in metrics]
    metric_rows.append(
        html.Div(
            aq.get("explanation", ""),
            className="fs-12 clr-muted fsi pt-8",
        )
    )

    return _metric_scorecard(
        title="Accounting Quality",
        score_text=f"{score:.0f}/100",
        score_color=sig_color,
        status_text=f"\u2014 {risk} Manipulation Risk",
        body_children=metric_rows,
    )


def _beneish_card(data: dict) -> html.Div:
    """Beneish M-Score card: earnings-manipulation probability diagnostic."""
    ben = data.get("beneish") or {}
    if not ben:
        return html.Div()

    m_score = ben.get("m_score")
    if m_score is None:
        return html.Div()

    risk = ben.get("risk_label", "Unknown")
    sig_color = {
        "Low": GREEN,
        "Moderate": AMBER,
        "High": RED,
        "Unknown": MUTED,
    }.get(risk, MUTED)

    def _fmt(v, decimals=2, suffix=""):
        return f"{v:.{decimals}f}{suffix}" if v is not None else "N/A"

    metrics = [
        ("M-Score", _fmt(m_score, 2)),
        ("Threshold", _fmt(ben.get("threshold"), 2)),
        ("Coverage", f"{ben.get('n_available', 0)}/8"),
        ("DSRI", _fmt(ben.get("dsri"), 2)),
        ("GMI", _fmt(ben.get("gmi"), 2)),
        ("TATA", _fmt(ben.get("tata"), 3)),
    ]

    metric_rows = [_metric_data_row(lbl, val) for lbl, val in metrics]
    metric_rows.append(html.Div(ben.get("note", ""), className="fs-12 clr-muted fsi pt-8"))

    return _metric_scorecard(
        title="Beneish M-Score",
        score_text=f"{m_score:.2f}",
        score_color=sig_color,
        status_text=f"\u2014 {risk} Risk",
        body_children=metric_rows,
    )


def _dechow_card(data: dict) -> html.Div:
    """Dechow F-Score card: misstatement-probability diagnostic."""
    dec = data.get("dechow") or {}
    if not dec:
        return html.Div()

    score = dec.get("f_score")
    if score is None:
        return html.Div()

    risk = dec.get("risk_label", "Unknown")
    sig_color = {
        "Low": GREEN,
        "Moderate": AMBER,
        "High": RED,
        "Unknown": MUTED,
    }.get(risk, MUTED)

    def _fmt(v, decimals=2, suffix=""):
        return f"{v:.{decimals}f}{suffix}" if v is not None else "N/A"

    metrics = [
        ("F-Score", _fmt(score, 0, "/100")),
        ("Probability", _fmt((dec.get("misstatement_probability") or 0) * 100, 1, "%")),
        ("Coverage", f"{dec.get('n_available', 0)}/7"),
        ("RSST Accruals", _fmt(dec.get("rsst_accruals"), 3)),
        ("Soft Assets", _fmt((dec.get("soft_assets") or 0) * 100, 1, "%") if dec.get("soft_assets") is not None else "N/A"),
        ("Flags", str(len(dec.get("flags") or []))),
    ]
    metric_rows = [_metric_data_row(lbl, val) for lbl, val in metrics]
    metric_rows.append(html.Div(dec.get("note", ""), className="fs-12 clr-muted fsi pt-8"))

    return _metric_scorecard(
        title="Dechow F-Score",
        score_text=f"{score:.0f}/100",
        score_color=sig_color,
        status_text=f"\u2014 {risk} Risk",
        body_children=metric_rows,
    )


def _fraud_dashboard_card(data: dict) -> html.Div:
    """Advanced Fraud Dashboard: aggregated forensic accounting view."""
    fd = data.get("fraud_dashboard") or {}
    if not fd:
        return html.Div()

    score = fd.get("fraud_risk_score")
    if score is None:
        return html.Div()

    risk = fd.get("fraud_risk_level", "Unknown")
    sig_color = {
        "Low": GREEN,
        "Moderate": AMBER,
        "High": RED,
        "Unknown": MUTED,
    }.get(risk, MUTED)

    red_flags = fd.get("red_flags") or []
    metrics = [
        ("Fraud Risk", f"{score:.0f}/100"),
        ("Accounting Quality", f"{fd.get('accounting_quality_score'):.0f}/100" if fd.get("accounting_quality_score") is not None else "N/A"),
        ("Beneish M-Score", f"{fd.get('beneish_m_score'):.2f}" if fd.get("beneish_m_score") is not None else "N/A"),
        ("Dechow F-Score", f"{fd.get('dechow_f_score'):.0f}/100" if fd.get("dechow_f_score") is not None else "N/A"),
        ("Red Flags", str(fd.get("red_flag_count", 0))),
    ]
    metric_rows = [_metric_data_row(lbl, val) for lbl, val in metrics]
    if red_flags:
        metric_rows.append(
            html.Div(
                ", ".join(str(flag).replace("_", " ") for flag in red_flags[:6]),
                className="fs-12 clr-muted fsi pt-8",
            )
        )

    return _metric_scorecard(
        title="Advanced Fraud Dashboard",
        score_text=f"{score:.0f}/100",
        score_color=sig_color,
        status_text=f"\u2014 {risk} Fraud Risk",
        body_children=metric_rows,
    )


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
        html.Div(className="metric-row-divider d-flex jc-between py-4 fs-12",
                 children=[
            html.Span(lbl, className="text-muted"),
            html.Span(val, className="clr-text fw-600"),
        ])
        for lbl, val in metrics
    ]
    return html.Div(className="scorecard", children=[
        html.Div(className="d-flex ai-center gap-10 pt-14 px-18 pb-10", children=[
            html.Span("Insider Activity", className="fs-14 fw-700 clr-text"),
            html.Span(f"{score:.0f}/100", className=f"fs-22 fw-800 {tone_class(sig_color)}"),
            html.Span(f"\u2014 {signal}", className=f"fs-13 {tone_class(sig_color)}"),
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

    metric_rows = [_metric_data_row(lbl, val) for lbl, val in metrics]

    return _metric_scorecard(
        title="Factor Momentum",
        score_text=f"{score:.0f}/100",
        score_color=sig_color,
        status_text=f"\u2014 {signal}",
        body_children=metric_rows,
    )


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
        html.Div(className="analysis-metric-row metric-row-divider--analysis d-flex jc-between gap-12 fs-12 py-4",
                 children=[
            html.Div([
                html.Div(s.get("label", s.get("name", "Signal")),
                         className="clr-text fw-600"),
                html.Div(s.get("description", ""),
                         className="clr-muted fs-11 metric-note-tight"),
            ]),
            html.Span(s.get("status", status),
                      className="clr-muted fw-700 wsnw"),
        ])
        for s in signals
    ]

    return _metric_scorecard(
        title="Alternative Data",
        score_text=f"{score:.0f}/100",
        score_color=sig_color,
        status_text=f"\u2014 {status}",
        status_color=MUTED,
        body_children=rows,
    )


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
            rows.append(html.Div(className="analysis-divider d-flex gap-10 ai-start py-6",
                                 children=[
                html.Span("✅" if on else "❌", className="piotroski-icon"),
                html.Div([
                    html.Div(f"{s['id']}: {s['label']}",
                             className=f"fs-13 fw-600 {tone_class(TEXT if on else MUTED)}"),
                    html.Div(s["note"],
                             className="fs-11 clr-muted piotroski-copy"),
                ]),
            ]))
        cat_blocks.append(html.Div(className="flex-1 min-w-240", children=[
            html.Div(cat_name.upper(),
                     className="piotroski-category fs-10 fw-700 clr-muted ls-008 mb-6 pb-4"),
            *rows,
        ]))
    return _metric_scorecard(
        title="Financial Health",
        score_text=f"{f_score}/9",
        score_color=lc,
        status_text=f"— {label.title()}",
        body_children=[
            html.Div(interp, className="piotroski-interpretation fs-12 clr-muted fsi"),
            html.Div(cat_blocks, className="d-flex gap-20 flex-wrap"),
        ],
    )

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
        comp_rows.append(
            _metric_data_row(
                lbl,
                html.Span(
                    f"{v:.3f}" if v is not None else "N/A",
                    className=f"stability-component-value fw-600 {tone_class(TEXT if v is not None else MUTED)}",
                ),
            )
        )
    return _metric_scorecard(
        title="Stability Score (Bankruptcy Risk)",
        card_class="stability-card",
        body_children=[
            html.Div(className=f"stability-zone stability-zone--{zone} br-10 mb-14 p-14", children=[
                html.Div(f"Z = {z_score:.2f}" if z_score is not None else "N/A",
                         className=f"stability-status fs-34 fw-800 {tone_class(zc)}"),
                html.Div(zone_label,
                         className=f"stability-status fs-16 fw-700 mt-2 {tone_class(zc)}"),
                html.Div(note, className="fs-11 clr-muted mt-6"),
                html.Div(f"Model: {model} · {n_avail}/5 components",
                         className="fs-10 clr-muted mt-3"),
            ]),
            *comp_rows,
        ],
    )

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
    def _risk_value_class(color):
        return (
            "risk-value--positive" if color == GREEN else
            "risk-value--danger" if color == RED else
            "risk-value--caution" if color == AMBER else
            "risk-value--neutral"
        )
    metric_cells = [
        html.Div(className="risk-metric-cell", children=[
            html.P(lbl, className="clr-muted fs-12 m-0"),
            html.P(val, className=f"risk-value {_risk_value_class(col)} fw-600 m-0 {tone_class(col)}"),
        ])
        for lbl, val, col in metrics
    ]
    risk_criteria = r.get("risk_criteria") or []
    return html.Div(className="risk-row",children=[
            
            html.Div(className="metric_cell risk-metric-grid scorecard", children=[
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
        _metric_data_row(lbl, html.Span(val, className=f"fw-600 {tone_class(col)}"))
        for lbl, val, col in metrics
    ]

    alert_banner = html.Div(
        "⚡ Fast Deterioration Alert — reduce position sizes",
        className="alert-deterioration br-6 px-12 py-6 fs-12 fw-700",
    ) if risk_alert else html.Div()

    return _metric_scorecard(
        title="Market Regime",
        score_text=regime.replace("_", " "),
        score_color=rc,
        status_text=f"· {risk_level}",
        status_color=rlc,
        body_children=[
            alert_banner,
            *metric_rows,
            html.Div(
                "Regime multiplier adjusts final score; max equity exposure governs position sizing. "
                "Based on SPY price history.",
                className="analysis-copy-leading fs-11 clr-muted mt-8 fsi",
            ),
        ],
    )


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
        html.Div(className="metric-row-divider d-flex jc-between py-4 fs-12",
                 children=[
            html.Span(label, className="text-muted"),
            html.Span(value, className="clr-text fw-600"),
        ])
        for label, value in metrics
    ]

    return html.Div(className="scorecard", children=[
        html.Div(className="d-flex ai-center gap-10 pt-14 px-18 pb-10 flex-wrap", children=[
            html.Span("Market Fear Gauge", className="fs-14 fw-700 clr-text"),
            html.Span(fear.get("badge", "Market Conditions"),
                      className=f"fs-18 fw-800 {tone_class(accent)}"),
        ]),
        html.Div(className="market-fear-body", children=[
            *metric_rows,
            html.P(
                fear.get("interpretation"),
                className="market-fear-interpretation",
            ),
            html.Div(
                "Informational only. Intrinsic value, quality scores, rankings, "
                "and portfolio sizing are unchanged by market fear.",
                className="analysis-copy-leading fs-11 clr-muted mt-8 fsi",
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
        className=f"fw-700 {tone_class(er_color)}"
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
    composite_bucket = (
        data.get("enhanced", {}).get("verdict")
        or data.get("composite", {}).get("verdict")
        or "N/A"
    ).replace("_", " ")
    composite_tone = tone_class(_verdict_color(
        data.get("enhanced", {}).get("verdict_label")
        or data.get("composite", {}).get("verdict_label", "pending")
    ))
    intrinsic_tone = tone_class(
        GREEN if (price and b_data.get("intrinsic_value") and price <= b_data["intrinsic_value"])
        else RED if b_data.get("intrinsic_value") else MUTED
    )
    moat_tone = tone_class({"A": GREEN, "B": BLUE, "C": AMBER, "D": RED}.get(b_data.get("grade", ""), MUTED))
    header = html.Div(
        className="company-header company-identity-header",
        children=[
            html.Div(
                className="company-header-left",
                children=[
                    html.H2(dcc.Link(
                        f"{symbol} — {name}",
                        href=f"/analyze/{symbol}/",
                        refresh=True,
                        className="company-title-link",
                        title=f"Open {name} company research",
                    )),
                    html.Div(className="company-meta", children=[
                        html.Span(f"Sector · {sector}", className="company-meta-item"),
                        html.Span(f"Composite · {composite_bucket}", className="company-meta-item"),
                    ]),
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
        className=tone_class(_score_color(g.get("pe"), RULES["pe"]))
    ),
    "Price-to-Earnings (P/E) Ratio. Compares share price to earnings per share. Lower values generally indicate a lower valuation. Traditional value investing often uses 15× as a reference threshold."
),
_stat(
    "P/B",
    html.Span(
        f"{g.get('pb') or 0:.2f}×",
        className=tone_class(_score_color(g.get("pb"), RULES["pb"]))
    ),
    "Price-to-Book (P/B) Ratio. Compares market price to book value per share. Lower values generally indicate a lower valuation. Traditional value investing often uses 1.5× as a reference threshold."
),
_stat(
    "ROE",
    html.Span(
        f"{q.get('roe') or 0:.1f}%",
        className=tone_class(_score_color(q.get("roe"), RULES["roe"]))
    ),
    "Return on Equity. Target: ≥15%."
),
_stat(
    "Op Margin",
    html.Span(
        f"{q.get('op_margin') or 0:.1f}%",
        className=tone_class(_score_color(q.get("op_margin"), RULES["op_margin"]))
    ),
    "Operating Margin. Target: ≥15%."
),
_stat(
    "Sharpe",
    html.Span(
        f"{r_data.get('sharpe') or 0:.2f}",
        className=tone_class(_score_color(r_data.get('sharpe'), RULES["sharpe"]))
    ),
    "Sharpe Ratio. ≥1.0 = good, ≥1.5 = excellent."
),
_stat(
    "Beta",
    html.Span(
        f"{r_data.get('beta') or 0:.2f}",
        className=tone_class(_score_color(r_data.get('beta'), RULES["beta"]))
    ),
    "Beta vs SPY. <1.0 = defensive, >1.0 = more volatile."
),
_stat(
    "F-Score",
    html.Span(
        f"{p_data.get('f_score') or 0}/9",
        className=tone_class(_score_color(p_data.get('f_score'), RULES["f_score"]))
    ),
    "Piotroski F-Score. 8–9 = strong."
),
                            _stat(
                                "Economic Moat Rating",
                                html.Span(
                                    f"${b_data.get('intrinsic_value'):.2f}"
                                    if b_data.get("intrinsic_value") else "N/A",
                                    className=tone_class(
                                        GREEN if (price and b_data.get("intrinsic_value") and price <= b_data["intrinsic_value"])
                                        else RED if b_data.get("intrinsic_value") else MUTED
                                    )
                                ),
                                "Intrinsic Value. Green = Price below IV (margin of safety)."
                            ),
                            _stat(
                                "Moat",
                                html.Span(
                                    f"{b_data.get('grade')} ({b_data.get('grade_label', '')})"
                                    if b_data.get("grade") else "N/A",
                                    className=tone_class({
                                            "A": GREEN,
                                            "B": BLUE,
                                            "C": AMBER,
                                            "D": RED
                                        }.get(b_data.get("grade"), MUTED))
                                ),
                                "Economic Moat Rating: A=Wide Moat (best), D=Avoid."
                            ),
                            _stat(
                                "Comp",
                                html.Span(
                                    f"{comp:.0f}/100",
                                    className=f"fw-700 {composite_tone}"
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
                                className=f"grade-letter {tone_class(_grade_color(g['grade']))}"
                            ),
                            html.Div("Intrinsic Value Estimate", className="grade-label"),
                            html.Div(
                                f"{g['total_score']}/{g['total_max']}",
                                className="grade-score"
                            ),
                        ]
                    ),
                    html.Div(
                        className="grade-badge badge-divider",
                        children=[
                            html.Div(
                                f"${b_data.get('intrinsic_value', 0):.0f}"
                                if b_data.get("intrinsic_value") else "—",
                                className=f"grade-letter fs-22 {intrinsic_tone}",
                            ),
                            html.Div("Economic Moat Rating", className="grade-label"),
                            html.Span(
                                f"{b_data.get('grade')} — {b_data.get('grade_label')}"
                                if b_data.get("grade") else "N/A",
                                className=f"grade-score ch moat-grade-link {moat_tone}",
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
    beneish_card = _beneish_card(data)
    dechow_card = _dechow_card(data)
    risk_card = _risk_card(data)
    fcf_quality_card = _fcf_quality_card(data)
    market_fear_card = _market_fear_card(data)
    regime_card = _regime_card(data)
    capital_allocation_card = _capital_allocation_card(data)
    growth_quality_card = _growth_quality_card(data)
    accounting_quality_card = _accounting_quality_card(data)
    fraud_dashboard_card = _fraud_dashboard_card(data)
    factor_momentum_card = _factor_momentum_card(data)
    alternative_data_card = _alternative_data_card(data)
    div_chart = _div_chart(g.get("div_history", []), symbol, data)
    graham_details = _graham_details_card(g, b_data)
    buffett_details = _buffett_details_card(data)
    sections = [
        ("analysis-overview", "Overview", [header, banner]),
        (
            "analysis-valuation",
            "Valuation",
            [html.Div(className="card-row bg", children=[graham_details, buffett_details])],
        ),
        (
            "analysis-moat",
            "Moat & Momentum",
            [html.Div(className="moment_quality_row", children=[buffett_card, momentum_card])],
        ),
        ("analysis-risk", "Risk", [risk_card]),
        (
            "analysis-scorecards",
            "Scorecards",
            [html.Div(className="card-row", children=[quality_card, graham_card])],
        ),
        (
            "analysis-accounting",
            "Accounting",
            [html.Div(className="quant_row", children=[piotroski_card, altman_card])]
            + ([html.Div(className="card-row", children=[accounting_quality_card, beneish_card])]
               if data.get("accounting_quality") or data.get("beneish") else [])
            + ([html.Div(className="card-row", children=[dechow_card, fraud_dashboard_card])]
               if data.get("dechow") or data.get("fraud_dashboard") else [])
            if p_data and a_data else [],
        ),
        (
            "analysis-regime",
            "Regime & Cash Flow",
            [
                html.Div(className="card-row", children=[market_fear_card, regime_card]),
                html.Div(className="card-row", children=[fcf_quality_card, factor_momentum_card]),
            ],
        ),
        (
            "analysis-growth",
            "Growth",
            [html.Div(className="card-row", children=[capital_allocation_card, growth_quality_card])],
        ),
        (
            "analysis-signals",
            "Signals",
            [
                html.Div(className="card-row", children=[_insider_activity_card(data), alternative_data_card]),
            ],
        ),
        (
            "analysis-charts",
            "Charts",
            [
                html.Div(
                    className="charts-grid",
                    children=[
                        _eps_chart(g.get("eps_history", []), symbol, data),
                        _price_chart(data.get("price_history"), data.get("spy_history"), symbol, data),
                    ],
                ),
                div_chart,
            ],
        ),
    ]
    sections = [(section_id, title, children) for section_id, title, children in sections if children]
    nav = html.Nav(
        className="analysis-jump-nav",
        **{"aria-label": "Analysis sections"},
        children=[
            html.A(
                href=f"#{section_id}",
                className="analysis-jump-link",
                title=title,
                children=[
                    html.Span(className="analysis-jump-dot"),
                    html.Span(title, className="analysis-jump-label"),
                ],
            )
            for section_id, title, _children in sections
        ],
    )
    return [
        nav,
        *[
            html.Section(
                id=section_id,
                className="analysis-section",
                children=children,
            )
            for section_id, _title, children in sections
        ],
    ]


def _stat(label, value, tooltip=None):
    return html.Div([
        html.Div(label, className="stat-label" + (" ch stat-label-tooltip" if tooltip else ""),
                 title=tooltip or ""),
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
        "high-conviction": GREEN,
        "buy": BLUE,
        "favorable": BLUE,
        "watch": AMBER,
        "balanced": AMBER,
        "hold": MUTED,
        "caution": MUTED,
        "avoid": RED,
        "unfavorable": RED,
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
            html.Div(className="criterion-left", children=[
                html.Div(c["label"], className="criterion-label"),
                html.Div(c.get("note", ""), className="criterion-note"),
                html.Div(className="score-bar", children=[
                    html.Progress(value=str(pct), max="100", className=f"score-bar-fill {tone_class(color)}")
                ]),
            ]),
            html.Div(f"{score}/{max_s}", className=f"criterion-pts {tone_class(color)}"),
        ]))
    return html.Div(className="scorecard", children=[
        html.Div(title, className="scorecard-header"),
        html.Div(rows),
    ])

def _eps_chart(eps_history: list, symbol: str, data: dict | None = None) -> html.Div:
    dataset = chart_service.get_analysis_chart_dataset(data or {"symbol": symbol, "graham": {"eps_history": eps_history}}, "eps_history")
    series = (dataset.get("series") or [{}])[0]
    if not series.get("x"):
        return html.Div(className="empty-card", children=[
            html.Div("EPS History", className="empty-card-title"),
            html.Div("No EPS data", className="empty-title"),
            html.Div("Insufficient data available", className="empty-msg"),
        ])
    y_values = series.get("y") or []
    colors = [GREEN if (v or 0) >= 0 else RED for v in y_values]
    fig = go.Figure(go.Bar(
        x=series.get("x"), y=y_values,
        marker_color=colors,
        text=[format_currency(v) for v in y_values],
        textposition="outside",
        textfont=dict(size=12, color=WHITE) 
    ))
    fig.update_layout(**_chart_layout(dataset.get("title") or f"{symbol} EPS History (10yr)"))
    return dcc.Graph(figure=fig, config={"displayModeBar": False})

def _price_chart(price_history_dict, spy_history_dict, symbol: str, data: dict | None = None) -> html.Div:
    dataset = chart_service.get_analysis_chart_dataset(
        data or {"symbol": symbol, "price_history": price_history_dict, "spy_history": spy_history_dict},
        "price_history",
    )
    series = dataset.get("series") or []
    if not series:
        return html.Div(className="empty-card", children=[
            html.Div("Price History", className="empty-card-title"),
            html.Div("No price data", className="empty-title"),
            html.Div("Insufficient history available", className="empty-msg"),
        ])
    fig = go.Figure()
    for item in series:
        is_spy = item.get("name") == "SPY"
        fig.add_trace(go.Scatter(
            x=item.get("x"), y=item.get("y"), name=item.get("name") or symbol,
            line=dict(color=MUTED if is_spy else BLUE, width=1.5 if is_spy else 2, dash="dot" if is_spy else None)
        ))
    fig.update_layout(**_chart_layout(dataset.get("title") or f"{symbol} vs SPY (10yr normalised)"))
    fig.update_yaxes(title_text="Index (100 = start)")
    return dcc.Graph(figure=fig, config={"displayModeBar": False})

def _div_chart(div_history: list, symbol: str, data: dict | None = None) -> html.Div:
    dataset = chart_service.get_analysis_chart_dataset(data or {"symbol": symbol, "graham": {"div_history": div_history}}, "dividend_history")
    series = (dataset.get("series") or [{}])[0]
    if not series.get("x"):
        return html.Div(className="empty-card", children=[
            html.Div("Dividend History", className="empty-card-title"),
            html.Div("No dividends", className="empty-title"),
            html.Div("This company has not paid dividends", className="empty-msg"),
        ])
    fig = go.Figure(go.Bar(
        x=series.get("x"),
        y=series.get("y"),
        marker_color=BLUE,
        text=[format_currency(v) for v in series.get("raw_y", [])],
        textposition="outside",
        textfont=dict(size=20, color=WHITE) 
    ))
    fig.update_layout(**_chart_layout(dataset.get("title") or f"{symbol} Dividend Payments (USD Millions)"))
    return dcc.Graph(figure=fig, config={"displayModeBar": False})

def _graham_details_card(g_data: dict, b_data: dict | None = None) -> html.Div:
    gn    = g_data.get("graham_number")
    price = g_data.get("price")
    mos   = g_data.get("margin_of_safety")
    b_data   = b_data or {}
    biv      = b_data.get("intrinsic_value")
    b_mos    = b_data.get("margin_of_safety")
    b_grade  = b_data.get("grade")
    b_glabel = b_data.get("grade_label", "")
    # Grade calculation for intrinsic score (0-105 scale)
    intrinsic_score = min(105, max(0, int((gn or 0) / (price or 1) * 50))) if gn and price else 0
    grade = "A" if intrinsic_score >= 80 else "B" if intrinsic_score >= 65 else "C" if intrinsic_score >= 50 else "D" if intrinsic_score >= 35 else "F"
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
            html.Span(value, className=f"detail-value {tone_class(_row_color(label))}"),
        ])
        for label, value in rows
    ]
    grade_rgba_map = {'A': '0,230,118', 'B': '22,119,255', 'C': '255,171,0', 'D': '255,23,68', 'F': '255,23,68'}
    grade_color_map = {"A": GREEN, "B": BLUE, "C": AMBER, "D": RED, "F": RED}
    g_rgba = grade_rgba_map.get(grade, '158,158,158')
    g_col  = grade_color_map.get(grade, MUTED)
    return html.Div(className="scorecard", children=[
        html.Div(className="card-header", children=[
            html.Span("Intrinsic Value Estimate"),
        ]),
        *detail_rows
    ])

def _buffett_details_card(data: dict) -> html.Div:
    b = data.get("buffett") or {}
    iv  = b.get("intrinsic_value")
    mos = b.get("margin_of_safety")
    price = b.get("price")
    grade = b.get("grade", "N/A")
    glabel = b.get("grade_label", "")
    moat_desc = _MOAT_TOOLTIPS.get(grade, "")
    rows = [
        ("Grade",             f"{grade} — {glabel}" if glabel else str(grade)),
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
            html.Span(value, className=f"detail-value {tone_class(iv_color if label == 'Margin of Safety' else TEXT)}"),
        ])
        for label, value in rows
    ]
    return html.Div(className="scorecard", children=[
        html.Div(className="card-header", children=[
            html.Span("Economic Moat Rating"),
        ]),
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
            bgcolor="rgba(0,0,0,0)",
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
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color=TEXT, family="Inter, system-ui, sans-serif"),
        margin=margin,
        xaxis=dict(showgrid=False, zeroline=False),
        yaxis=dict(gridcolor=BORDER, zeroline=False),
        legend=legend,
    )
