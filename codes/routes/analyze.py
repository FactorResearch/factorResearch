from __future__ import annotations

import html
import re

import flask

from codes.services.analysis_snapshot_service import get_snapshot


analyze_pages = flask.Blueprint("analysis_pages", __name__)
_TICKER_RE = re.compile(r"^[A-Z]{1,6}(\.[A-Z])?$")
_DATE_RE = re.compile(r"^\d{8}$")


def _fmt(value, suffix: str = "") -> str:
    if value is None:
        return "N/A"
    return f"{value:.2f}{suffix}"


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

    title = html.escape(snapshot.title)
    description = html.escape(snapshot.description)
    company = html.escape(snapshot.company_name)
    rating = html.escape(snapshot.final_rating)
    url = html.escape(snapshot.public_path)

    body = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{title}</title>
  <meta name="description" content="{description}">
  <link rel="canonical" href="{url}">
  <style>
    body {{ margin:0; font-family:Arial,sans-serif; color:#111827; background:#f7f8fb; }}
    main {{ max-width:960px; margin:0 auto; padding:40px 20px; }}
    header {{ border-bottom:1px solid #d7dce5; margin-bottom:24px; }}
    h1 {{ margin:0 0 8px; font-size:36px; }}
    .muted {{ color:#5f6978; }}
    .grid {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(180px,1fr)); gap:12px; }}
    .metric {{ background:white; border:1px solid #d7dce5; border-radius:8px; padding:16px; }}
    .label {{ color:#5f6978; font-size:13px; }}
    .value {{ font-size:24px; font-weight:700; margin-top:6px; }}
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
</main>
</body>
</html>"""
    return flask.Response(body, mimetype="text/html")

