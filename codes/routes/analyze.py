from __future__ import annotations

import html
import json
import re

import flask

from codes.services.analysis_snapshot_service import (
    get_snapshot,
    list_related_snapshots,
    list_ticker_snapshots,
)


analyze_pages = flask.Blueprint("analysis_pages", __name__)
_TICKER_RE = re.compile(r"^[A-Z]{1,6}(\.[A-Z])?$")
_DATE_RE = re.compile(r"^\d{8}$")


def _fmt(value, suffix: str = "") -> str:
    if value is None:
        return "N/A"
    return f"{value:.2f}{suffix}"


def _fmt_delta(value, suffix: str = "") -> str:
    if value is None:
        return "N/A"
    sign = "+" if value > 0 else ""
    return f"{sign}{value:.2f}{suffix}"


def _delta(current, previous) -> float | None:
    if current is None or previous is None:
        return None
    return float(current) - float(previous)


def _delta_class(value) -> str:
    if value is None or abs(value) < 0.005:
        return "flat"
    return "up" if value > 0 else "down"


def _metric_card(label: str, current, previous, suffix: str = "") -> str:
    change = _delta(current, previous)
    klass = _delta_class(change)
    return (
        '<div class="metric compare-metric">'
        f'<div class="label">{html.escape(label)}</div>'
        f'<div class="value">{html.escape(_fmt(current, suffix))}</div>'
        f'<div class="compare-prev">Was {html.escape(_fmt(previous, suffix))}</div>'
        f'<div class="delta {klass}">{html.escape(_fmt_delta(change, suffix))}</div>'
        "</div>"
    )


def _history_picker(snapshot, history, compare_date: str | None) -> str:
    options = []
    for item in history:
        if item.url_date == snapshot.url_date:
            continue
        selected = " selected" if item.url_date == compare_date else ""
        label = f"{item.analysis_date.isoformat()} - {item.final_rating}"
        options.append(
            f'<option value="{html.escape(item.url_date)}"{selected}>'
            f"{html.escape(label)}</option>"
        )

    if not options:
        return (
            '<section class="panel">'
            "<h2>Analysis History</h2>"
            '<p class="muted">No earlier public snapshots are available for this ticker yet.</p>'
            "</section>"
        )

    return (
        f'<form class="panel compare-form" action="{html.escape(snapshot.public_path)}" method="get">'
        "<h2>Compare Previous Analysis</h2>"
        '<label for="compare">Historical snapshot</label>'
        '<div class="form-row">'
        '<select id="compare" name="compare">'
        + "".join(options)
        + "</select>"
        '<button type="submit">Compare</button>'
        "</div>"
        "</form>"
    )


def _history_links(snapshot, history) -> str:
    rows = []
    for item in history:
        active = " current" if item.url_date == snapshot.url_date else ""
        current_attr = ' aria-current="page"' if item.url_date == snapshot.url_date else ""
        if item.url_date == snapshot.url_date:
            action = "Current"
            action_html = f'<span class="history-action">{html.escape(action)}</span>'
        else:
            action = "Compare"
            compare_href = f"{snapshot.public_path}?compare={item.url_date}"
            action_html = (
                f'<a class="history-action" href="{html.escape(compare_href)}">'
                f"{html.escape(action)}</a>"
            )
        rows.append(
            f'<div class="history-row{active}">'
            f'<a class="history-date" href="{html.escape(item.public_path)}"{current_attr}>'
            f"{html.escape(item.analysis_date.isoformat())}</a>"
            f"<strong>{html.escape(item.final_rating)}</strong>"
            f"{action_html}"
            "</div>"
        )
    return (
        '<section class="panel">'
        "<h2>Analysis History</h2>"
        '<div class="history-list">'
        + "".join(rows)
        + "</div>"
        "</section>"
    )


