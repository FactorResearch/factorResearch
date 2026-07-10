from __future__ import annotations

import html
import json
import re

import flask

from codes import auth
from codes.data import db
from codes.models.analysis_snapshot import company_slug
from codes.services import permissions
from codes.services.analysis_snapshot_service import (
    get_company_snapshots_by_slug,
    get_custom_snapshot_for_owner,
    get_snapshot,
    list_custom_snapshots,
    list_related_snapshots,
    list_ticker_snapshots,
    save_standard_snapshot,
)


analyze_pages = flask.Blueprint("analysis_pages", __name__)
_TICKER_RE = re.compile(r"^[A-Z]{1,6}(\.[A-Z])?$")
_DATE_RE = re.compile(r"^(?:\d{8}|\d{4}-\d{2}-\d{2})$")
_SLUG_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


def _date_key(value: str) -> str:
    return value.replace("-", "")


def _theme_for(snapshot) -> dict[str, str]:
    approved = {
        "apple": ("#a7b0bc", "#f4f5f7", "precision"),
        "nvidia": ("#76b900", "#b5e853", "compute"),
        "coca-cola": ("#e43b3b", "#ff9c78", "consumer"),
        "jpmorgan-chase": ("#2674b8", "#76b8e8", "finance"),
        "tesla": ("#e82127", "#f17b7f", "mobility"),
        "microsoft": ("#1688d4", "#45c4a0", "platform"),
        "alphabet": ("#4285f4", "#a66ee5", "network"),
        "meta-platforms": ("#1687f8", "#8b5cf6", "network"),
    }
    accent, accent_2, motif = approved.get(
        company_slug(snapshot.company_name),
        ("#448aff", "#00b8d4", "research"),
    )
    return {"accent": accent, "accent_2": accent_2, "motif": motif}


def _official_history_cards(history) -> str:
    rows = []
    previous = None
    for item in reversed(history):
        score_change = _delta(item.valuation_score, previous.valuation_score) if previous else None
        rows.append((item, score_change))
        previous = item
    cards = []
    current_price = history[0].market_price if history else None
    for item, score_change in reversed(rows):
        metrics = item.official_metrics or {}
        price_change = None
        if current_price is not None and item.market_price:
            price_change = (current_price / item.market_price - 1) * 100
        cards.append(
            '<article class="history-card">'
            '<div class="history-card-head">'
            f'<div><span class="official-kicker">FactorResearch official</span><time datetime="{item.analysis_date.isoformat()}">{item.analysis_date.isoformat()}</time></div>'
            f'<span class="score-chip">{_fmt(item.valuation_score, "/100")}</span></div>'
            f'<h3>{html.escape(item.final_rating)}</h3>'
            f'<p>Score change: {_fmt_delta(score_change)} · Price at analysis: ${_fmt(item.market_price)} · Current-price change: {_fmt_delta(price_change, "%")}</p>'
            '<div class="mini-grid">'
            f'<span>Graham {_fmt(metrics.get("graham_score"))}</span><span>Piotroski {_fmt(metrics.get("piotroski_f_score"))}</span>'
            f'<span>Altman Z {_fmt(metrics.get("altman_z_score"))}</span><span>Beneish M {_fmt(metrics.get("beneish_m_score"))}</span>'
            f'<span>Ohlson O {_fmt(metrics.get("ohlson_o_score"))}</span><span>Margin of safety {_fmt(metrics.get("margin_of_safety"), "%")}</span>'
            f'<span>Quality {_fmt(item.quality_score)}</span><span>Profitability {_fmt(metrics.get("profitability_score"))}</span>'
            f'<span>Growth {_fmt(item.growth_score)}</span><span>Momentum {_fmt(item.momentum_score)}</span><span>Risk {_fmt(item.risk_score)}</span>'
            '</div>'
            f'<a href="{html.escape(item.permanent_path)}">Complete historical report</a>'
            '</article>'
        )
    return "".join(cards)


