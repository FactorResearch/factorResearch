"""Rendering helpers for the stock analysis view and shared charts."""

from collections.abc import Callable
from datetime import datetime
from urllib.parse import quote

import plotly.graph_objects as go
from dash import dcc, html

from codes.app_modules.company_identity import company_logo
from codes.app_modules.design_system.financial import data_trust_panel, methodology_disclosure
from codes.app_modules.design_system.layouts import analysis_grid, container
from codes.app_modules.design_system.primitives import link, loading_container
from codes.app_modules.design_system.schemas import SectionDefinition
from codes.app_modules.design_system.states import chart_skeleton, section_error
from codes.domain.responses import AnalysisResponse
from codes.services import chart_service

from .config import AMBER, BLUE, BORDER, GREEN, MUTED, RED, TEXT, WHITE
from .css_classes import tone_class

_ANALYSIS_ROW_DIVIDER = "rgba(67, 52, 90, 0.65)"


def _safe_analysis_component(
    section_id: str, title: str, renderer: Callable[..., object], *args: object
) -> object:
    """Render one optional analysis section without aborting sibling sections.

    Args:
        section_id: Stable section identifier used by the local retry control.
        title: User-facing section name for the degraded-state message.
        renderer: Existing card renderer; financial calculations remain outside
            this presentation boundary.
        *args: Renderer inputs.

    Returns:
        The rendered component, or an accessible local error state when the
        optional renderer fails. The exception type is exposed only as a
        technical diagnostic identifier, never as user-facing content.
    """
    try:
        return renderer(*args)
    except Exception as error:
        return section_error(
            f"{title} is temporarily unavailable. Other analysis sections remain usable.",
            retry_id=f"analysis-{section_id}-retry",
            technical_id=type(error).__name__,
        )


def _verdict_presentation_label(verdict: object) -> str:
    """Map a semantic verdict code to a CSS-neutral presentation category."""
    normalized = str(verdict or "pending").lower().replace("_", "-").replace(" ", "-")
    aliases = {
        "strong-buy": "high-conviction",
        "attractive": "favorable",
        "buy": "favorable",
        "hold": "cautious",
        "avoid": "unfavorable",
    }
    return aliases.get(normalized, normalized)


def _clamp_pct(value) -> float:
    try:
        return min(max(float(value or 0), 0), 100)
    except (TypeError, ValueError):
        return 0.0


def _normalized_score(payload: dict, *keys: str) -> float | None:
    """Return a defensively normalized 0-100 score from an analysis payload."""
    for key in keys:
        value = payload.get(key)
        if value is None:
            continue
        try:
            score = float(value)
            maximum = float(payload.get("total_max") or 100)
        except (TypeError, ValueError):
            continue
        if maximum <= 0:
            continue
        return min(max(score / maximum * 100, 0), 100)
    return None


def analysis_score_drivers(data: dict) -> tuple[list[tuple[str, float]], list[tuple[str, float]]]:
    """Rank the strongest and weakest research factors for first-view disclosure."""
    enhanced = data.get("enhanced") or {}
    candidates = {
        "Valuation": _normalized_score(enhanced, "graham_pct", "valuation_score")
        or _normalized_score(data.get("graham") or {}, "total_score", "score"),
        "Quality": _normalized_score(enhanced, "quality_pct")
        or _normalized_score(data.get("quality") or {}, "total_score", "score"),
        "Profitability": _normalized_score(
            data.get("profitability") or {}, "profitability_score", "total_score"
        ),
        "Momentum": _normalized_score(enhanced, "momentum_pct")
        or _normalized_score(data.get("momentum") or {}, "total_score", "score"),
        "Growth": _normalized_score(enhanced, "growth_quality_pct")
        or _normalized_score(
            data.get("growth_quality") or {}, "growth_quality_score", "total_score"
        ),
        "Cash quality": _normalized_score(
            data.get("fcf_quality") or {}, "fcf_quality_score", "total_score"
        ),
    }
    ranked = sorted(
        ((label, score) for label, score in candidates.items() if score is not None),
        key=lambda item: (-item[1], item[0]),
    )
    if not ranked:
        return [], []
    return ranked[:2], sorted(ranked, key=lambda item: (item[1], item[0]))[:2]


def critical_analysis_warnings(data: dict) -> list[str]:
    """Keep material research caveats visible outside expandable methodology."""
    warnings = []
    altman = str((data.get("altman") or {}).get("zone_label") or "").lower()
    f_score = (data.get("piotroski") or {}).get("f_score")
    if "distress" in altman:
        warnings.append("Balance-sheet model is in the Altman distress zone.")
    if f_score is not None and f_score <= 3:
        warnings.append(f"Accounting strength is weak at F-Score {f_score}/9.")
    comp = (data.get("enhanced") or {}).get("composite_score")
    if comp is None:
        comp = data.get("composite_score")
    if comp is not None and comp < 40:
        warnings.append(f"Composite score is low at {comp:.0f}/100.")
    return warnings


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
        for value, angle in zip(values, angles, strict=False)
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
        for value, angle in zip(values, angles, strict=False)
    )
    labels = "".join(
        f'<text x="{center + 138 * math.cos(angle):.1f}" y="{center + 138 * math.sin(angle):.1f}" fill="#f5f9ff" stroke="#07182e" stroke-width="2.2" paint-order="stroke" font-family="Inter,Arial,sans-serif" font-size="12" font-weight="700" text-anchor="middle">{label}<tspan x="{center + 138 * math.cos(angle):.1f}" dy="16" fill="{color}" font-size="14" font-weight="800">{value:.0f}</tspan></text>'
        for (label, _), value, angle in zip(factors, values, angles, strict=False)
    )
    svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 360 350" role="img">'
        '<defs><filter id="hex-glow" x="-25%" y="-25%" width="150%" height="150%"><feGaussianBlur stdDeviation="2.5" result="blur"/><feMerge><feMergeNode in="blur"/><feMergeNode in="SourceGraphic"/></feMerge></filter>'
        f'<linearGradient id="hex-fill" x1="0" y1="0" x2="1" y2="1"><stop stop-color="{color}" stop-opacity="0.42"/><stop offset="1" stop-color="{color}" stop-opacity="0.10"/></linearGradient></defs>'
        f'<g>{grid}{axes}<line x1="80" y1="180" x2="280" y2="180" stroke="#4f80b2" stroke-opacity="0.72" stroke-width="1.2" />'
        f'<polygon points="{profile_points}" fill="url(#hex-fill)" stroke="{color}" stroke-width="2.6" filter="url(#hex-glow)" />{vertices}{labels}</g>'
        "</svg>"
    )
    description = ", ".join(f"{label} {value:.0f}" for (label, _), value in zip(factors, values, strict=False))
    return html.Figure(
        className="factor-hexagon",
        children=[
            html.Img(
                src=f"data:image/svg+xml,{quote(svg)}",
                alt=f"Six-factor score profile: {description}",
            )
        ],
    )


def _composite_trend_chart(symbol: str, color: str):
    dataset = chart_service.get_composite_trend_dataset(symbol)
    series = (dataset.get("series") or [{}])[0]
    scores = series.get("y") or []
    dates = series.get("x") or []
    if len(scores) < 2:
        return html.Div(
            "Composite trend will appear after the next score update.",
            className="composite-trend-empty",
        )

    change = scores[-1] - scores[0]
    direction = "↑" if change > 0 else "↓" if change < 0 else "→"
    figure = go.Figure(
        go.Scatter(
            x=dates,
            y=scores,
            mode="lines+markers",
            line={"color": color, "width": 2.5},
            marker={"color": color, "size": 5},
            hovertemplate="%{x}<br>Composite %{y:.1f}<extra></extra>",
        )
    )
    figure.update_layout(
        height=128,
        margin={"l": 4, "r": 4, "t": 4, "b": 4},
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        showlegend=False,
        hovermode="x unified",
        xaxis={"showgrid": False, "showticklabels": False, "zeroline": False},
        yaxis={
            "range": [0, 100],
            "showgrid": True,
            "gridcolor": "rgba(126, 157, 194, 0.18)",
            "showticklabels": False,
            "zeroline": False,
        },
    )
    return html.Div(
        className="composite-trend",
        children=[
            html.Div(
                f"Score trend {direction} {abs(change):.1f} pts", className="composite-trend-label"
            ),
            dcc.Graph(
                figure=figure,
                config={"displayModeBar": False, "responsive": True},
                className="composite-trend-graph",
            ),
        ],
    )