def _comparison_section(snapshot, comparison) -> str:
    if comparison is None:
        return ""

    rating_changed = snapshot.final_rating != comparison.final_rating
    rating_class = "up" if rating_changed else "flat"
    rating_delta = (
        f"{comparison.final_rating} to {snapshot.final_rating}"
        if rating_changed
        else "No change"
    )
    cards = [
        _metric_card("Valuation Score", snapshot.valuation_score, comparison.valuation_score, "/100"),
        _metric_card("Quality Score", snapshot.quality_score, comparison.quality_score, "/100"),
        _metric_card("Growth Score", snapshot.growth_score, comparison.growth_score, "/100"),
        _metric_card("Momentum Score", snapshot.momentum_score, comparison.momentum_score, "/100"),
        _metric_card("Risk Score", snapshot.risk_score, comparison.risk_score, "/100"),
        _metric_card("Intrinsic Value", snapshot.intrinsic_value, comparison.intrinsic_value),
        _metric_card("Market Price", snapshot.market_price, comparison.market_price),
        _metric_card("Market Fear Score", snapshot.market_fear_score, comparison.market_fear_score, "/100"),
    ]
    return (
        '<section class="panel">'
        "<h2>Historical Comparison</h2>"
        f'<p class="muted">Comparing {html.escape(snapshot.analysis_date.isoformat())} '
        f"against {html.escape(comparison.analysis_date.isoformat())}.</p>"
        '<div class="metric compare-metric rating-change">'
        '<div class="label">Rating Change</div>'
        f'<div class="value">{html.escape(snapshot.final_rating)}</div>'
        f'<div class="compare-prev">Was {html.escape(comparison.final_rating)}</div>'
        f'<div class="delta {rating_class}">{html.escape(rating_delta)}</div>'
        "</div>"
        '<div class="grid compare-grid">'
        + "".join(cards)
        + "</div>"
        "</section>"
    )


def _related_link_list(items, *, include_sector: bool = False) -> str:
    rows = []
    for item in items:
        detail = item.final_rating
        if include_sector and item.sector:
            detail = f"{item.sector} · {detail}"
        rows.append(
            '<li class="related-item">'
            f'<a href="{html.escape(item.public_path)}">'
            f"{html.escape(item.company_name)} ({html.escape(item.ticker)})"
            "</a>"
            f'<span>{html.escape(detail)}</span>'
            "</li>"
        )
    return '<ul class="related-list">' + "".join(rows) + "</ul>"


def _related_links_section(snapshot, related: dict[str, list]) -> str:
    panels = []
    sections = [
        (
            "Similar Factor Stocks",
            related.get("similar_factor_stocks") or [],
            False,
        ),
        (
            f"{snapshot.sector} Competitors" if snapshot.sector else "Industry Competitors",
            related.get("industry_competitors") or [],
            False,
        ),
        (
            "Related Market Sectors",
            related.get("related_market_sectors") or [],
            True,
        ),
    ]
    for title, items, include_sector in sections:
        if not items:
            continue
        panels.append(
            '<section class="panel related-panel">'
            f"<h2>{html.escape(title)}</h2>"
            + _related_link_list(items, include_sector=include_sector)
            + "</section>"
        )
    if not panels:
        return ""
    return '<div class="related-grid">' + "".join(panels) + "</div>"


def _absolute_url(path: str) -> str:
    return f"{flask.request.url_root.rstrip('/')}{path}"


def _metric_property(name: str, value, unit_text: str | None = None) -> dict | None:
    if value is None:
        return None
    prop = {
        "@type": "PropertyValue",
        "name": name,
        "value": value,
    }
    if unit_text:
        prop["unitText"] = unit_text
    return prop