def _custom_history_column(user_id: str | None, ticker: str) -> str:
    if not user_id:
        return '<div class="upgrade"><h2>My Custom Models</h2><p>Sign in and upgrade to access private custom-formula history.</p></div>'
    access = permissions.can_access_feature(user_id, permissions.Feature.BACKTEST)
    if not access.allowed:
        return f'<div class="upgrade"><h2>My Custom Models</h2><p>{html.escape(access.message)}</p></div>'
    custom = list_custom_snapshots(user_id, ticker, limit=12)
    if not custom:
        return '<section class="section-shell"><h2>My Custom Models</h2><p>No custom analyses saved for this company.</p></section>'
    cards = []
    for item in custom:
        cards.append(
            '<article class="history-card private">'
            f'<time>{item.analysis_date.isoformat()}</time><h3>{html.escape(item.formula_name)}</h3>'
            f'<p>Version {html.escape(item.formula_version)} · Score {_fmt(item.composite_score)}</p>'
            f'<a rel="nofollow" href="{html.escape(item.private_path)}">Open private analysis</a>'
            '</article>'
        )
    return '<section class="section-shell"><h2>My Custom Models</h2>' + "".join(cards) + '</section>'


@analyze_pages.route("/analyze/<slug>", strict_slashes=False)
def company_analysis_page(slug: str):
    raw_slug = slug or ""
    ticker = raw_slug.upper() if raw_slug == raw_slug.upper() and _TICKER_RE.match(raw_slug) else None
    slug = raw_slug.lower()
    if not ticker and not _SLUG_RE.match(slug):
        flask.abort(404)
    try:
        page = max(1, int(flask.request.args.get("page", "1")))
        if ticker:
            all_history = list_ticker_snapshots(ticker, limit=min(page * 12, 120))
            if not all_history and page == 1:
                cached = db.get_analysis(ticker)
                if cached and not cached.get("error"):
                    save_standard_snapshot(cached)
                    all_history = list_ticker_snapshots(ticker, limit=12)
            history = all_history[(page - 1) * 12:page * 12]
        else:
            history = get_company_snapshots_by_slug(slug, limit=12, offset=(page - 1) * 12)
    except (TypeError, ValueError):
        flask.abort(404)
    except Exception as exc:
        print(f"Company snapshot lookup failed for {slug}: {type(exc).__name__}: {exc}")
        fallback = _dash_shell_response()
        if fallback is not None:
            return fallback
        flask.abort(404)
    if not history:
        fallback = _dash_shell_response()
        if fallback is not None:
            return fallback
        flask.abort(404)
    latest = history[0]
    if not ticker and company_slug(latest.company_name) != slug:
        flask.abort(404)
    theme = _theme_for(latest)
    accent = theme["accent"]
    accent_2 = theme["accent_2"]
    motif = theme["motif"]
    canonical = _absolute_url(latest.company_path)
    title = f"{latest.company_name} Stock Analysis, Valuation and Historical Scores | FactorResearch"
    description = (
        f"View {latest.company_name}'s historical valuation, financial strength, risk scores, "
        "intrinsic value estimates, and FactorResearch analysis history."
    )
    landing_schema = json.dumps({
        "@context": "https://schema.org",
        "@type": "CollectionPage",
        "name": title,
        "description": description,
        "url": canonical,
        "about": {
            "@type": "Corporation",
            "name": latest.company_name,
            "tickerSymbol": latest.ticker,
            "industry": latest.sector or None,
        },
    }, separators=(",", ":")).replace("</", "<\\/")
    user_id = auth.get_authenticated_user_id()
    custom_column = _custom_history_column(user_id, latest.ticker)
    pagination = (
        f'<nav aria-label="History pages"><a href="?page={page - 1}">Newer</a></nav>'
        if page > 1 else
        (f'<nav aria-label="History pages"><a href="?page={page + 1}">Older</a></nav>' if len(history) == 12 else "")
    )
    body = f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>{html.escape(title)}</title>