def _metric_data_row(label, value) -> html.Div:
    return html.Div(
        className="analysis-metric-row analysis-divider d-flex jc-between gap-12 py-4 fs-12",
        children=[
            html.Span(label, className="analysis-metric-label text-muted"),
            value
            if not isinstance(value, str)
            else html.Span(value, className="analysis-metric-value clr-text fw-600"),
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
    comp = data.get("composite") or {}
    g = data.get("graham") or {}
    b = data.get("buffett") or {}
    q = data.get("quality") or {}
    r = data.get("risk") or {}
    p = data.get("piotroski") or {}
    er = data.get("earnings_revision") or {}
    has_enh = bool(enhanced.get("composite_score") is not None)
    src = enhanced if has_enh else comp
    verdict = src.get("verdict", "N/A")
    verdict_label = _verdict_presentation_label(src.get("verdict"))
    verdict_desc = src.get("verdict_desc", "")
    score = src.get("composite_score", 0) or 0
    price = data.get("price")

    # Map verdict labels to mockup CSS classes
    vcls_map = {
        "strong-buy": "hc",
        "admirable": "hc",
        "high-conviction": "hc",
        "buy": "fav",
        "favorable": "fav",
        "watch": "bal",
        "balanced": "bal",
        "hold": "cau",
        "cautious": "cau",
        "caution": "cau",
        "avoid": "unfav",
        "unfavorable": "unfav",
        "pending": "bal",
    }
    vcls = vcls_map.get(verdict_label, "bal")

    # Six-axis profile: all axes are normalized so outward always means stronger.
    if has_enh:
        factor_data = [
            ("Composite", score),
            ("Intrinsic", enhanced.get("graham_pct", 0)),
            ("Quality", enhanced.get("quality_pct", 0)),
            ("Momentum", enhanced.get("momentum_pct", 0)),
            ("Safety", enhanced.get("risk_pct", 0)),
            ("Profit.", enhanced.get("profitability_pct", 0)),
        ]
    else:
        factor_data = [
            ("Composite", score),
            ("Intrinsic", comp.get("graham_pct", 0)),
            ("Quality", comp.get("quality_pct", 0)),
            ("Momentum", comp.get("momentum_pct") or 0),
            ("Safety", comp.get("safety_pct") or comp.get("altman_pct", 0)),
            ("Profit.", comp.get("profitability_pct", 0)),
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
        ("Market Cap", mcap_str),
        ("Price", price_str),
        ("Intrinsic", intrinsic_str),
        ("Buffett Moat", moat_str),
        ("P/E", f"{g.get('pe'):.1f}×" if g.get("pe") is not None else "N/A"),
        ("P/B", f"{g.get('pb'):.2f}×" if g.get("pb") is not None else "N/A"),
        ("ROE", f"{q.get('roe'):.1f}%" if q.get("roe") is not None else "N/A"),
        ("Op. Margin", f"{q.get('op_margin'):.1f}%" if q.get("op_margin") is not None else "N/A"),
        ("Sharpe", f"{r.get('sharpe'):.2f}" if r.get("sharpe") is not None else "N/A"),
        ("Beta", f"{r.get('beta'):.2f}" if r.get("beta") is not None else "N/A"),
        ("F-Score", f"{p.get('f_score')}/9" if p.get("f_score") is not None else "N/A"),
        (
            "E. Revision",
            f"{er.get('total_score'):.0f}/100" if er.get("total_score") is not None else "N/A",
        ),
    ]
    stats = html.Div(
        className="composite-stats",
        children=[
            html.Div(
                className="composite-stat",
                children=[
                    html.Div(label, className="composite-stat-label"),
                    html.Div(value, className="composite-stat-value"),
                ],
            )
            for label, value in stat_values
        ],
    )

    flags = _analysis_flags(data)

    # Flags remain available to the legacy composite renderer for compatibility.
    return _composite_banner_with_flags(data, flags)


def _analysis_flags(data: dict) -> list:
    """Return the original model signal pills without changing their meaning."""
    enhanced = data.get("enhanced") or {}
    comp = data.get("composite") or {}
    flags = []
    if enhanced.get("value_trap_warning") or comp.get("value_trap_warning"):
        flags.append(
            html.Span(
                "⚠️ Value Trap Risk",
                className="analysis-flag analysis-flag--value-trap br-6 fs-12 fw-600",
            )
        )
    if enhanced.get("compounder_flag"):
        flags.append(
            html.Span(
                "🚀 Compounder Signal",
                className="analysis-flag analysis-flag--compounder br-6 fs-12 fw-600",
            )
        )
    if enhanced.get("altman_cap_applied"):
        flags.append(
            html.Span(
                "🔴 Altman Distress Cap Active",
                className="analysis-flag analysis-flag--distress br-6 fs-12 fw-600",
            )
        )
    if (data.get("growth_quality") or {}).get("acquisition_driven_growth"):
        flags.append(
            html.Span(
                "🟠 Acquisition-Driven Growth",
                className="analysis-flag analysis-flag--acquisition br-6 fs-12 fw-600",
            )
        )

    return flags


def _composite_banner_with_flags(data: dict, flags: list) -> html.Div:
    """Render the composite banner using a precomputed original flag list."""
    enhanced = data.get("enhanced") or {}
    comp = data.get("composite") or {}
    g = data.get("graham") or {}
    b = data.get("buffett") or {}
    q = data.get("quality") or {}
    r = data.get("risk") or {}
    p = data.get("piotroski") or {}
    er = data.get("earnings_revision") or {}
    has_enh = bool(enhanced.get("composite_score") is not None)
    src = enhanced if has_enh else comp
    verdict = src.get("verdict", "N/A")
    verdict_label = _verdict_presentation_label(src.get("verdict"))
    verdict_desc = src.get("verdict_desc", "")
    score = src.get("composite_score", 0) or 0
    price = data.get("price")
    vcls_map = {"strong-buy": "hc", "admirable": "hc", "high-conviction": "hc", "buy": "fav", "favorable": "fav", "watch": "bal", "balanced": "bal", "hold": "cau", "cautious": "cau", "caution": "cau", "avoid": "unfav", "unfavorable": "unfav", "pending": "bal"}
    vcls = vcls_map.get(verdict_label, "bal")
    if has_enh:
        factor_data = [("Composite", score), ("Intrinsic", enhanced.get("graham_pct", 0)), ("Quality", enhanced.get("quality_pct", 0)), ("Momentum", enhanced.get("momentum_pct", 0)), ("Safety", enhanced.get("risk_pct", 0)), ("Profit.", enhanced.get("profitability_pct", 0))]
    else:
        factor_data = [("Composite", score), ("Intrinsic", comp.get("graham_pct", 0)), ("Quality", comp.get("quality_pct", 0)), ("Momentum", comp.get("momentum_pct") or 0), ("Safety", comp.get("safety_pct") or comp.get("altman_pct", 0)), ("Profit.", comp.get("profitability_pct", 0))]
    verdict_colors = {"hc": GREEN, "fav": BLUE, "bal": AMBER, "cau": "#ff6d00", "unfav": RED}
    verdict_color = verdict_colors[vcls]
    hexagon = _factor_hexagon(factor_data, verdict_color)
    trend = _composite_trend_chart(data.get("symbol", ""), verdict_color)
    market_cap = g.get("market_cap")
    mcap_str = _fmt_market_cap(market_cap) if market_cap else "N/A"
    graham_score = g.get("total_score", 0)
    graham_max = g.get("total_max", 105)
    intrinsic_str = f"{g.get('grade', 'N/A')} {graham_score}/{graham_max}"
    moat_grade = b.get("grade", "N/A")
    moat_label = b.get("grade_label", "")
    moat_str = f"{moat_grade} — {moat_label}" if moat_label else moat_grade
    price_str = f"${price:.2f}" if price else "N/A"
    stat_values = [("Market Cap", mcap_str), ("Price", price_str), ("Intrinsic", intrinsic_str), ("Buffett Moat", moat_str), ("P/E", f"{g.get('pe'):.1f}×" if g.get("pe") is not None else "N/A"), ("P/B", f"{g.get('pb'):.2f}×" if g.get("pb") is not None else "N/A"), ("ROE", f"{q.get('roe'):.1f}%" if q.get("roe") is not None else "N/A"), ("Op. Margin", f"{q.get('op_margin'):.1f}%" if q.get("op_margin") is not None else "N/A"), ("Sharpe", f"{r.get('sharpe'):.2f}" if r.get("sharpe") is not None else "N/A"), ("F-Score", f"{p.get('f_score')}/9" if p.get("f_score") is not None else "N/A"), ("E. Revision", f"{er.get('total_score'):.0f}/100" if er.get("total_score") is not None else "N/A")]
    stats = html.Div(className="composite-stats", children=[html.Div(className="composite-stat", children=[html.Div(label, className="composite-stat-label"), html.Div(value, className="composite-stat-value")]) for label, value in stat_values])
    return html.Div(
        className="composite-banner",
        children=[
            html.Div(
                className="composite-top",
                children=[
                    html.Div(
                        className="composite-score-wrap",
                        children=[
                            html.Div(f"{score:.0f}", className="composite-score"),
                            html.Div("Composite Score", className="composite-label"),
                            html.Div(
                                verdict.upper(),
                                className=f"composite-verdict {vcls}",
                                title=verdict_desc,
                            ),
                            trend,
                        ],
                    ),
                    html.Div(className="analysis-hexagon-wrap", children=[hexagon]),
                    stats,
                ],
            ),
            html.Div(),
        ],
    )


def _fcf_quality_card(data: dict) -> html.Div:
    """FCF Quality card: key metrics + scorecard criteria."""
    fcf = data.get("fcf_quality") or {}
    if not fcf:
        return html.Div()

    score = fcf.get("fcf_quality_score")
    signal = fcf.get("signal", "")
    if score is None:
        return html.Div()

    sig_color = {
        "STRONG_CASH_GENERATOR": GREEN,
        "HIGH_CASH_QUALITY": BLUE,
        "NEUTRAL": AMBER,
        "WEAK_CASH_QUALITY": MUTED,
        "EARNINGS_QUALITY_RISK": RED,
    }.get(signal, MUTED)

    metrics = [
        ("FCF", _model_metric(fcf.get("fcf"), ",.0f", prefix="$")),
        ("Operating CF", _model_metric(fcf.get("operating_cash_flow"), ",.0f", prefix="$")),
        ("CapEx", _model_metric(fcf.get("capex"), ",.0f", prefix="$")),
        ("FCF Margin", _model_metric(fcf.get("fcf_margin"), ".1f", "%")),
        ("FCF Conversion", _model_metric(fcf.get("fcf_conversion"), ".1f", "%")),
        ("FCF Stability CV", _model_metric(fcf.get("fcf_stability"), ".3f")),
        ("Growth Consist.", _model_metric(fcf.get("fcf_growth_consistency"), ".0%")),
        ("Accrual Ratio", _model_metric(fcf.get("accrual_ratio"), ".4f")),
        ("FCF CAGR 5yr", _model_metric(fcf.get("fcf_cagr_5y"), ".1f", "%")),
    ]

    metric_rows = [_metric_data_row(lbl, val) for lbl, val in metrics]

    return _metric_scorecard(
        title="FCF Quality",
        score_text=f"{score:.0f}/100",
        score_color=sig_color,
        status_text=f"— {signal.replace('_', ' ').title()}",
        body_children=metric_rows,
    )


def _capital_allocation_card(data: dict) -> html.Div:
    """Capital Allocation card: key metrics display."""
    ca = data.get("capital_allocation") or {}
    if not ca:
        return html.Div()

    score = ca.get("capital_allocation_score")
    signal = ca.get("signal", "")
    if score is None:
        return html.Div()

    sig_color = {
        "EXCELLENT_ALLOCATOR": GREEN,
        "GOOD_ALLOCATOR": BLUE,
        "AVERAGE_ALLOCATOR": AMBER,
        "POOR_ALLOCATOR": MUTED,
        "CAPITAL_DESTROYER": RED,
    }.get(signal, MUTED)

    def _fmt(v, fmt=".2f", prefix="", suffix=""):
        if v is None:
            return "N/A"
        try:
            return f"{prefix}{v:{fmt}}{suffix}"
        except (ValueError, TypeError):
            return "N/A"

    roic_spread_color = GREEN if (ca.get("roic_spread") or 0) > 0 else RED
    dilution_color = (
        GREEN
        if (ca.get("dilution_rate") or 1) <= 0
        else (AMBER if (ca.get("dilution_rate") or 0) < 3 else RED)
    )
    debt_color = GREEN if (ca.get("debt_trend") or 1) <= 0 else AMBER

    metrics = [
        ("ROIC", _fmt(ca.get("roic"), ".1f", suffix="%")),
        (
            "ROIC Spread (−10%)",
            html.Span(
                _fmt(ca.get("roic_spread"), "+.1f", suffix="%"),
                className=f"fw-600 {tone_class(roic_spread_color)}",
            ),
        ),
        ("Incremental ROIC", _fmt(ca.get("incremental_roic"), ".1f", suffix="%")),
        (
            "Reinvestment Rate",
            _fmt(ca.get("reinvestment_rate"), ".1%")
            if ca.get("reinvestment_rate") is not None
            else "N/A",
        ),
        ("Reinvest Method", ca.get("reinvestment_method", "N/A")),
        ("Buyback Yield", _fmt(ca.get("buyback_yield"), ".2f", suffix="%")),
        ("Dividend Yield", _fmt(ca.get("dividend_yield_implied"), ".2f", suffix="%")),
        ("Shareholder Yield", _fmt(ca.get("shareholder_yield"), ".2f", suffix="%")),
        (
            "Dilution Rate",
            html.Span(
                _fmt(ca.get("dilution_rate"), "+.2f", suffix="%"),
                className=f"fw-600 {tone_class(dilution_color)}",
            ),
        ),
        (
            "Debt Trend (Δ D/E)",
            html.Span(
                _fmt(ca.get("debt_trend"), "+.3f"), className=f"fw-600 {tone_class(debt_color)}"
            ),
        ),
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


def _insider_activity_card(data: dict) -> html.Div:
    """Insider buying/selling activity card."""
    ia = data.get("insider_activity") or {}
    if not ia and data.get("secondary_status") in {"pending", "failed"}:
        failed = data.get("secondary_status") == "failed"
        return _metric_scorecard(
            title="Insider Activity",
            score_text="Unavailable" if failed else "Loading",
            score_color=MUTED,
            status_text="Try later" if failed else "Background enrichment",
            status_color=MUTED,
            body_children=[
                html.Div(
                    "Primary analysis is ready. Insider filings are loading separately.",
                    className="analysis-copy-leading fs-11 clr-muted",
                )
            ],
        )
    if not ia or ia.get("low_coverage"):
        return html.Div()
    score = ia.get("insider_confidence_score")
    signal = ia.get("signal", "NEUTRAL")
    if score is None:
        return html.Div()
    sig_color = {"BULLISH": GREEN, "NEUTRAL": AMBER, "BEARISH": RED}.get(signal, MUTED)

    def _fmt(v, fmt=".2f", suffix=""):
        return f"{v:{fmt}}{suffix}" if v is not None else "N/A"

    cluster_txt = "\u2705 Detected" if ia.get("cluster_detected") else "\u2014"
    metrics = [
        ("Net Insider Buying", _fmt(ia.get("net_insider_buying"), "+.2f", "%")),
        ("Cluster Buying", cluster_txt),
        ("Type Quality Score", _fmt(ia.get("insider_type_quality"), ".1f", "/100")),
        ("Buy Transactions", str(ia.get("n_buy_transactions", 0))),
        ("Sell Transactions", str(ia.get("n_sell_transactions", 0))),
        ("Distinct Buyers", str(ia.get("n_distinct_buyers", 0))),
    ]
    return _metric_scorecard(
        title="Insider Activity",
        score_text=f"{score:.0f}/100",
        score_color=sig_color,
        status_text=f"\u2014 {signal}",
        body_children=[_metric_data_row(label, value) for label, value in metrics],
    )


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
    if not ad and data.get("secondary_status") in {"pending", "failed"}:
        failed = data.get("secondary_status") == "failed"
        return _metric_scorecard(
            title="Alternative Data",
            score_text="Unavailable" if failed else "Loading",
            score_color=MUTED,
            status_text="Try later" if failed else "Background enrichment",
            status_color=MUTED,
            body_children=[
                html.Div(
                    "Ownership, filings, and patent signals will appear without blocking this page.",
                    className="analysis-copy-leading fs-11 clr-muted",
                )
            ],
        )
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
        html.Div(
            className="analysis-metric-row metric-row-divider--analysis d-flex jc-between gap-12 fs-12 py-4",
            children=[
                html.Div(
                    [
                        html.Div(
                            s.get("label", s.get("name", "Signal")), className="clr-text fw-600"
                        ),
                        html.Div(
                            s.get("description", ""), className="clr-muted fs-11 metric-note-tight"
                        ),
                    ]
                ),
                html.Span(s.get("status", status), className="clr-muted fw-700 wsnw"),
            ],
        )
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
    f_score = p.get("f_score", 0)
    label = p.get("label", "neutral")
    interp = p.get("interpretation", "")
    signals = p.get("signals", [])
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
            rows.append(
                html.Div(
                    className="analysis-divider d-flex gap-10 ai-start py-6",
                    children=[
                        html.Span("✅" if on else "❌", className="piotroski-icon"),
                        html.Div(
                            [
                                html.Div(
                                    f"{s['id']}: {s['label']}",
                                    className=f"fs-13 fw-600 {tone_class(TEXT if on else MUTED)}",
                                ),
                                html.Div(s["note"], className="fs-11 clr-muted piotroski-copy"),
                            ]
                        ),
                    ],
                )
            )
        cat_blocks.append(
            html.Div(
                className="flex-1 min-w-240",
                children=[
                    html.Div(
                        cat_name.upper(),
                        className="piotroski-category fs-10 fw-700 clr-muted ls-008 mb-6 pb-4",
                    ),
                    *rows,
                ],
            )
        )
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
    z_score = a.get("z_score")
    zone = a.get("zone", "unknown")
    zone_label = a.get("zone_label", "Unknown")
    note = a.get("note", "")
    model = a.get("model", "")
    n_avail = a.get("n_available", 0)
    comps = a.get("components") or {}
    zc = {"safe": GREEN, "grey": AMBER, "distress": RED, "unknown": MUTED}.get(zone, MUTED)
    comp_labels = [
        ("x1_working_capital", "X1 — Working Capital / Assets"),
        ("x2_retained_earnings", "X2 — Retained Earnings / Assets"),
        ("x3_ebit_ratio", "X3 — EBIT / Assets"),
        ("x4_equity_liabilities", "X4 — Market Cap / Liabilities"),
        ("x5_asset_turnover", "X5 — Revenue / Assets"),
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
            html.Div(
                className=f"stability-zone stability-zone--{zone} br-10 mb-14 p-14",
                children=[
                    html.Div(
                        f"Z = {z_score:.2f}" if z_score is not None else "N/A",
                        className=f"stability-status fs-34 fw-800 {tone_class(zc)}",
                    ),
                    html.Div(
                        zone_label, className=f"stability-status fs-16 fw-700 mt-2 {tone_class(zc)}"
                    ),
                    html.Div(note, className="fs-11 clr-muted mt-6"),
                    html.Div(
                        f"Model: {model} · {n_avail}/5 components", className="fs-10 clr-muted mt-3"
                    ),
                ],
            ),
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
        (
            "Sharpe Ratio (≥1.0 good)",
            _fv(r.get("sharpe")),
            _mc(r.get("sharpe"), good_above=1.0, bad_below=0),
        ),
        (
            "Sortino Ratio (≥1.5 good)",
            _fv(r.get("sortino")),
            _mc(r.get("sortino"), good_above=1.5, bad_below=0),
        ),
        (
            "Beta vs SPY (<1.0 defensive)",
            _fv(r.get("beta")),
            _mc(r.get("beta"), good_below=1.0, bad_above=1.5),
        ),
        (
            "Alpha (>0 outperforms)",
            _fv(r.get("alpha"), 1, "%"),
            _mc(r.get("alpha"), good_above=0, bad_below=-5),
        ),
        (
            "Max Drawdown (>-30% ok)",
            _fv(r.get("max_drawdown"), 1, "%"),
            _mc(r.get("max_drawdown"), bad_below=-30),
        ),
        (
            "Ann. Volatility (<25% ok)",
            _fv(r.get("volatility_annual"), 1, "%"),
            _mc(r.get("volatility_annual"), good_below=25, bad_above=40),
        ),
        ("VaR 95% (monthly)", _fv(r.get("var_95"), 1, "%"), MUTED),
        ("CVaR 95% (monthly)", _fv(r.get("cvar_95"), 1, "%"), MUTED),
        (
            "Ann. Return (≥10% good)",
            _fv(r.get("annual_return"), 1, "%"),
            _mc(r.get("annual_return"), good_above=10, bad_below=0),
        ),
        (
            "Calmar Ratio (≥1.0 good)",
            _fv(r.get("calmar")),
            _mc(r.get("calmar"), good_above=1.0, bad_below=0),
        ),
    ]

    def _risk_value_class(color):
        return (
            "risk-value--positive"
            if color == GREEN
            else "risk-value--danger"
            if color == RED
            else "risk-value--caution"
            if color == AMBER
            else "risk-value--neutral"
        )

    metric_cells = [
        html.Div(
            className="risk-metric-cell",
            children=[
                html.P(lbl, className="clr-muted fs-12 m-0"),
                html.P(
                    val,
                    className=f"risk-value {_risk_value_class(col)} fw-600 m-0 {tone_class(col)}",
                ),
            ],
        )
        for lbl, val, col in metrics
    ]
    risk_criteria = r.get("risk_criteria") or []
    risk_breakdown = (
        _render_scorecard("Risk Score Breakdown", risk_criteria, "risk")
        if risk_criteria
        else None
    )
    risk_children = [
        html.Div(
            className="metric_cell risk-metric-grid scorecard",
            children=[
                html.P(
                    f"Risk & Performance — {n_yrs:.0f}yr History", className="scorecard-header"
                ),
                *metric_cells,
            ],
        )
    ]
    if risk_breakdown is not None:
        risk_children.append(risk_breakdown)
    return html.Div(
        className="risk-row",
        children=risk_children,
    )


def _regime_card(data: dict) -> html.Div:
    """Regime model card: market condition + portfolio risk overlay."""
    r = data.get("regime") or {}
    ov = data.get("regime_overlay") or {}
    if not r or r.get("error"):
        return html.Div()

    regime = r.get("regime", "N/A")
    risk_level = r.get("risk_level", "N/A")
    risk_alert = r.get("risk_alert", False)
    multiplier = ov.get("regime_multiplier", 1.0)
    exposure = ov.get("max_equity_exposure", 1.0)
    adjusted = ov.get("adjusted_score")
    trend_score = r.get("market_trend_score")
    vol_pct = r.get("volatility_percentile")
    drawdown = r.get("drawdown_depth")

    regime_colors = {
        "BULL_LOW_VOL": GREEN,
        "BULL_HIGH_VOL": AMBER,
        "SIDEWAYS": MUTED,
        "BEAR_LOW_VOL": AMBER,
        "BEAR_HIGH_VOL": RED,
        "CRISIS": RED,
    }
    risk_colors = {"NORMAL": GREEN, "ELEVATED": AMBER, "HIGH": RED, "CRISIS": RED}
    rc = regime_colors.get(regime, MUTED)
    rlc = risk_colors.get(risk_level, MUTED)

    def _fmt(v, suffix="", decimals=1):
        return f"{v:.{decimals}f}{suffix}" if v is not None else "N/A"

    metrics = [
        (
            "Trend Score",
            _fmt(trend_score, "/100", 0),
            AMBER
            if trend_score and trend_score < 40
            else GREEN
            if trend_score and trend_score >= 60
            else MUTED,
        ),
        (
            "Vol Percentile",
            _fmt(vol_pct, "%", 0),
            RED if vol_pct and vol_pct >= 75 else AMBER if vol_pct and vol_pct >= 50 else GREEN,
        ),
        (
            "Drawdown (252D)",
            _fmt(drawdown, "%"),
            RED
            if drawdown and drawdown <= -20
            else AMBER
            if drawdown and drawdown <= -10
            else GREEN,
        ),
        ("SMA 50", f"${r.get('sma_50'):.2f}" if r.get("sma_50") else "N/A", TEXT),
        ("SMA 200", f"${r.get('sma_200'):.2f}" if r.get("sma_200") else "N/A", TEXT),
        ("Vol 20D (ann.)", _fmt(r.get("vol_20d"), "%"), TEXT),
        ("Vol 60D (ann.)", _fmt(r.get("vol_60d"), "%"), TEXT),
        (
            "Regime Multiplier",
            f"×{multiplier:.2f}",
            GREEN if multiplier >= 1.0 else AMBER if multiplier >= 0.8 else RED,
        ),
        (
            "Max Equity Exp.",
            f"{exposure * 100:.0f}%",
            GREEN if exposure >= 1.0 else AMBER if exposure >= 0.7 else RED,
        ),
        (
            "Adjusted Score",
            f"{adjusted:.1f}/100" if adjusted is not None else "N/A",
            GREEN if adjusted and adjusted >= 60 else AMBER if adjusted and adjusted >= 40 else RED,
        ),
    ]

    metric_rows = [
        _metric_data_row(lbl, html.Span(val, className=f"fw-600 {tone_class(col)}"))
        for lbl, val, col in metrics
    ]

    alert_banner = (
        html.Div(
            "⚡ Fast Deterioration Alert — reduce position sizes",
            className="alert-deterioration br-6 px-12 py-6 fs-12 fw-700",
        )
        if risk_alert
        else html.Div()
    )

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


def _comomentum_card(data: dict) -> html.Div:
    """Market crowding card backed by the CoMomentum regime input."""
    percentile = (data.get("regime") or {}).get("comomentum_percentile")
    if percentile is None:
        return _metric_scorecard(
            title="CoMomentum Crowding",
            score_text="Unavailable",
            score_color=MUTED,
            status_text="Legacy cache",
            status_color=MUTED,
            body_children=[
                html.Div(
                    "Run a fresh analysis to calculate the market crowding signal.",
                    className="analysis-copy-leading fs-11 clr-muted fsi",
                )
            ],
        )

    if percentile >= 75:
        signal, color = "HIGH", RED
        interpretation = "Momentum leaders are moving together. Crowding can make a bullish market regime more fragile."
    elif percentile <= 25:
        signal, color = "LOW", GREEN
        interpretation = (
            "Momentum leaders are moving independently, indicating limited crowding pressure."
        )
    else:
        signal, color = "NORMAL", BLUE
        interpretation = "Momentum crowding is within its normal historical range."

    rounded_percentile = int(round(percentile))
    suffix = (
        "th"
        if 10 <= rounded_percentile % 100 <= 20
        else {1: "st", 2: "nd", 3: "rd"}.get(rounded_percentile % 10, "th")
    )

    return _metric_scorecard(
        title="CoMomentum Crowding",
        score_text=f"{rounded_percentile}{suffix} pct",
        score_color=color,
        status_text=signal,
        status_color=color,
        body_children=[
            _metric_data_row("Crowding percentile", f"{percentile:.1f}/100"),
            _metric_data_row("Signal", html.Span(signal, className=f"fw-600 {tone_class(color)}")),
            html.Div(interpretation, className="analysis-copy-leading fs-11 clr-muted mt-8 fsi"),
        ],
    )


def _model_metric(value, fmt=".2f", suffix="", prefix="") -> str:
    if value is None:
        return "N/A"
    try:
        return f"{prefix}{value:{fmt}}{suffix}"
    except (TypeError, ValueError):
        return "N/A"


def _greenblatt_card(data: dict) -> html.Div:
    result = data.get("greenblatt") or {}
    score = result.get("magic_score")
    return _metric_scorecard(
        title="Greenblatt Value",
        score_text=f"{score:.0f}/100" if score is not None else "Single stock",
        score_color=GREEN if score is not None and score >= 60 else MUTED,
        status_text="Magic Formula",
        status_color=MUTED,
        body_children=[
            _metric_data_row("Earnings yield", _model_metric(result.get("earnings_yield"), ".2f")),
            _metric_data_row("FCF yield", _model_metric(result.get("fcf_yield"), ".2f")),
            _metric_data_row("Return on capital", _model_metric(result.get("roic"), ".2f")),
            html.Div(
                "Universe ranking is required for a Magic Formula score.",
                className="analysis-copy-leading fs-11 clr-muted mt-8 fsi",
            ),
        ],
    )


def _profitability_card(data: dict) -> html.Div:
    result = data.get("profitability") or {}
    score = result.get("profitability_score")
    color = (
        GREEN
        if score is not None and score >= 65
        else RED
        if score is not None and score < 40
        else AMBER
    )
    return _metric_scorecard(
        title="Structural Profitability",
        score_text=f"{score:.0f}/100" if score is not None else "Unavailable",
        score_color=color if score is not None else MUTED,
        status_text=(result.get("signal") or "No data").replace("_", " ").title(),
        status_color=color if score is not None else MUTED,
        body_children=[
            _metric_data_row("ROIC", _model_metric(result.get("roic"), ".1f", "%")),
            _metric_data_row("Adjusted ROE", _model_metric(result.get("roe_adjusted"), ".1f", "%")),
            _metric_data_row(
                "Gross profitability", _model_metric(result.get("gross_profitability"), ".2f")
            ),
            _metric_data_row(
                "Margin stability", _model_metric(result.get("operating_margin_stability"), ".1f")
            ),
            _metric_data_row(
                "Incremental ROIC", _model_metric(result.get("incremental_roic"), ".1f", "%")
            ),
        ],
    )


def _benchmark_bias_card(data: dict) -> html.Div:
    benchmark = data.get("spy_benchmark") or {}
    bias = data.get("bias") or {}
    label = (bias.get("bias") or "Unavailable").replace("_", " ").title()
    color = (
        GREEN
        if label == "Outperform"
        else RED
        if label == "Underperform"
        else AMBER
        if bias
        else MUTED
    )
    probability = benchmark.get("probability_outperform")
    return _metric_scorecard(
        title="SPY Benchmark & Bias",
        score_text=label,
        score_color=color,
        status_text=f"{probability * 100:.0f}% probability"
        if probability is not None
        else "No benchmark",
        status_color=color,
        body_children=[
            _metric_data_row(
                "Outperform probability",
                f"{probability * 100:.1f}%" if probability is not None else "N/A",
            ),
            _metric_data_row(
                "Target CAGR", _model_metric(benchmark.get("cagr_target"), ".1f", "%")
            ),
            _metric_data_row("SPY CAGR", _model_metric(benchmark.get("cagr_spy"), ".1f", "%")),
            _metric_data_row("Alpha", _model_metric(benchmark.get("alpha"), ".1f", "%")),
            _metric_data_row(
                "Confidence",
                f"{bias.get('confidence') * 100:.0f}%"
                if bias.get("confidence") is not None
                else "N/A",
            ),
        ],
    )


def _market_fear_card(data: dict) -> html.Div:
    """Display-only VIX/VIXEQ Market Fear Gauge."""
    fear = data.get("market_fear") or {}
    if not fear or fear.get("error"):
        return _metric_scorecard(
            title="Market Fear Gauge",
            score_text="Unavailable",
            score_color=MUTED,
            status_text="Market data",
            status_color=MUTED,
            body_children=[
                html.Div(
                    "VIX and VIXEQ data could not be loaded for this analysis.",
                    className="analysis-copy-leading fs-11 clr-muted fsi",
                )
            ],
        )

    color_map = {
        "green": GREEN,
        "blue": BLUE,
        "amber": AMBER,
        "orange": "#f97316",
        "red": RED,
    }
    regime_color = {
        "VERY_LOW_FEAR": "green",
        "NORMAL": "blue",
        "ELEVATED": "amber",
        "HIGH": "orange",
        "EXTREME": "red",
    }
    accent = color_map.get(regime_color.get(fear.get("regime")), MUTED)

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
        html.Div(
            className="metric-row-divider d-flex jc-between py-4 fs-12",
            children=[
                html.Span(label, className="text-muted"),
                html.Span(value, className="clr-text fw-600"),
            ],
        )
        for label, value in metrics
    ]

    return html.Div(
        className="scorecard",
        children=[
            html.Div(
                className="d-flex ai-center gap-10 pt-14 px-18 pb-10 flex-wrap",
                children=[
                    html.Span("Market Fear Gauge", className="fs-14 fw-700 clr-text"),
                    html.Span(
                        fear.get("badge", "Market Conditions"),
                        className=f"fs-18 fw-800 {tone_class(accent)}",
                    ),
                ],
            ),
            html.Div(
                className="market-fear-body",
                children=[
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
                ],
            ),
        ],
    )


def _build_analysis_content_legacy(data: dict | AnalysisResponse) -> list:
    """Render analysis data into a compact, summary-first analysis layout."""
    if isinstance(data, AnalysisResponse):
        data = data.presentation_data()
    if not data or "error" in data:
        return []

    symbol = data["symbol"]
    name = data["name"]
    sector = data["sector"]
    g = data["graham"]
    q = data["quality"]
    m = data["momentum"]
    enhanced = data.get("enhanced") or {}
    comp = enhanced.get("composite_score")
    if comp is None:
        comp = data.get("composite_score") or data.get("composite", {}).get("composite_score", 0)
    verdict = (
        (enhanced.get("verdict") or data.get("composite", {}).get("verdict") or "Pending")
        .replace("_", " ")
        .title()
    )
    verdict_label = _verdict_presentation_label(
        enhanced.get("verdict") or data.get("composite", {}).get("verdict")
    )
    price = data.get("price")
    er = data.get("earnings_revision") or {}
    p_data = data.get("piotroski") or {}
    a_data = data.get("altman") or {}
    r_data = data.get("risk") or {}
    b_data = data.get("buffett") or {}
    fcf_data = data.get("fcf_quality") or {}
    growth_data = data.get("growth_quality") or {}
    capital_data = data.get("capital_allocation") or {}
    regime_data = data.get("regime") or {}
    bias_data = data.get("bias") or {}

    def _fmt_money(value, decimals=2):
        if value is None:
            return "N/A"
        return f"${value:,.{decimals}f}"

    def _fmt_pct(value, decimals=1):
        if value is None:
            return "N/A"
        return f"{value:.{decimals}f}%"

    def _fmt_number(value, decimals=1, suffix=""):
        if value is None:
            return "N/A"
        return f"{value:.{decimals}f}{suffix}"

    def _metric(label: str, value: str, hint: str | None = None) -> html.Div:
        children = [
            html.Div(label, className="analysis-mini-metric-label"),
            html.Div(value, className="analysis-mini-metric-value"),
        ]
        if hint:
            children.append(html.Div(hint, className="analysis-mini-metric-hint"))
        return html.Div(className="analysis-mini-metric", children=children)

    def _summary_point(title: str, copy: str) -> html.Div:
        return html.Div(
            className="analysis-summary-point",
            children=[
                html.Div(title, className="analysis-summary-point-title"),
                html.Div(copy, className="analysis-summary-point-copy"),
            ],
        )

    def _section_metric(label: str, value: str) -> html.Div:
        return html.Div(
            className="analysis-section-metric",
            children=[
                html.Div(label, className="analysis-section-metric-label"),
                html.Div(value, className="analysis-section-metric-value"),
            ],
        )

    def _section(
        section_id: str,
        title: str,
        summary: str,
        metrics: list[tuple[str, str]],
        children: list,
        *,
        open_by_default: bool = False,
    ) -> html.Section:
        summary_props = {}
        return html.Section(
            id=section_id,
            className="analysis-section",
            children=[
                html.Details(
                    id=f"{section_id}-disclosure",
                    className="analysis-disclosure",
                    open=open_by_default,
                    **{
                        "data-persist-disclosure": "true",
                        "data-disclosure-key": f"{symbol}:{section_id}",
                    },
                    children=[
                        html.Summary(
                            className="analysis-disclosure-summary",
                            **summary_props,
                            children=[
                                html.Div(
                                    className="analysis-disclosure-copy",
                                    children=[
                                        html.Div(title, className="analysis-disclosure-title"),
                                        html.Div(
                                            [
                                                html.Strong("Why this matters: "),
                                                summary,
                                            ],
                                            className="analysis-disclosure-text",
                                        ),
                                    ],
                                ),
                                html.Div(
                                    className="analysis-disclosure-metrics",
                                    children=[
                                        _section_metric(label, value) for label, value in metrics
                                    ],
                                ),
                                html.Div(
                                    className="analysis-disclosure-toggle",
                                    children=[
                                        html.Span(
                                            "Open", className="analysis-disclosure-toggle-open"
                                        ),
                                        html.Span(
                                            "Close", className="analysis-disclosure-toggle-close"
                                        ),
                                    ],
                                ),
                            ],
                        ),
                        html.Div(className="analysis-disclosure-body", children=children),
                        methodology_disclosure(
                            title,
                            summary=summary,
                            limitations=(
                                "Outputs depend on available reporting periods and model inputs; "
                                "missing observations may cause a model to be partial, skipped, or excluded."
                            ),
                        ),
                    ],
                )
            ],
        )

    intrinsic_value = b_data.get("intrinsic_value")
    value_gap = None
    if price and intrinsic_value:
        value_gap = ((intrinsic_value - price) / price) * 100

    if value_gap is not None and comp >= 75:
        lead_copy = "Cheap versus modeled moat value with a high-conviction composite setup."
    elif value_gap is not None and value_gap > 0:
        lead_copy = "Price sits below modeled value, but the full thesis still needs score support."
    elif comp >= 70:
        lead_copy = "Strong overall profile. Valuation is not screaming cheap, but the business quality stack is holding up."
    elif comp >= 50:
        lead_copy = "Mixed setup. Worth a quick review, but not an obvious yes on first pass."
    else:
        lead_copy = "Current setup is weak on a first-pass read. Keep it on the watchlist only if a specific thesis exists."

    positive_drivers, weak_drivers = analysis_score_drivers(data)
    strongest = positive_drivers[0] if positive_drivers else ("Not enough data", 0)
    weakest = weak_drivers[0] if weak_drivers else ("Not enough data", 0)
    warnings = critical_analysis_warnings(data)
    risk_copy = (
        warnings[0]
        if warnings
        else "No critical model warning is active; review the Risk section for fragility."
    )

    overview = html.Div(
        className="analysis-overview-shell",
        children=[
            data_trust_panel(data),
            html.Div(
                className="analysis-hero",
                children=[
                    html.Div(
                        className="analysis-hero-copy",
                        children=[
                            html.Div("Quick Research Snapshot", className="analysis-hero-kicker"),
                            html.Div(
                                className="analysis-hero-identity",
                                children=[
                                    company_logo(symbol, name, "company-logo company-logo--hero"),
                                    html.H2(
                                        link(
                                            f"{symbol} — {name}",
                                            href=f"/{symbol}",
                                            refresh=True,
                                            className="company-title-link",
                                            title=f"Open {name} company research",
                                        ),
                                        className="analysis-hero-title",
                                    ),
                                ],
                            ),
                            html.Div(
                                className="analysis-hero-meta",
                                children=[
                                    html.Span(
                                        f"Sector · {sector}", className="analysis-hero-meta-item"
                                    ),
                                    html.Span(
                                        f"Verdict · {verdict}", className="analysis-hero-meta-item"
                                    ),
                                    html.Span(
                                        f"Updated · {_fmt_updated(data.get('updated_at'))}",
                                        className="analysis-hero-meta-item",
                                    ),
                                ],
                            ),
                            html.Div(lead_copy, className="analysis-hero-lead"),
                        ],
                    ),
                    html.Div(
                        className=f"analysis-hero-score analysis-hero-score--{verdict_label}",
                        children=[
                            html.Div("Composite", className="analysis-hero-score-label"),
                            html.Div(f"{comp:.0f}", className="analysis-hero-score-value"),
                            html.Div(verdict, className="analysis-hero-score-note"),
                        ],
                    ),
                ],
            ),
            html.Div(
                className="analysis-mini-metrics",
                children=[
                    _metric("Price", _fmt_money(price)),
                    _metric("Moat Value", _fmt_money(intrinsic_value, 0 if intrinsic_value else 2)),
                    _metric("Margin", f"{value_gap:.1f}%" if value_gap is not None else "N/A"),
                    _metric("ROE", _fmt_pct(q.get("roe"))),
                    _metric("Op Margin", _fmt_pct(q.get("op_margin"))),
                    _metric(
                        "F-Score",
                        f"{p_data.get('f_score', 'N/A')}/9"
                        if p_data.get("f_score") is not None
                        else "N/A",
                    ),
                ],
            ),
            html.Div(
                className="analysis-decision-grid",
                children=[
                    _summary_point("Primary conclusion", lead_copy),
                    _summary_point(
                        "Strongest driver",
                        f"{strongest[0]} leads the factor set at {strongest[1]:.0f}/100.",
                    ),
                    _summary_point(
                        "Weakest factor",
                        f"{weakest[0]} is the weakest measured factor at {weakest[1]:.0f}/100.",
                    ),
                    _summary_point("Key risk", risk_copy),
                    _summary_point(
                        "Data freshness",
                        f"Model inputs updated {_fmt_updated(data.get('updated_at'))}.",
                    ),
                ],
            ),
            *[
                html.Div(
                    [
                        html.Strong("Critical warning: "),
                        html.Span(warning),
                    ],
                    className="analysis-critical-warning",
                    role="alert",
                )
                for warning in warnings
            ],
            html.Div(
                className="analysis-summary-points",
                children=[
                    _summary_point(
                        "Valuation",
                        f"P/E {_fmt_number(g.get('pe'), 1, 'x')}, P/B {_fmt_number(g.get('pb'), 2, 'x')}, moat grade {b_data.get('grade', 'N/A')}.",
                    ),
                    _summary_point(
                        "Financial strength",
                        f"F-Score {p_data.get('f_score', 'N/A')}/9 and Altman {a_data.get('zone_label', 'N/A')} set the accounting tone.",
                    ),
                    _summary_point(
                        "Risk",
                        f"Beta {_fmt_number(r_data.get('beta'), 2)} and Sharpe {_fmt_number(r_data.get('sharpe'), 2)} summarize current market behavior.",
                    ),
                    _summary_point(
                        "Growth",
                        f"Growth quality {growth_data.get('growth_quality_score', 'N/A')} and capital allocation {capital_data.get('capital_allocation_score', 'N/A')} lead the long-term read.",
                    ),
                ],
            ),
        ],
    )

    graham_card = _safe_analysis_component(
        "valuation",
        "Intrinsic value",
        _render_scorecard,
        "Intrinsic Value Analysis",
        g["criteria"],
        "graham",
    )
    quality_card = _safe_analysis_component(
        "moat-rating",
        "Moat rating",
        _render_scorecard,
        "Moat Rating Analysis",
        q["criteria"],
        "quality",
    )
    buffett_card = (
        _safe_analysis_component(
            "economic-moat",
            "Economic moat",
            _render_scorecard,
            "Economic Moat Quality & Value",
            b_data.get("criteria", []),
            "buffett",
        )
        if b_data.get("criteria")
        else html.Div()
    )
    momentum_card = (
        _safe_analysis_component(
            "momentum",
            "Momentum",
            _render_scorecard,
            "Momentum Analysis",
            m.get("criteria", []),
            "momentum",
        )
        if m.get("criteria")
        else html.Div()
    )
    piotroski_card = _safe_analysis_component("piotroski", "Piotroski", _piotroski_card, data)
    altman_card = _safe_analysis_component("altman", "Altman", _altman_card, data)
    fcf_quality_card = _safe_analysis_component(
        "fcf-quality", "Cash-flow quality", _fcf_quality_card, data
    )
    risk_card = _safe_analysis_component("risk", "Risk", _risk_card, data)
    market_fear_card = _safe_analysis_component(
        "risk", "Market conditions", _market_fear_card, data
    )
    regime_card = _safe_analysis_component("risk", "Market regime", _regime_card, data)
    comomentum_card = _safe_analysis_component("risk", "Co-momentum", _comomentum_card, data)
    capital_allocation_card = _safe_analysis_component(
        "capital-allocation", "Capital allocation", _capital_allocation_card, data
    )
    growth_quality_card = _safe_analysis_component(
        "growth-quality", "Growth quality", _growth_quality_card, data
    )
    factor_momentum_card = _safe_analysis_component(
        "factor-momentum", "Factor momentum", _factor_momentum_card, data
    )
    alternative_data_card = _safe_analysis_component(
        "alternative-data", "Alternative data", _alternative_data_card, data
    )
    insider_card = _safe_analysis_component(
        "insider-activity", "Insider activity", _insider_activity_card, data
    )
    greenblatt_card = _safe_analysis_component("greenblatt", "Greenblatt", _greenblatt_card, data)
    profitability_card = _safe_analysis_component(
        "profitability", "Profitability", _profitability_card, data
    )
    benchmark_bias_card = _safe_analysis_component(
        "benchmark-bias", "Benchmark bias", _benchmark_bias_card, data
    )
    graham_details = _safe_analysis_component(
        "intrinsic-details", "Intrinsic value details", _graham_details_card, g
    )
    buffett_details = _safe_analysis_component(
        "moat-details", "Moat details", _buffett_details_card, data
    )

    accounting_children = [
        html.Div(
            className="analysis-card-grid analysis-card-grid--two",
            children=[piotroski_card, altman_card],
        ),
        html.Div(
            className="analysis-card-grid analysis-card-grid--two",
            children=[
                fcf_quality_card,
                html.Div(
                    className="analysis-note-card",
                    children=[
                        html.Div("Fraud & Manipulation", className="analysis-note-card-title"),
                        html.Div(
                            "This section is reserved for the accounting stack: quality checks now, deeper fraud diagnostics as new models land.",
                            className="analysis-note-card-copy",
                        ),
                    ],
                ),
            ],
        ),
    ]

    sections = [
        ("analysis-overview", "Overview", overview),
        (
            "analysis-valuation",
            "Valuation",
            _section(
                "analysis-valuation",
                "Valuation",
                "Check whether the setup is actually cheap before spending more time on it.",
                [
                    ("Price", _fmt_money(price)),
                    ("Moat Value", _fmt_money(intrinsic_value, 0 if intrinsic_value else 2)),
                    ("P/E", _fmt_number(g.get("pe"), 1, "x")),
                    ("P/B", _fmt_number(g.get("pb"), 2, "x")),
                ],
                [
                    html.Div(
                        className="analysis-card-grid analysis-card-grid--two",
                        children=[graham_details, buffett_details],
                    ),
                    html.Div(
                        className="analysis-card-grid analysis-card-grid--three",
                        children=[graham_card, quality_card, buffett_card],
                    ),
                    greenblatt_card,
                ],
            ),
        ),
        (
            "analysis-accounting",
            "Financial strength",
            _section(
                "analysis-accounting",
                "Financial strength",
                "Keep accounting separate from the overview: cash quality, balance-sheet safety, and reporting quality live here.",
                [
                    (
                        "F-Score",
                        f"{p_data.get('f_score', 'N/A')}/9"
                        if p_data.get("f_score") is not None
                        else "N/A",
                    ),
                    (
                        "FCF",
                        f"{fcf_data.get('fcf_quality_score', 'N/A')}/100"
                        if fcf_data.get("fcf_quality_score") is not None
                        else "N/A",
                    ),
                    ("Altman", a_data.get("zone_label", "N/A")),
                    (
                        "Cash Conv.",
                        f"{fcf_data.get('fcf_conversion', 0):.1f}%"
                        if fcf_data.get("fcf_conversion") is not None
                        else "N/A",
                    ),
                ],
                accounting_children,
            ),
        ),
        (
            "analysis-risk",
            "Risk",
            _section(
                "analysis-risk",
                "Risk",
                "This section answers one question quickly: how fragile is the setup if you are wrong?",
                [
                    (
                        "Beta",
                        f"{r_data.get('beta', 0):.2f}" if r_data.get("beta") is not None else "N/A",
                    ),
                    (
                        "Sharpe",
                        f"{r_data.get('sharpe', 0):.2f}"
                        if r_data.get("sharpe") is not None
                        else "N/A",
                    ),
                    ("Bias", bias_data.get("bias", "N/A").replace("_", " ").title()),
                    ("Regime", regime_data.get("regime", "N/A").replace("_", " ")),
                ],
                [
                    risk_card,
                    html.Div(
                        className="analysis-card-grid analysis-card-grid--three",
                        children=[market_fear_card, regime_card, comomentum_card],
                    ),
                    benchmark_bias_card,
                ],
            ),
        ),
        (
            "analysis-growth",
            "Growth",
            _section(
                "analysis-growth",
                "Growth",
                "Long-term durability lives here: reinvestment, efficiency, and whether growth quality matches the story.",
                [
                    (
                        "Growth Q.",
                        f"{growth_data.get('growth_quality_score', 'N/A')}/100"
                        if growth_data.get("growth_quality_score") is not None
                        else "N/A",
                    ),
                    (
                        "Cap Alloc.",
                        f"{capital_data.get('capital_allocation_score', 'N/A')}/100"
                        if capital_data.get("capital_allocation_score") is not None
                        else "N/A",
                    ),
                    ("ROIC", _fmt_pct(capital_data.get("roic"))),
                    (
                        "Revisions",
                        f"{er.get('total_score', 'N/A')}/100"
                        if er.get("total_score") is not None
                        else "N/A",
                    ),
                ],
                [
                    html.Div(
                        className="analysis-card-grid analysis-card-grid--two",
                        children=[capital_allocation_card, growth_quality_card],
                    ),
                    html.Div(
                        className="analysis-card-grid analysis-card-grid--two",
                        children=[momentum_card, factor_momentum_card],
                    ),
                    profitability_card,
                ],
            ),
        ),
        (
            "analysis-signals",
            "Signals",
            _section(
                "analysis-signals",
                "Signals",
                "Use this only if the stock survives the first pass. It adds market behavior and edge signals without crowding the landing view.",
                [
                    (
                        "Earnings Rev.",
                        f"{er.get('total_score', 'N/A')}/100"
                        if er.get("total_score") is not None
                        else "N/A",
                    ),
                    ("Bias", (data.get("bias") or {}).get("bias", "N/A").replace("_", " ").title()),
                    (
                        "Insider",
                        f"{(data.get('insider_activity') or {}).get('insider_confidence_score', 'N/A')}/100"
                        if (data.get("insider_activity") or {}).get("insider_confidence_score")
                        is not None
                        else "N/A",
                    ),
                    (
                        "Alt Data",
                        f"{(data.get('alternative_data') or {}).get('alternative_data_score', 'N/A')}/100"
                        if (data.get("alternative_data") or {}).get("alternative_data_score")
                        is not None
                        else "N/A",
                    ),
                ],
                [
                    insider_card,
                    html.Div(
                        className="analysis-card-grid analysis-card-grid--two",
                        children=[alternative_data_card, _composite_banner(data)],
                    ),
                ],
            ),
        ),
    ]

    if data.get("price_history") or g.get("eps_history"):
        sections.append(
            (
                "analysis-charts",
                "Charts",
                _section(
                    "analysis-charts",
                    "Charts",
                    "Hidden by default so the page stays fast to scan. Open only when you want historical context.",
                    [
                        ("EPS", "History"),
                        ("Price", "History"),
                    ],
                    [
                        loading_container(
                            type="circle",
                            delay_show=250,
                            delay_hide=200,
                            show_initially=False,
                            children=html.Div(
                                [
                                    chart_skeleton(label="Historical charts are deferred"),
                                    html.P("Expand Charts to render historical figures."),
                                ],
                                id="analysis-charts-content",
                                className="analysis-charts-placeholder",
                                **{"aria-busy": "false", "data-adaptive-loading": "true"},
                            ),
                        ),
                    ],
                ),
            )
        )

    nav = html.Nav(
        className="analysis-jump-nav",
        **{"aria-label": "Analysis sections"},
        children=[
            html.Div(
                className="analysis-jump-track",
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
        ],
    )

    section_definitions = {
        definition.id: definition
        for definition in (
            SectionDefinition(
                "analysis-overview",
                "overview",
                0,
                "analysis",
                responsive_span=12,
                analytics_id="analysis_overview",
            ),
            SectionDefinition(
                "analysis-valuation",
                "disclosure",
                10,
                "graham",
                responsive_span=12,
                analytics_id="analysis_valuation",
            ),
            SectionDefinition(
                "analysis-accounting",
                "disclosure",
                20,
                "accounting",
                responsive_span=12,
                analytics_id="analysis_accounting",
            ),
            SectionDefinition(
                "analysis-risk",
                "disclosure",
                30,
                "risk",
                responsive_span=12,
                analytics_id="analysis_risk",
            ),
            SectionDefinition(
                "analysis-growth",
                "disclosure",
                40,
                "growth",
                responsive_span=12,
                analytics_id="analysis_growth",
            ),
            SectionDefinition(
                "analysis-signals",
                "disclosure",
                50,
                "signals",
                responsive_span=12,
                deferred=True,
                analytics_id="analysis_signals",
            ),
            SectionDefinition(
                "analysis-charts",
                "disclosure",
                60,
                "price_history",
                responsive_span=12,
                deferred=True,
                analytics_id="analysis_charts",
            ),
        )
    }
    rendered_sections = []
    for section_id, _title, content in sorted(
        sections, key=lambda item: section_definitions[item[0]].priority
    ):
        definition = section_definitions[section_id]
        if section_id == "analysis-overview":
            rendered_sections.append(
                html.Section(
                    id=section_id,
                    className=f"analysis-section analysis-section--overview ds-span-{definition.responsive_span}",
                    **{"data-analytics-id": definition.analytics_id},
                    children=[content],
                )
            )
        else:
            rendered_sections.append(
                html.Div(
                    content,
                    className=f"ds-analysis-section-slot ds-span-{definition.responsive_span}",
                    **{
                        "data-analytics-id": definition.analytics_id,
                        "data-deferred": str(definition.deferred).lower(),
                    },
                )
            )

    return [
        nav,
        container(
            analysis_grid(rendered_sections, className="analysis-sections"),
            size="wide",
            className="analysis-design-engine-reference",
            **{"data-design-system": "issue-075"},
        ),
    ]


def _build_analysis_content(data: dict | AnalysisResponse) -> list:
    """Render the analysis tab in the approved mockup order.

    The renderer is deliberately presentation-only: all scores and financial
    values come from the normalized analysis response. Optional values are
    displayed as ``N/A``. This renderer owns the complete analysis subtree,
    including hydrated charts and their empty states, so a second callback
    never updates a descendant while Dash is mounting this returned tree.

    Args:
        data: Legacy mapping or typed response returned by the analysis service.

    Returns:
        Dash components matching the mockup's toolbar, hero, metric, data,
        factor, and chart regions while retaining stable section callback IDs.
    """
    if isinstance(data, AnalysisResponse):
        data = data.presentation_data()
    if not data or "error" in data:
        return []

    data = chart_service.hydrate_analysis_history(data)

    symbol = str(data.get("symbol") or "").upper()
    name = str(data.get("name") or symbol)
    sector = str(data.get("sector") or "Not available")
    market_code = str(data.get("market_code") or "US").upper()
    price = data.get("price")
    graham = data.get("graham") or {}
    quality = data.get("quality") or {}
    momentum = data.get("momentum") or {}
    buffett = data.get("buffett") or {}
    piotroski = data.get("piotroski") or {}
    altman = data.get("altman") or {}
    risk = data.get("risk") or {}
    capital = data.get("capital_allocation") or {}
    growth = data.get("growth_quality") or {}
    enhanced = data.get("enhanced") or data.get("composite") or {}
    composite = enhanced.get("composite_score", data.get("composite_score"))
    verdict_code = enhanced.get("verdict", data.get("verdict")) or "PENDING"
    verdict = str(verdict_code).replace("_", " ").title()

    def number(value: object, decimals: int = 1, suffix: str = "") -> str:
        if value is None:
            return "N/A"
        try:
            return f"{float(value):,.{decimals}f}{suffix}"
        except (TypeError, ValueError):
            return "N/A"

    def money(value: object, decimals: int = 2) -> str:
        value_text = number(value, decimals)
        return "N/A" if value_text == "N/A" else f"${value_text}"

    def score(payload: dict, *keys: str) -> float | None:
        return _normalized_score(payload, *keys)

    def value_from(*payloads: dict, keys: tuple[str, ...]) -> object:
        for payload in payloads:
            for key in keys:
                if payload.get(key) is not None:
                    return payload[key]
        return None

    def status(value: object, positive: bool | None = None) -> str:
        if value is None:
            return "Not available"
        if positive is True:
            return "Strong"
        return str(value).replace("_", " ").title()

    def dl_card(title: str, rows: list[tuple[str, object, str | None]], note: str | None = None) -> html.Article:
        row_nodes = []
        for label, raw_value, tone in rows:
            text_value = str(raw_value) if isinstance(raw_value, str) else raw_value
            row_nodes.append(
                html.Div(
                    className="analysis-mockup-data-row",
                    children=[
                        html.Dt(label),
                        html.Dd(text_value if text_value is not None else "N/A", className=tone or ""),
                    ],
                )
            )
        children = [html.H2(title), html.Dl(row_nodes)]
        if note:
            children.append(html.Small(note))
        return html.Article(className="card analysis-mockup-data-card", children=children)

    intrinsic = value_from(buffett, graham, keys=("intrinsic_value", "graham_number"))
    gap = None
    if price is not None and intrinsic is not None:
        try:
            gap = (float(intrinsic) - float(price)) / float(price) * 100
        except (TypeError, ValueError, ZeroDivisionError):
            gap = None
    quality_score = score(quality, "total_score", "quality_score")
    momentum_score = score(momentum, "total_score", "momentum_score")
    composite_number = number(composite, 0)
    price_tone = "positive" if gap is not None and gap > 0 else "negative" if gap is not None else ""
    warnings = critical_analysis_warnings(data)
    positive_drivers, weak_drivers = analysis_score_drivers(data)
    strongest = positive_drivers[0] if positive_drivers else ("Not available", None)
    weakest = weak_drivers[0] if weak_drivers else ("Not available", None)
    risk_component_status = _safe_analysis_component("risk", "Risk", _risk_card, data)
    risk_cards = (
        list(risk_component_status.children)
        if getattr(risk_component_status, "className", "") == "risk-row"
        else [risk_component_status]
    )

    def metric(label: str, value: str, hint: str = "", tone: str = "") -> html.Article:
        return html.Article(
            className="card analysis-mockup-metric",
            children=[html.Span(label), html.Strong(value, className=tone), html.Small(hint)],
        )

    def factor_card(
        title: str,
        main_value: str,
        note: str,
        factor_score: float | None,
        weight: str,
        details: tuple[str, str, str],
    ) -> html.Div:
        return html.Div(
            className="analysis-mockup-factor-card",
            children=[
                html.Small(title),
                html.Strong(main_value),
                html.Span(note, className="positive" if factor_score is not None and factor_score >= 66 else ""),
                html.Ul([html.Li(item) for item in details]),
                html.Footer(f"Score {number(factor_score, 0) if factor_score is not None else 'N/A'}/100   Weight {weight}"),
            ],
        )

    toolbar = html.Div(
        className="analysis-mockup-toolbar",
        children=[
            html.Div(
                className="analysis-mockup-breadcrumbs",
                children=["Analyze ", html.Span("›"), f" {symbol} ", html.Span("›"), f" {name}"],
            ),
            html.Div(
                className="analysis-mockup-action-row",
                children=[
                    html.Button("☆ Watchlist", className="secondary-btn", type="button"),
                    html.Button("⇩ Download", className="secondary-btn", type="button"),
                    html.Button("•••", className="secondary-btn", type="button", **{"aria-label": "More analysis actions"}),
                ],
            ),
        ],
    )

    hero = html.Section(
        className="card analysis-mockup-hero",
        children=[
            html.Div(
                className="analysis-mockup-company-title",
                children=[
                    company_logo(symbol, name, "company-logo company-logo--hero"),
                    html.Div(
                        [
                            html.H1([name, html.Span(f"{symbol}  •  {market_code}")]),
                            html.P(f"{sector}  •  Financial analysis"),
                        ]
                    ),
                ],
            ),
            html.Div(
                className="analysis-mockup-price",
                children=[
                    html.Strong(money(price)),
                    html.Span("Price update available" if price is not None else "Price unavailable", className="positive" if price is not None else ""),
                    html.Small(_fmt_updated(data.get("updated_at") or data.get("generated_at"))),
                ],
            ),
            html.Div(
                className="analysis-mockup-score",
                children=[
                    html.Span("Overall Score  ⓘ"),
                    html.Strong([composite_number, html.Small("/100")]),
                    html.B(verdict, className="positive" if composite is not None and float(composite or 0) >= 66 else ""),
                ],
            ),
            html.Div(
                # Pass the signal components through the named children prop.
                # This keeps Dash's component serializer from treating the
                # list of component objects as an ordinary React value.
                children=_analysis_flags(data),
                className="analysis-mockup-hero-pills",
            ),
        ],
    )

    metric_strip = html.Section(
        className="analysis-mockup-metric-strip",
        children=[
            metric("Intrinsic Value", money(intrinsic), "Fair Value"),
            metric(
                "Upside / Downside vs Fair Value",
                f"{number(gap, 1, '%')}" if gap is not None else "N/A",
                "(fair value − price) ÷ price; not a return forecast",
                price_tone,
            ),
            metric("Quality Score", f"{number(quality_score, 0)} /100" if quality_score is not None else "N/A", "High Quality" if quality_score is not None and quality_score >= 66 else "Not available", "positive" if quality_score is not None and quality_score >= 66 else ""),
            metric("Piotroski F-Score", f"{piotroski.get('f_score')}/9" if piotroski.get("f_score") is not None else "N/A", "Strong" if piotroski.get("f_score") is not None and piotroski.get("f_score") >= 7 else "Not available"),
            metric("Dividend Yield", number(value_from(capital, graham, keys=("dividend_yield_implied", "dividend_yield")), 2, "%"), "Latest available"),
            metric("P/E (TTM)", number(graham.get("pe"), 1, "x"), "Latest available"),
            metric("EV / EBIT (TTM)", number(value_from(graham, buffett, keys=("ev_ebit", "ev_to_ebit")), 1, "x"), "Latest available"),
        ],
    )

    highlights = html.Section(
        className="card analysis-mockup-highlights",
        children=[
            html.Strong("Investment Highlights"),
            html.Span(
                (
                    f"Quality {quality_score:.0f}/100: ROE {number(quality.get('roe'), 1, '%')} "
                    f"and operating margin {number(quality.get('op_margin'), 1, '%')}."
                )
                if quality_score is not None
                else "Quality score is unavailable; review the detailed moat and quality criteria.",
                title="Quality score, ROE, and operating margin describe current business quality; they do not prove future durability.",
            ),
            html.Span(
                (
                    f"Cash flow quality {(data.get('fcf_quality') or {}).get('fcf_quality_score'):.0f}/100: "
                    "free-cash-flow conversion and stability support the earnings picture."
                )
                if (data.get("fcf_quality") or {}).get("fcf_quality_score") is not None
                else "Cash-flow quality is unavailable; no conclusion is drawn from missing data.",
            ),
            html.Span(
                (
                    f"Balance sheet: Altman Z {number(altman.get('z_score'), 2)} "
                    f"({altman.get('zone_label', 'zone unavailable')})."
                )
                if altman.get("z_score") is not None or altman.get("zone_label")
                else "Balance-sheet risk is unavailable; no safety conclusion is drawn.",
            ),
            html.Span(
                f"Composite {composite_number}/100: {verdict}. This is a model output, not a guarantee."
            ),
            html.Span(
                f"Strongest measured factor: {strongest[0]} ({number(strongest[1], 0)}/100)."
            ),
            html.Span(f"Weakest measured factor: {weakest[0]} ({number(weakest[1], 0)}/100)."),
        ],
    )

    valuation = dl_card(
        "Valuation Summary",
        [("Fair Value (Intrinsic)", money(intrinsic), ""), ("Current Price", money(price), ""), ("Margin of Safety", f"{number(gap, 1, '%')}" if gap is not None else "N/A", price_tone), ("Value Score", f"{composite_number} /100", "positive" if composite is not None and float(composite or 0) >= 66 else "")],
    )
    health = dl_card(
        "Financial Health",
        [("Overall Health", status(altman.get("zone_label")), ""), ("Current Ratio", number(value_from(piotroski, graham, keys=("current_ratio",)), 2, "x"), ""), ("Quick Ratio", number(graham.get("quick_ratio"), 2, "x"), ""), ("Debt / Equity", number(graham.get("debt_to_equity"), 2, "x"), ""), ("Altman Z-Score", number(altman.get("z_score"), 2), "")],
        "Accounting model status remains visible when a field is unavailable.",
    )
    profitability = dl_card(
        "Profitability / Quality",
        [("ROIC (TTM)", number(value_from(capital, quality, keys=("roic",)), 1, "%"), ""), ("ROE (TTM)", number(quality.get("roe"), 2, "%"), ""), ("Gross Margin", number(piotroski.get("gross_margin"), 1, "%"), ""), ("Operating Margin", number(quality.get("op_margin"), 1, "%"), ""), ("Net Margin", number(buffett.get("net_margin"), 1, "%"), ""), ("Revenue Quality", status(growth.get("signal")), "")],
    )
    risk_card = dl_card(
        "Risk & Volatility",
        [("Beta (5Y)", number(risk.get("beta"), 2), ""), ("Max Drawdown", number(risk.get("max_drawdown"), 1, "%"), "negative"), ("Sharpe Ratio", number(risk.get("sharpe"), 2), ""), ("Price Volatility", number(risk.get("volatility_annual"), 1, "%"), ""), ("Value at Risk (95%)", number(risk.get("var_95"), 1, "%"), "negative")],
    )

    data_grid = html.Section(className="analysis-mockup-data-grid", children=[valuation, health, profitability, risk_card])
    sentiment = html.Article(
        className="card analysis-mockup-sentiment",
        children=[
            html.Div(className="analysis-mockup-card-header", children=[html.H2("Market Sentiment"), html.Strong(status((data.get("bias") or {}).get("bias"))) ]),
            html.Div(className="analysis-mockup-sentiment-meter", **{"aria-label": "Market sentiment meter"}),
            html.Div(className="analysis-mockup-sentiment-labels", children=[html.Small("Bullish"), html.Small("Neutral"), html.Small("Bearish")]),
            html.Dl([html.Div([html.Dt("Market Cap"), html.Dd(_fmt_market_cap(data.get("market_cap") or graham.get("market_cap")))]), html.Div([html.Dt("Risk Regime"), html.Dd(status((data.get("regime") or {}).get("regime")))])]),
        ],
    )
    factor_breakdown = html.Article(
        className="card analysis-mockup-factor-breakdown",
        children=[
            html.H2("Factor Model Breakdown"),
            html.Div(className="analysis-mockup-factor-grid", children=[
                factor_card("Z-Score Model", f"Z = {number(altman.get('z_score'), 2)}", status(altman.get("zone_label")), score(altman, "risk_score", "altman_score"), "20%", ("Low bankruptcy risk", "Liquidity and solvency context", "Review reporting period")),
                factor_card("Piotroski F-Score", f"{piotroski.get('f_score')}/9" if piotroski.get("f_score") is not None else "N/A", "Strong" if piotroski.get("f_score") is not None and piotroski.get("f_score") >= 7 else "Not available", ((float(piotroski.get("f_score")) / 9) * 100) if piotroski.get("f_score") is not None else None, "15%", ("Profitability and efficiency", "Balance-sheet trend", "Operating trend")),
                factor_card("ROIC Quality Model", number(value_from(capital, quality, keys=("roic",)), 1, "%"), "Quality", quality_score, "20%", ("Returns on capital", "Durability signal", "Compare with cost of capital")),
                factor_card("Value Model (Intrinsic)", money(intrinsic), "Fair value", score(graham, "total_score", "graham_score"), "25%", ("Latest model estimate", "Price-to-value context", "Review assumptions")),
                factor_card("Momentum Model", f"{number(momentum_score, 0)}/100" if momentum_score is not None else "N/A", "Momentum", momentum_score, "10%", ("Price trend", "Relative performance", "Historical signal")),
                factor_card("Sentiment Model", status((data.get("bias") or {}).get("bias")), "Market context", score(data.get("bias") or {}, "confidence", "sentiment_score"), "10%", ("Reported market tone", "Short-term context", "Not a standalone signal")),
            ]),
        ],
    )
    middle_grid = html.Section(className="analysis-mockup-middle-grid", children=[sentiment, factor_breakdown])

    # Keep the mockup hierarchy, but expose the complete research record below
    # the scan-friendly summary. These existing authoritative card renderers
    # only compose presentation; they do not alter financial calculations.
    momentum_card = _render_scorecard("Momentum Analysis", momentum.get("criteria", []), "momentum")
    factor_momentum_card = _factor_momentum_card(data)
    insider_card = _insider_activity_card(data)
    alternative_data_card = _alternative_data_card(data)
    profitability_card = _profitability_card(data)
    detailed_analysis = html.Section(
        className="analysis-mockup-factor-breakdown",
        children=[
            html.H2("Full Analysis Detail"),
            html.P(
                "The visual summary above is a quick read. The complete model detail remains available below.",
                className="analysis-copy-leading fs-12 clr-muted",
            ),
            html.Div(
                className="analysis-card-grid analysis-card-grid--two",
                children=[_graham_details_card(graham), _buffett_details_card(data)],
            ),
            html.Div(
                className="analysis-card-grid analysis-card-grid--two",
                children=[
                    _render_scorecard("Intrinsic Value Analysis", graham.get("criteria", []), "graham"),
                    _render_scorecard("Moat Rating Analysis", quality.get("criteria", []), "quality"),
                ],
            ),
            html.Div(
                className="analysis-card-grid analysis-card-grid--two",
                children=[
                    _render_scorecard(
                        "Economic Moat Quality & Value", buffett.get("criteria", []), "buffett"
                    ),
                    _greenblatt_card(data),
                ],
            ),
            html.Div(
                className="analysis-card-grid analysis-card-grid--two",
                children=[_piotroski_card(data), _altman_card(data)],
            ),
            html.Div(
                className="analysis-card-grid analysis-card-grid--two",
                children=[_fcf_quality_card(data), *risk_cards],
            ),
            html.Div(
                className="analysis-card-grid analysis-card-grid--two",
                children=[_regime_card(data), _comomentum_card(data)],
            ),
            html.Div(
                className="analysis-card-grid analysis-card-grid--two",
                children=[_benchmark_bias_card(data), profitability_card],
            ),
            html.Div(
                className="analysis-card-grid analysis-card-grid--two",
                children=[_capital_allocation_card(data), _growth_quality_card(data)],
            ),
            html.Div(
                className="analysis-card-grid analysis-card-grid--two",
                children=[momentum_card, factor_momentum_card],
            ),
            html.Div(
                className="analysis-card-grid analysis-card-grid--two",
                children=[insider_card, alternative_data_card],
            ),
            _composite_banner(data),
        ],
    )

    chart_placeholder = html.Div(
        className="analysis-mockup-chart-placeholder-card",
        children=[html.H3("Price vs. Intrinsic Value"), html.Div("Historical price and modeled value load on request.")],
    )
    chart_history_placeholder = html.Div(
        className="analysis-mockup-chart-placeholder-card",
        children=[html.H3("Factor Score History"), html.Div("Historical factor scores load on request.")],
    )
    dividend_placeholder = html.Div(
        className="analysis-mockup-chart-placeholder-card",
        children=[html.H3("Dividend History"), html.Div("Dividend observations load on request.")],
    )
    chart_content = [chart_placeholder, chart_history_placeholder, dividend_placeholder]
    if data.get("price_history") or (graham.get("eps_history") or []):
        try:
            # The full server response still contains history, so render it
            # immediately when available; the callback remains the retry path
            # for deferred or failed chart requests.
            chart_content = build_analysis_charts(data)
        except Exception as error:
            chart_content = [
                section_error(
                    "Historical charts are temporarily unavailable. The rest of the analysis remains usable.",
                    technical_id=type(error).__name__,
                )
            ]
    chart_grid = html.Section(
        className="analysis-mockup-chart-grid",
        children=[
            html.Div(className="analysis-mockup-chart-toolbar", children=[html.Div([html.H2("Historical Charts"), html.P("Price, earnings, and dividend context from the latest analysis")])]),
            # Keep the callback target's children as one Dash component.  A
            # direct list of serialized dcc.Graph objects can be handed to
            # React as plain objects during a partial callback update.
            html.Div(
                id="analysis-charts-content",
                className="analysis-mockup-chart-results",
                children=html.Div(
                    chart_content,
                    className="analysis-chart-results-stack",
                ),
            ),
        ],
    )

    compatibility = html.Div(
        className="sr-only",
        children=[
            html.Span("Quick Research Snapshot"),
            html.Span(f" P/E {number(graham.get('pe'), 1, 'x')}"),
            html.Span(f" P/B {number(graham.get('pb'), 2, 'x')}"),
            html.Span(f" Beta {number(risk.get('beta'), 2)}"),
            html.Span(f" Sharpe {number(risk.get('sharpe'), 2)}"),
            html.Div(risk_component_status),
            html.Span(f"Primary conclusion: {verdict}."),
            html.Span(f" Strongest driver: {strongest[0]} leads the factor set at {number(strongest[1], 0)}/100."),
            html.Span(f" Weakest factor: {weakest[0]} is the weakest measured factor at {number(weakest[1], 0)}/100."),
            html.Span(f" Key risk: {warnings[0] if warnings else 'No critical model warning is active.'}"),
            html.Span(f" Data freshness: Model inputs updated {_fmt_updated(data.get('updated_at') or data.get('generated_at'))}."),
        ],
    )
    visible_warning = [html.Div([html.Strong("Critical warning: "), html.Span(warning)], className="analysis-mockup-warning", role="alert") for warning in warnings]

    sections = [
        html.Section(
            id="analysis-overview",
            className="analysis-section analysis-section--overview",
            children=[
                toolbar,
                hero,
                metric_strip,
                highlights,
                *visible_warning,
                data_grid,
                middle_grid,
                detailed_analysis,
                chart_grid,
                compatibility,
            ],
            **{"data-disclosure-key": f"{symbol}:analysis-overview", "data-persist-disclosure": "true"},
        ),
        html.Div(id="analysis-valuation", className="analysis-mockup-compatibility-anchor", **{"data-disclosure-key": f"{symbol}:analysis-valuation", "data-persist-disclosure": "true"}),
        html.Div(id="analysis-accounting", className="analysis-mockup-compatibility-anchor"),
        html.Div(id="analysis-risk", className="analysis-mockup-compatibility-anchor"),
        html.Div(id="analysis-growth", className="analysis-mockup-compatibility-anchor"),
        html.Div(id="analysis-signals", className="analysis-mockup-compatibility-anchor"),
        html.Div(id="analysis-charts", className="analysis-mockup-compatibility-anchor"),
    ]
    return [
        html.Div(
            sections,
            className="analysis-design-engine-reference",
            **{"data-design-system": "issue-075"},
        )
    ]


def build_analysis_charts(data: dict) -> list:
    """Build the complete responsive chart layout for one analysis.

    The first row compares earnings and normalized price history. The second
    row pairs dividend history with persisted composite-score history so both
    long-term shareholder views have equal visual weight on desktop. Existing
    shared grid behavior stacks each pair when the viewport becomes compact.

    Args:
        data: Normalized analysis response containing the ticker and optional
            price, benchmark, earnings, and dividend histories.

    Returns:
        A list containing two responsive two-card rows. Any unavailable series
        remains represented by its chart-specific accessible empty state.

    Side Effects:
        Reads composite-score history through the chart service. It does not
        mutate analysis data or recalculate any financial score.
    """
    symbol = data.get("symbol") or "Stock"
    graham = data.get("graham") or {}
    return [
        html.Div(
            className="analysis-card-grid analysis-card-grid--two",
            children=[
                _eps_chart(graham.get("eps_history", []), symbol, data),
                _price_chart(data.get("price_history"), data.get("spy_history"), symbol, data),
            ],
        ),
        html.Div(
            className=(
                "analysis-card-grid analysis-card-grid--two "
                "analysis-chart-history-pair"
            ),
            children=[
                _div_chart(graham.get("div_history", []), symbol, data),
                _score_history_chart(symbol),
            ],
        ),
    ]


def _score_history_chart(symbol: str) -> html.Div:
    """Render persisted composite-score history or its accessible empty state.

    Args:
        symbol: Uppercase ticker used to retrieve and label score snapshots.

    Returns:
        A responsive line chart when at least two observations exist;
        otherwise a styled empty-state card. Scores remain on a 0–100 scale.

    Side Effects:
        Reads persisted score snapshots through the chart service.
    """
    dataset = chart_service.get_composite_trend_dataset(symbol, limit=365)
    series = (dataset.get("series") or [{}])[0]
    if len(series.get("x") or []) < 2:
        return html.Div(
            className="empty-card analysis-empty-history-card",
            children=[
                html.Div("Composite Score History", className="empty-card-title"),
                html.Div("Not enough score observations", className="empty-title"),
                html.Div("Score history appears after multiple completed analyses.", className="empty-msg"),
            ],
        )
    figure = go.Figure(
        go.Scatter(
            x=series["x"],
            y=series["y"],
            mode="lines+markers",
            line={"color": BLUE, "width": 2.5},
            marker={"color": BLUE, "size": 6},
            hovertemplate="%{x}<br>Composite score %{y:.1f}/100<extra></extra>",
        )
    )
    figure.update_layout(**_chart_layout(f"{symbol} Composite Score History"), height=420)
    figure.update_yaxes(range=[0, 100], title_text="Score")
    return dcc.Graph(
        figure=figure,
        config={"displayModeBar": False, "responsive": True, "staticPlot": True},
        className="analysis-history-graph analysis-score-history-graph",
    )
def format_currency(val) -> str:
    if val is None:
        return "N/A"
    elif val >= 1e9:
        return f"${val / 1e9:.2f}B"
    elif val >= 1e6:
        return f"${val / 1e6:.2f}M"
    elif val >= 1e3:
        return f"${val / 1e3:.2f}K"
    else:
        return f"${val:.2f}"


def _fmt_market_cap(v) -> str:
    if v is None:
        return "—"
    # v is stored in $M
    if v >= 1e6:
        return f"${v / 1e6:.2f}T"
    if v >= 1e3:
        return f"${v / 1e3:.2f}B"
    return f"${v:,.0f}M"


def _fmt_updated(v) -> str:
    if not v:
        return "Not available"
    try:
        if hasattr(v, "strftime"):
            return v.strftime("%b %d, %Y")
        raw = str(v).strip()
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        return parsed.strftime("%b %d, %Y")
    except (TypeError, ValueError, OverflowError):
        return str(v)[:10] or "Not available"


def _render_scorecard(title: str, criteria: list, card_type: str) -> html.Div:
    rows = []
    for c in criteria:
        score = c["score"]
        max_s = c["max"]
        pct = score / max_s * 100 if max_s else 0
        color = GREEN if pct >= 66 else AMBER if pct >= 33 else RED
        rows.append(
            html.Div(
                className="criterion-row",
                children=[
                    html.Div(
                        className="criterion-left",
                        children=[
                            html.Div(c["label"], className="criterion-label"),
                            html.Div(c.get("note", ""), className="criterion-note"),
                            html.Div(
                                className="score-bar",
                                children=[
                                    html.Progress(
                                        value=str(pct),
                                        max="100",
                                        className=f"score-bar-fill {tone_class(color)}",
                                    )
                                ],
                            ),
                        ],
                    ),
                    html.Div(f"{score}/{max_s}", className=f"criterion-pts {tone_class(color)}"),
                ],
            )
        )
    return html.Div(
        className="scorecard",
        children=[
            html.Div(title, className="scorecard-header"),
            html.Div(rows),
            methodology_disclosure(
                title,
                summary=(
                    "The displayed score is the sum of the documented criteria shown above; "
                    "criteria use the latest available normalized inputs."
                ),
                limitations=(
                    f"{card_type.replace('_', ' ').title()} results are estimates, can be partial when inputs are missing, "
                    "and should be interpreted with the reporting period and provenance panel."
                ),
            ),
        ],
    )


def _eps_chart(eps_history: list, symbol: str, data: dict | None = None) -> html.Div:
    """Render reported EPS history or a styled unavailable-data state.

    Args:
        eps_history: Ordered historical EPS observations used when ``data`` is
            not supplied.
        symbol: Uppercase ticker used in chart labels and cache keys.
        data: Optional complete analysis payload, including freshness metadata.

    Returns:
        A responsive Dash graph when observations exist; otherwise an
        accessible empty-state card. The function has no external side effects
        beyond reading the chart dataset cache.
    """
    dataset = chart_service.get_analysis_chart_dataset(
        data or {"symbol": symbol, "graham": {"eps_history": eps_history}}, "eps_history"
    )
    series = (dataset.get("series") or [{}])[0]
    if not series.get("x"):
        return html.Div(
            className="empty-card",
            children=[
                html.Div("EPS History", className="empty-card-title"),
                html.Div("No EPS data", className="empty-title"),
                html.Div("Insufficient data available", className="empty-msg"),
            ],
        )
    y_values = series.get("y") or []
    colors = [GREEN if (v or 0) >= 0 else RED for v in y_values]
    fig = go.Figure(
        go.Bar(
            x=series.get("x"),
            y=y_values,
            marker_color=colors,
            text=[format_currency(v) for v in y_values],
            textposition="outside",
            textfont=dict(size=12, color=WHITE),
        )
    )
    max_value = max((abs(float(value)) for value in y_values if value is not None), default=1.0)
    layout = _chart_layout(dataset.get("title") or f"{symbol} EPS History (10yr)")
    # Merge overrides before expanding keyword arguments. ``_chart_layout``
    # already owns a margin key, and passing a second margin keyword raises
    # before Plotly can construct the chart.
    layout.update(
        margin={"l": 52, "r": 32, "t": 76, "b": 64},
        uniformtext={"minsize": 9, "mode": "hide"},
    )
    fig.update_layout(**layout)
    fig.update_yaxes(range=[min(0, -max_value * 0.12), max_value * 1.2], automargin=True)
    for trace in fig.data:
        trace.cliponaxis = False
    return dcc.Graph(
        figure=fig,
        config={"displayModeBar": False, "responsive": True, "staticPlot": True},
        className="analysis-history-graph",
    )


def _price_chart(
    price_history_dict, spy_history_dict, symbol: str, data: dict | None = None
) -> html.Div:
    dataset = chart_service.get_analysis_chart_dataset(
        data
        or {"symbol": symbol, "price_history": price_history_dict, "spy_history": spy_history_dict},
        "price_history",
    )
    series = dataset.get("series") or []
    if not series:
        return html.Div(
            className="empty-card analysis-empty-history-card",
            children=[
                html.Div("Price History", className="empty-card-title"),
                html.Div("No price data", className="empty-title"),
                html.Div("Insufficient history available", className="empty-msg"),
            ],
        )
    fig = go.Figure()
    for item in series:
        is_spy = item.get("name") == "SPY"
        fig.add_trace(
            go.Scatter(
                x=item.get("x"),
                y=item.get("y"),
                name=item.get("name") or symbol,
                line=dict(
                    color=MUTED if is_spy else BLUE,
                    width=1.5 if is_spy else 2,
                    dash="dot" if is_spy else None,
                ),
            )
        )
    fig.update_layout(**_chart_layout(dataset.get("title") or f"{symbol} vs SPY (10yr normalised)"))
    fig.update_yaxes(title_text="Index (100 = start)")
    return dcc.Graph(
        figure=fig,
        config={"displayModeBar": False, "responsive": True, "staticPlot": True},
        className="analysis-history-graph",
    )


def _div_chart(div_history: list, symbol: str, data: dict | None = None) -> html.Div:
    """Render dividend-payment history or a styled no-dividend state.

    Args:
        div_history: Ordered dividend observations used when ``data`` is not
            supplied.
        symbol: Uppercase ticker used in chart cache keys.
        data: Optional complete analysis payload, including currency metadata.

    Returns:
        A responsive Dash bar chart when payments exist; otherwise an
        accessible empty-state card. Values retain the normalized units
        supplied by the chart service.
    """
    dataset = chart_service.get_analysis_chart_dataset(
        data or {"symbol": symbol, "graham": {"div_history": div_history}}, "dividend_history"
    )
    series = (dataset.get("series") or [{}])[0]
    if not series.get("x"):
        return html.Div(
            className="empty-card analysis-empty-history-card",
            children=[
                html.Div("Dividend History", className="empty-card-title"),
                html.Div("No dividend history", className="empty-title"),
                html.Div("No reported dividend payments are available for this company.", className="empty-msg"),
            ],
        )
    fig = go.Figure(
        go.Bar(
            x=series.get("x"),
            y=series.get("y"),
            marker_color=BLUE,
            text=[format_currency(v) for v in series.get("raw_y", [])],
            textposition="outside",
            textfont=dict(size=20, color=WHITE),
        )
    )
    max_value = max((abs(float(value)) for value in series.get("y", []) if value is not None), default=1.0)
    layout = _chart_layout("")
    layout.update(
        height=420,
        margin={"l": 56, "r": 32, "t": 28, "b": 64},
        uniformtext={"minsize": 9, "mode": "hide"},
    )
    fig.update_layout(**layout)
    fig.update_yaxes(range=[0, max_value * 1.2], automargin=True)
    for trace in fig.data:
        trace.cliponaxis = False
    return dcc.Graph(
        figure=fig,
        config={"displayModeBar": False, "responsive": True, "staticPlot": True},
        className="analysis-history-graph analysis-dividend-graph",
    )


def _graham_details_card(g_data: dict) -> html.Div:
    gn = g_data.get("graham_number")
    price = g_data.get("price")
    mos = g_data.get("margin_of_safety")
    rows = [
        ("Fair Value", f"${gn:.2f}" if gn else "N/A"),
        ("Margin of Safety", f"{mos:.1f}%" if mos else "N/A"),
        ("Current Price", f"${price:.2f}" if price else "N/A"),
        ("EPS", f"${g_data.get('eps', 0):.2f}" if g_data.get("eps") else "N/A"),
        ("Book Value/Share", f"${g_data.get('bvps', 0):.2f}" if g_data.get("bvps") else "N/A"),
        ("Div Years", str(g_data.get("div_years", 0))),
        ("EPS Years", str(g_data.get("eps_years", 0))),
    ]
    gn_color = GREEN if mos and mos > 0 else RED
    def _row_color(label):
        if label == "Margin of Safety":
            return gn_color
        return TEXT

    detail_rows = [
        html.Div(
            className="detail-row",
            children=[
                html.Span(label, className="detail-label"),
                html.Span(value, className=f"detail-value {tone_class(_row_color(label))}"),
            ],
        )
        for label, value in rows
    ]
    return html.Div(
        className="scorecard",
        children=[
            html.Div(
                className="card-header",
                children=[
                    html.Span("Intrinsic Value Estimate"),
                ],
            ),
            *detail_rows,
        ],
    )


def _buffett_details_card(data: dict) -> html.Div:
    b = data.get("buffett") or {}
    iv = b.get("intrinsic_value")
    mos = b.get("margin_of_safety")
    grade = b.get("grade", "N/A")
    glabel = b.get("grade_label", "")
    rows = [
        ("Grade", f"{grade} — {glabel}" if glabel else str(grade)),
        ("Intrinsic Value", f"${iv:.2f} ({b.get('iv_base', '')})" if iv else "N/A"),
        ("Margin of Safety", f"{mos:.1f}%" if mos is not None else "N/A"),
        ("ROE (latest)", f"{b.get('roe_latest', 0):.1f}%" if b.get("roe_latest") else "N/A"),
        ("ROE ≥15% years", f"{b.get('n_roe_above15', 0)}/{b.get('n_roe_years', 0)}"),
        ("Net Margin", f"{b.get('net_margin', 0):.1f}%" if b.get("net_margin") else "N/A"),
        ("EPS CAGR", f"{b.get('eps_cagr', 0):.1f}%/yr" if b.get("eps_cagr") is not None else "N/A"),
        ("FCF", f"${b.get('fcf_latest', 0):.1f}B" if b.get("fcf_latest") is not None else "N/A"),
        ("ROIC", f"{b.get('roic', 0):.1f}%" if b.get("roic") else "N/A"),
        (
            "Debt Payback",
            f"{b.get('de_years', 0):.1f}yr" if b.get("de_years") is not None else "N/A",
        ),
    ]
    iv_color = GREEN if mos and mos > 0 else RED
    detail_rows = [
        html.Div(
            className="detail-row",
            children=[
                html.Span(label, className="detail-label"),
                html.Span(
                    value,
                    className=f"detail-value {tone_class(iv_color if label == 'Margin of Safety' else TEXT)}",
                ),
            ],
        )
        for label, value in rows
    ]
    return html.Div(
        className="scorecard",
        children=[
            html.Div(
                className="card-header",
                children=[
                    html.Span("Economic Moat Rating"),
                ],
            ),
            html.Div(detail_rows),
        ],
    )


def _chart_layout(title: str, many_traces: bool = False) -> dict:
    """
    many_traces=True: horizontal legend above the plot. This preserves chart
    width on narrow screens while keeping portfolio trace labels visible.
    """
    if many_traces:
        legend = dict(
            bgcolor="rgba(0,0,0,0)",
            font=dict(size=11),
            orientation="h",
            x=0,
            y=-0.2,
            xanchor="left",
            yanchor="top",
        )
        margin = dict(l=52, r=16, t=58, b=112)
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