def _structured_data(snapshot, canonical_url: str) -> str:
    date_published = (
        snapshot.created_at.isoformat()
        if snapshot.created_at is not None
        else snapshot.analysis_date.isoformat()
    )
    metrics = [
        _metric_property("Final rating", snapshot.final_rating),
        _metric_property("Valuation score", snapshot.valuation_score, "points out of 100"),
        _metric_property("Quality score", snapshot.quality_score, "points out of 100"),
        _metric_property("Growth score", snapshot.growth_score, "points out of 100"),
        _metric_property("Momentum score", snapshot.momentum_score, "points out of 100"),
        _metric_property("Risk score", snapshot.risk_score, "points out of 100"),
        _metric_property("Intrinsic value", snapshot.intrinsic_value, "USD"),
        _metric_property("Market price", snapshot.market_price, "USD"),
        _metric_property("Market fear score", snapshot.market_fear_score, "points out of 100"),
        _metric_property("Algorithm version", snapshot.algorithm_version),
    ]
    metrics = [metric for metric in metrics if metric is not None]
    graph = {
        "@context": "https://schema.org",
        "@graph": [
            {
                "@type": "Article",
                "@id": f"{canonical_url}#article",
                "headline": snapshot.title,
                "description": snapshot.description,
                "url": canonical_url,
                "mainEntityOfPage": canonical_url,
                "datePublished": date_published,
                "dateModified": date_published,
                "articleSection": "Stock analysis",
                "author": {
                    "@type": "Organization",
                    "name": "FactorResearch",
                    "url": flask.request.url_root.rstrip("/"),
                },
                "publisher": {
                    "@type": "Organization",
                    "name": "FactorResearch",
                    "url": flask.request.url_root.rstrip("/"),
                },
                "about": {
                    "@type": "Corporation",
                    "name": snapshot.company_name,
                    "tickerSymbol": snapshot.ticker,
                    "industry": snapshot.sector or None,
                },
                "mentions": {
                    "@type": "ItemList",
                    "itemListElement": metrics,
                },
            },
            {
                "@type": "BreadcrumbList",
                "@id": f"{canonical_url}#breadcrumb",
                "itemListElement": [
                    {
                        "@type": "ListItem",
                        "position": 1,
                        "name": "Home",
                        "item": flask.request.url_root.rstrip("/"),
                    },
                    {
                        "@type": "ListItem",
                        "position": 2,
                        "name": f"{snapshot.ticker} Analysis",
                        "item": canonical_url,
                    },
                ],
            },
        ],
    }
    return json.dumps(graph, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")


@analyze_pages.route("/analyze/<ticker>/<yyyymmdd>")
def historical_analysis_page(ticker: str, yyyymmdd: str):
    ticker = (ticker or "").upper()
    if not _TICKER_RE.match(ticker) or not _DATE_RE.match(yyyymmdd):
        flask.abort(404)

    try:
        snapshot = get_snapshot(ticker, yyyymmdd)
    except ValueError:
        flask.abort(404)

    if snapshot is None:
        flask.abort(404)

    compare_date = flask.request.args.get("compare", "").strip()
    if compare_date and not _DATE_RE.match(compare_date):
        flask.abort(404)

    comparison = None
    if compare_date:
        comparison = get_snapshot(ticker, compare_date)
        if comparison is None or comparison.ticker != snapshot.ticker:
            flask.abort(404)

    history = list_ticker_snapshots(ticker, limit=24)
    related = list_related_snapshots(snapshot, limit=5)

    title = html.escape(snapshot.title)
    description = html.escape(snapshot.description)
    company = html.escape(snapshot.company_name)
    rating = html.escape(snapshot.final_rating)
    canonical_url = _absolute_url(snapshot.public_path)
    url = html.escape(canonical_url)
    structured_data = _structured_data(snapshot, canonical_url)

    body = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{title}</title>
  <meta name="description" content="{description}">
  <link rel="canonical" href="{url}">
  <script type="application/ld+json">{structured_data}</script>
  <style>
    body {{ margin:0; font-family:Arial,sans-serif; color:#111827; background:#f7f8fb; }}
    main {{ max-width:960px; margin:0 auto; padding:40px 20px; }}
    header {{ border-bottom:1px solid #d7dce5; margin-bottom:24px; }}
    h1 {{ margin:0 0 8px; font-size:36px; }}
    h2 {{ margin:0 0 12px; font-size:24px; }}
    .muted {{ color:#5f6978; }}
    .grid {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(180px,1fr)); gap:12px; }}
    .metric, .panel {{ background:white; border:1px solid #d7dce5; border-radius:8px; padding:16px; }}
    .panel {{ margin-top:18px; }}
    .label {{ color:#5f6978; font-size:13px; }}
    .value {{ font-size:24px; font-weight:700; margin-top:6px; }}
    .compare-form label {{ display:block; color:#5f6978; font-size:13px; margin-bottom:6px; }}
    .form-row {{ display:flex; gap:10px; flex-wrap:wrap; }}
    select {{ min-width:240px; flex:1; border:1px solid #c8ced8; border-radius:6px; padding:10px 12px; background:white; }}
    button {{ border:0; border-radius:6px; padding:10px 16px; background:#111827; color:white; font-weight:700; cursor:pointer; }}
    .compare-grid {{ margin-top:12px; }}
    .compare-prev {{ color:#5f6978; margin-top:4px; font-size:13px; }}
    .delta {{ display:inline-block; margin-top:10px; font-weight:700; }}
    .delta.up {{ color:#047857; }}
    .delta.down {{ color:#b91c1c; }}
    .delta.flat {{ color:#5f6978; }}
    .rating-change {{ margin:12px 0; }}
    .history-list {{ display:grid; gap:8px; }}
    .history-row {{ display:grid; grid-template-columns:1fr auto auto; gap:12px; align-items:center; padding:10px 0; border-top:1px solid #eef1f5; color:#111827; }}
    .history-row:first-child {{ border-top:0; }}
    .history-row.current {{ color:#5f6978; }}
    .history-date {{ color:inherit; text-decoration:none; font-weight:700; }}
    .history-date:hover, .history-action:hover {{ text-decoration:underline; }}
    .history-action {{ color:#2563eb; font-size:13px; text-decoration:none; }}
    .related-grid {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(260px,1fr)); gap:12px; margin-top:18px; }}
    .related-panel {{ margin-top:0; }}
    .related-list {{ list-style:none; margin:0; padding:0; display:grid; gap:10px; }}
    .related-item {{ display:grid; gap:3px; padding-top:10px; border-top:1px solid #eef1f5; }}
    .related-item:first-child {{ padding-top:0; border-top:0; }}
    .related-item a {{ color:#111827; font-weight:700; text-decoration:none; }}
    .related-item a:hover {{ text-decoration:underline; }}
    .related-item span {{ color:#5f6978; font-size:13px; }}
    @media (max-width: 620px) {{
      main {{ padding:28px 14px; }}
      h1 {{ font-size:30px; }}
      .history-row {{ grid-template-columns:1fr; gap:4px; }}
    }}
  </style>
</head>
<body>
<main>
  <header>
    <p class="muted">FactorResearch historical analysis</p>
    <h1>{company} Stock Analysis</h1>
    <p>{snapshot.analysis_date.isoformat()} · {html.escape(snapshot.ticker)} · Algorithm {html.escape(snapshot.algorithm_version)}</p>
  </header>
  <section class="grid">
    <div class="metric"><div class="label">Final Rating</div><div class="value">{rating}</div></div>
    <div class="metric"><div class="label">Valuation Score</div><div class="value">{_fmt(snapshot.valuation_score, "/100")}</div></div>
    <div class="metric"><div class="label">Quality Score</div><div class="value">{_fmt(snapshot.quality_score, "/100")}</div></div>
    <div class="metric"><div class="label">Growth Score</div><div class="value">{_fmt(snapshot.growth_score, "/100")}</div></div>
    <div class="metric"><div class="label">Momentum Score</div><div class="value">{_fmt(snapshot.momentum_score, "/100")}</div></div>
    <div class="metric"><div class="label">Risk Score</div><div class="value">{_fmt(snapshot.risk_score, "/100")}</div></div>
    <div class="metric"><div class="label">Intrinsic Value</div><div class="value">{_fmt(snapshot.intrinsic_value)}</div></div>
    <div class="metric"><div class="label">Market Price</div><div class="value">{_fmt(snapshot.market_price)}</div></div>
    <div class="metric"><div class="label">Market Fear Score</div><div class="value">{_fmt(snapshot.market_fear_score, "/100")}</div></div>
  </section>
  {_history_picker(snapshot, history, compare_date or None)}
  {_comparison_section(snapshot, comparison)}
  {_history_links(snapshot, history)}
  {_related_links_section(snapshot, related)}
</main>
</body>
</html>"""
    return flask.Response(body, mimetype="text/html")