<meta name="description" content="{html.escape(description)}"><meta name="robots" content="index,follow">
<meta property="og:title" content="{html.escape(title)}"><meta property="og:description" content="{html.escape(description)}">
<meta property="og:url" content="{html.escape(canonical)}"><link rel="canonical" href="{html.escape(canonical)}">
<script type="application/ld+json">{landing_schema}</script>
<style>
:root{{--accent:{accent};--accent-2:{accent_2};--bg:#0d1117;--surface:#161d2a;--card:#1e2a3a;--border:#29384b;--text:#e8eaf0;--dim:#8899aa;--green:#00e676;--red:#ff1744;--amber:#ffab00}}
*{{box-sizing:border-box}}body{{margin:0;background:var(--bg);color:var(--text);font:14px/1.55 Inter,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}}a{{color:inherit}}.topbar{{height:64px;border-bottom:1px solid #1e2a3a;display:flex;align-items:center;justify-content:space-between;padding:0 max(20px,calc((100vw - 1360px)/2));background:rgba(13,17,23,.96)}}.brand{{display:flex;align-items:center;gap:10px;font-weight:800;font-size:17px;text-decoration:none}}.brand-mark{{width:32px;height:32px;border-radius:7px;display:grid;place-items:center;background:rgba(22,119,255,.14);color:#448aff}}.topnav{{display:flex;gap:6px;padding:4px;background:#161d2a;border:1px solid #1e2a3a;border-radius:8px}}.topnav a{{padding:7px 13px;color:var(--dim);text-decoration:none;border-radius:6px;font-size:13px}}.topnav a.active{{background:#1677ff;color:white}}main{{max-width:1360px;margin:auto;padding:24px 20px 64px}}.hero{{position:relative;overflow:hidden;min-height:260px;padding:34px;border:1px solid color-mix(in srgb,var(--accent) 38%,#29384b);border-radius:12px;background:linear-gradient(120deg,#161d2a 0%,#121a26 62%,color-mix(in srgb,var(--accent) 13%,#121a26));display:flex;align-items:flex-end}}.hero:before,.hero:after{{content:"";position:absolute;border:1px solid color-mix(in srgb,var(--accent) 32%,transparent);border-radius:50%;pointer-events:none}}.hero:before{{width:360px;height:360px;right:-80px;top:-190px;box-shadow:0 0 90px color-mix(in srgb,var(--accent) 18%,transparent)}}.hero:after{{width:210px;height:210px;right:155px;bottom:-145px;border-color:color-mix(in srgb,var(--accent-2) 35%,transparent)}}.hero-content{{position:relative;z-index:1;display:flex;align-items:center;gap:24px}}.monogram{{width:96px;height:96px;display:grid;place-items:center;border-radius:24px;background:linear-gradient(145deg,var(--accent),var(--accent-2));color:white;font-size:31px;font-weight:800;letter-spacing:-.04em;box-shadow:0 16px 40px color-mix(in srgb,var(--accent) 24%,transparent)}}.eyebrow,.official-kicker{{font:600 10px/1.4 "DM Mono",monospace;letter-spacing:.12em;text-transform:uppercase;color:var(--accent)}}h1{{font-size:36px;line-height:1.12;margin:7px 0 8px;letter-spacing:-.03em}}.hero p{{max-width:720px;color:var(--dim);margin:0}}.hero-meta{{display:flex;gap:8px;margin-top:16px;flex-wrap:wrap}}.hero-meta span,.hero-meta a{{border:1px solid #304158;background:rgba(13,17,23,.55);border-radius:999px;padding:5px 10px;color:#b8c4d2;text-decoration:none;font-size:12px}}.columns{{display:grid;grid-template-columns:minmax(0,1.65fr) minmax(320px,.85fr);gap:20px;margin-top:20px}}.section-shell,.upgrade{{background:var(--surface);border:1px solid #1e2a3a;border-radius:10px;padding:20px}}.section-title{{display:flex;justify-content:space-between;align-items:end;border-bottom:1px solid #263447;padding-bottom:14px;margin-bottom:14px}}h2{{font-size:17px;margin:0}}.section-title p{{margin:2px 0 0;color:var(--dim);font-size:12px}}.history-card{{background:var(--card);border:1px solid var(--border);border-left:3px solid var(--accent);border-radius:8px;padding:16px;margin:12px 0;transition:.18s ease}}.history-card:hover{{transform:translateY(-1px);border-color:color-mix(in srgb,var(--accent) 60%,#29384b)}}.history-card-head{{display:flex;justify-content:space-between;gap:12px}}time{{display:block;color:var(--dim);font:500 11px "DM Mono",monospace;margin-top:3px}}.score-chip{{font:600 13px "DM Mono",monospace;color:var(--green);background:rgba(0,230,118,.1);border:1px solid rgba(0,230,118,.2);border-radius:999px;padding:5px 9px;height:max-content}}.history-card h3{{font-size:18px;margin:12px 0 4px}}.history-card p{{color:var(--dim);font-size:12px}}.history-card>a{{display:inline-block;color:#69a7ff;font-weight:650;text-decoration:none;margin-top:12px}}.mini-grid{{display:grid;grid-template-columns:repeat(3,1fr);gap:1px;background:#2a394c;border:1px solid #2a394c;border-radius:6px;overflow:hidden;margin-top:12px}}.mini-grid span{{background:#172231;padding:8px;color:#aebccc;font:500 10px "DM Mono",monospace}}.private{{border-left-color:var(--accent-2)}}.upgrade{{border-style:dashed;color:var(--dim)}}.upgrade h2{{color:var(--text);margin-bottom:8px}}.tabs{{display:none}}nav[aria-label="History pages"] a{{display:inline-block;margin-top:12px;color:#69a7ff}}.footer{{max-width:1360px;margin:auto;padding:20px;border-top:1px solid #1e2a3a;color:#526173;font-size:11px}}@media(max-width:760px){{.topnav{{display:none}}main{{padding:14px 12px 40px}}.hero{{min-height:310px;padding:24px}}.hero-content{{align-items:flex-start;flex-direction:column}}.monogram{{width:72px;height:72px;border-radius:18px}}h1{{font-size:29px}}.columns{{display:block}}.columns>section,.columns>div{{margin-bottom:14px}}.tabs{{display:block;color:var(--dim);font-size:12px;margin:14px 2px}}.mini-grid{{grid-template-columns:repeat(2,1fr)}}}}
</style></head>
<body><div class="topbar"><a class="brand" href="/"><span class="brand-mark">FR</span>FactorResearch</a><nav class="topnav" aria-label="Primary"><a href="/">Screener</a><a href="/analyze/{html.escape(latest.ticker)}">Analyze</a><a href="/?tab=portfolio">Portfolio</a><a class="active" href="{html.escape(latest.company_path)}">Company Research</a></nav></div><main><header class="hero" data-motif="{motif}"><div class="hero-content"><div class="monogram" aria-hidden="true">{html.escape(latest.ticker[:4])}</div><div><span class="eyebrow">FactorResearch company dossier · {html.escape(motif)}</span><h1>{html.escape(latest.company_name)} <span style="color:var(--dim)">({html.escape(latest.ticker)})</span></h1><p>{html.escape(description)}</p><div class="hero-meta"><a href="/?tab=screener&amp;sector={html.escape(latest.sector)}">{html.escape(latest.sector or 'Public company')}</a><span>{len(history)} official snapshot{'s' if len(history) != 1 else ''}</span><span>Updated {latest.analysis_date.isoformat()}</span></div></div></div></header>
<nav class="tabs" aria-label="Analysis sections">FactorResearch History&nbsp;&nbsp;·&nbsp;&nbsp;My Custom Models</nav><div class="columns"><section class="section-shell"><div class="section-title"><div><h2>FactorResearch History</h2><p>Immutable results from the official methodology</p></div></div>{_official_history_cards(history)}{pagination}</section><div>{custom_column}</div></div></main><footer class="footer">© FactorResearch · Independent financial research · Company-inspired visuals use abstract, non-proprietary design elements.</footer></body></html>"""
    response = flask.Response(body, mimetype="text/html")
    response.headers["Cache-Control"] = "private, no-store" if user_id else "public, max-age=300"
    return response


@analyze_pages.route("/analyze/<slug>/custom/<snapshot_id>")
def custom_analysis_page(slug: str, snapshot_id: str):
    user_id = auth.get_authenticated_user_id()
    if not user_id:
        flask.abort(401)
    access = permissions.can_access_feature(user_id, permissions.Feature.BACKTEST)
    if not access.allowed:
        flask.abort(403)
    snapshot = get_custom_snapshot_for_owner(snapshot_id, user_id)
    if snapshot is None or company_slug(snapshot.company_name) != slug:
        flask.abort(404)
    factors = "".join(f"<li>{html.escape(str(name))}: {html.escape(str(weight))}</li>" for name, weight in snapshot.factors.items())
    backtest = html.escape(json.dumps(snapshot.backtest_summary, sort_keys=True))
    default_comparison = html.escape(json.dumps(snapshot.default_comparison, sort_keys=True))
    benchmark_comparison = html.escape(json.dumps(snapshot.benchmark_comparison, sort_keys=True))
    body = f"""<!doctype html><html><head><meta charset="utf-8"><meta name="robots" content="noindex,nofollow,noarchive"><title>{html.escape(snapshot.formula_name)} | Private FactorResearch Analysis</title></head><body><main><h1>{html.escape(snapshot.formula_name)}</h1><p>{html.escape(snapshot.company_name)} ({html.escape(snapshot.ticker)}) · {snapshot.analysis_date.isoformat()}</p><p>Formula version: {html.escape(snapshot.formula_version)} · Custom score: {_fmt(snapshot.composite_score)}</p><h2>Selected factors and weights</h2><ul>{factors}</ul><h2>Backtest summary</h2><pre>{backtest}</pre><h2>Against FactorResearch default</h2><pre>{default_comparison}</pre><h2>Against benchmark</h2><pre>{benchmark_comparison}</pre><h2>Saved notes</h2><p>{html.escape(snapshot.notes)}</p></main></body></html>"""
    response = flask.Response(body, mimetype="text/html")
    response.headers["Cache-Control"] = "private, no-store"
    response.headers["X-Robots-Tag"] = "noindex, nofollow, noarchive"
    return response


def _dash_shell_response():
    dash_view = flask.current_app.view_functions.get("/<path:path>")
    if dash_view is None:
        return None
    return dash_view(flask.request.path.lstrip("/"))


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


def _drop_empty(value):
    if isinstance(value, dict):
        return {
            key: cleaned
            for key, child in value.items()
            if (cleaned := _drop_empty(child)) is not None
        }
    if isinstance(value, list):
        return [cleaned for child in value if (cleaned := _drop_empty(child)) is not None]
    if value == "" or value is None:
        return None
    return value


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
                "@type": "WebPage",
                "@id": f"{canonical_url}#webpage",
                "url": canonical_url,
                "name": snapshot.title,
                "description": snapshot.description,
                "datePublished": date_published,
                "dateModified": date_published,
                "isPartOf": {
                    "@type": "WebSite",
                    "name": "FactorResearch",
                    "url": flask.request.url_root.rstrip("/"),
                },
                "about": {"@id": f"{canonical_url}#stock"},
                "primaryImageOfPage": flask.request.url_root.rstrip("/") + "/assets/logo.png",
            },
            {
                "@type": "Article",
                "@id": f"{canonical_url}#article",
                "headline": snapshot.title,
                "description": snapshot.description,
                "url": canonical_url,
                "mainEntityOfPage": {"@id": f"{canonical_url}#webpage"},
                "datePublished": date_published,
                "dateModified": date_published,
                "articleSection": "Stock analysis",
                "keywords": snapshot.keywords,
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
                    "@id": f"{canonical_url}#stock",
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
    # Keep the primary Article first for consumers that do not traverse WebPage nodes.
    graph["@graph"] = [graph["@graph"][1], graph["@graph"][2], graph["@graph"][0]]
    graph = _drop_empty(graph)
    return json.dumps(graph, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")


@analyze_pages.route("/analyze/<ticker>/<yyyymmdd>")
def historical_analysis_page(ticker: str, yyyymmdd: str):
    route_id = ticker or ""
    if not _DATE_RE.match(yyyymmdd):
        flask.abort(404)

    ticker = route_id.upper()
    is_company_slug = route_id == route_id.lower() and _SLUG_RE.match(route_id)
    if is_company_slug or not _TICKER_RE.match(ticker):
        slug = route_id.lower()
        if not _SLUG_RE.match(slug):
            flask.abort(404)
        candidates = get_company_snapshots_by_slug(slug, limit=1)
        if not candidates:
            flask.abort(404)
        ticker = candidates[0].ticker

    try:
        snapshot = get_snapshot(ticker, _date_key(yyyymmdd))
    except ValueError:
        flask.abort(404)
    except Exception as exc:
        print(f"Analysis snapshot lookup failed for {ticker}/{yyyymmdd}: {type(exc).__name__}: {exc}")
        fallback = _dash_shell_response()
        if fallback is not None:
            return fallback
        flask.abort(404)

    if snapshot is None:
        fallback = _dash_shell_response()
        if fallback is not None:
            return fallback
        flask.abort(404)

    compare_date = flask.request.args.get("compare", "").strip()
    if compare_date and not _DATE_RE.match(compare_date):
        flask.abort(404)

    comparison = None
    if compare_date:
        comparison = get_snapshot(ticker, _date_key(compare_date))
        if comparison is None or comparison.ticker != snapshot.ticker:
            flask.abort(404)

    history = list_ticker_snapshots(ticker, limit=24)
    related = list_related_snapshots(snapshot, limit=5)

    title = html.escape(snapshot.title)
    description = html.escape(snapshot.description)
    keywords = html.escape(snapshot.keywords)
    company = html.escape(snapshot.company_name)
    rating = html.escape(snapshot.final_rating)
    canonical_url = _absolute_url(
        snapshot.permanent_path if route_id.lower() == company_slug(snapshot.company_name)
        else snapshot.public_path
    )
    url = html.escape(canonical_url)
    structured_data = _structured_data(snapshot, canonical_url)
    published = html.escape(
        snapshot.created_at.isoformat()
        if snapshot.created_at is not None
        else snapshot.analysis_date.isoformat()
    )

    body = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{title}</title>
  <meta name="description" content="{description}">
  <meta name="keywords" content="{keywords}">
  <meta name="robots" content="index,follow,max-snippet:-1,max-image-preview:large">
  <meta property="og:type" content="article">
  <meta property="og:site_name" content="FactorResearch">
  <meta property="og:title" content="{title}">
  <meta property="og:description" content="{description}">
  <meta property="og:url" content="{url}">
  <meta property="article:published_time" content="{published}">
  <meta property="article:modified_time" content="{published}">
  <meta name="twitter:card" content="summary">
  <meta name="twitter:title" content="{title}">
  <meta name="twitter:description" content="{description}">
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
    <p><time datetime="{snapshot.analysis_date.isoformat()}">{snapshot.analysis_date.isoformat()}</time> · {html.escape(snapshot.ticker)} · Algorithm {html.escape(snapshot.algorithm_version)}</p>
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
