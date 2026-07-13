from __future__ import annotations

import html
import hashlib
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
    known = approved.get(company_slug(snapshot.company_name))
    if known:
        accent, accent_2, motif = known
    else:
        sector = (snapshot.sector or "").lower()
        motif = (
            "finance" if any(word in sector for word in ("financ", "bank", "insurance")) else
            "consumer" if any(word in sector for word in ("consumer", "retail", "beverage", "food")) else
            "compute" if any(word in sector for word in ("semiconductor", "hardware")) else
            "mobility" if any(word in sector for word in ("auto", "transport", "energy")) else
            "precision" if any(word in sector for word in ("health", "medical", "pharma")) else
            "platform" if any(word in sector for word in ("software", "technology", "communication")) else
            "research"
        )
        palettes = [
            ("#448aff", "#00b8d4"), ("#9b7cff", "#dc6fd3"),
            ("#2fbf9f", "#7bd66f"), ("#e88a3d", "#e8c547"),
            ("#ef6275", "#a66ee5"), ("#3aa7d8", "#6a7df0"),
        ]
        digest = hashlib.sha256(snapshot.ticker.encode("utf-8")).digest()
        accent, accent_2 = palettes[digest[0] % len(palettes)]
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
        warnings = []
        if metrics.get("value_trap_warning"):
            warnings.append('<span class="warning-chip">Value Trap Risk</span>')
        if metrics.get("compounder_flag"):
            warnings.append('<span class="positive-chip">Compounder Signal</span>')
        if metrics.get("altman_cap_applied"):
            warnings.append('<span class="danger-chip">Altman Distress Cap</span>')
        price_change = None
        if current_price is not None and item.market_price:
            price_change = (current_price / item.market_price - 1) * 100
        cards.append(
            '<article class="history-card">'
            '<div class="history-card-head">'
            f'<div><span class="official-kicker">FactorResearch official</span><time datetime="{item.analysis_date.isoformat()}">{item.analysis_date.isoformat()}</time></div>'
            f'<span class="score-chip">{_fmt(item.valuation_score, "/100")}</span></div>'
            f'<h3>{html.escape(item.final_rating)}</h3>'
            f'<p>{html.escape(str(metrics.get("verdict_desc") or ""))}</p>'
            f'<div class="warning-row">{"".join(warnings)}</div>'
            f'<p>Score change: {_fmt_delta(score_change)} · Price at analysis: ${_fmt(item.market_price)} · Current-price change: {_fmt_delta(price_change, "%")}</p>'
            '<div class="mini-grid">'
            f'<span>Intrinsic Value {_fmt(metrics.get("graham_score"))}</span><span>Financial Health {_fmt(metrics.get("piotroski_f_score"), "/9")}</span>'
            f'<span>Stability Score {_fmt(metrics.get("altman_z_score"))}</span><span>Margin of Safety {_fmt(metrics.get("margin_of_safety"), "%")}</span>'
            f'<span>Moat Rating {_fmt(item.quality_score)}</span><span>Profitability {_fmt(metrics.get("profitability_score"))}</span>'
            f'<span>Growth Quality {_fmt(item.growth_score)}</span><span>Momentum Analysis {_fmt(item.momentum_score)}</span><span>Risk &amp; Performance {_fmt(item.risk_score)}</span>'
            '</div>'
            f'<a href="{html.escape(item.public_path)}">Complete historical report</a>'
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
    if ticker and flask.request.args.get("tab") == "analyze":
        fallback = _dash_shell_response()
        if fallback is not None:
            return fallback
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
<link rel="stylesheet" href="/assets/company_analysis.css">
<script type="application/ld+json">{landing_schema}</script>
<script>(function(){{try{{var t=localStorage.getItem("fr-theme")||"system";var light=t==="light"||(t==="system"&&window.matchMedia("(prefers-color-scheme: light)").matches);if(light)document.documentElement.classList.add("light");}}catch(e){{}}}})();</script>
</head>
<body><div class="topbar"><a class="brand" href="/"><span class="brand-mark">FR</span>FactorResearch</a><nav class="topnav" aria-label="Primary"><a href="/">Screener</a><a href="/analyze/{html.escape(latest.ticker)}?tab=analyze">Analyze</a><a href="/?tab=portfolio">Portfolio</a><a class="active" href="{html.escape(latest.company_path)}">Company Research</a></nav></div><main><header class="hero" data-motif="{motif}"><div class="hero-content"><div class="monogram" aria-hidden="true">{html.escape(latest.ticker[:4])}</div><div><span class="eyebrow">FactorResearch company dossier · {html.escape(motif)}</span><h1>{html.escape(latest.company_name)} <span class="ticker-symbol">({html.escape(latest.ticker)})</span></h1><p>{html.escape(description)}</p><div class="hero-meta"><a href="/?tab=screener&amp;sector={html.escape(latest.sector)}">{html.escape(latest.sector or 'Public company')}</a><span>{len(history)} official snapshot{'s' if len(history) != 1 else ''}</span><span>Updated {latest.analysis_date.isoformat()}</span></div></div></div></header>
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


def _fmt_pct(value) -> str:
    if value is None:
        return "N/A"
    return f"{float(value) * 100:.2f}%"


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


def _snapshot_factor_research_section(snapshot) -> str:
    metrics = snapshot.official_metrics or {}
    models = metrics.get("factor_research_models") or {}
    if models:
        labels = {
            "capm": "CAPM",
            "ff3": "Fama-French 3",
            "ff5": "Fama-French 5",
            "carhart4": "Carhart 4",
        }
        cards = []
        for key in ("capm", "ff3", "ff5", "carhart4"):
            model = models.get(key)
            if not model:
                continue
            beta = (model.get("betas") or {}).get("mkt_rf")
            cards.append(
                '<div class="metric">'
                f'<div class="label">{html.escape(labels[key])}</div>'
                f'<div class="value">β {_fmt(beta)} · α {_fmt_pct(model.get("alpha_annualized"))} · R² {_fmt_pct(model.get("r_squared"))}</div>'
                "</div>"
            )
        attribution = metrics.get("factor_research_return_attribution") or {}
        if not attribution:
            primary = next((models.get(key) for key in ("carhart4", "ff5", "ff3", "capm") if models.get(key)), {})
            attribution = primary.get("return_attribution") or {}
        attribution_cards = []
        for factor, value in (attribution.get("factor_contributions") or {}).items():
            attribution_cards.append(
                '<div class="metric">'
                f'<div class="label">{html.escape(str(factor).upper())}</div>'
                f'<div class="value">{_fmt_pct(value)}</div>'
                "</div>"
            )
        for label, key in (("Alpha", "alpha"), ("Residual", "residual"), ("Total Excess", "total_excess_return")):
            attribution_cards.append(
                '<div class="metric">'
                f'<div class="label">{html.escape(label)}</div>'
                f'<div class="value">{_fmt_pct(attribution.get(key))}</div>'
                "</div>"
            )
        rolling = metrics.get("factor_research_rolling_attribution") or []
        rolling_body = ""
        if rolling:
            latest = rolling[-1]
            latest_beta = (latest.get("betas") or {}).get("mkt_rf")
            latest_attr = latest.get("return_attribution") or {}
            rolling_body = (
                "<h3>Rolling Attribution</h3>"
                '<div class="grid">'
                f'<div class="metric"><div class="label">Windows</div><div class="value">{len(rolling)}</div></div>'
                f'<div class="metric"><div class="label">Latest Date</div><div class="value">{html.escape(str(latest.get("end_date", "N/A")))}</div></div>'
                f'<div class="metric"><div class="label">Latest Beta</div><div class="value">{_fmt(latest_beta)}</div></div>'
                f'<div class="metric"><div class="label">Latest Excess</div><div class="value">{_fmt_pct(latest_attr.get("total_excess_return"))}</div></div>'
                "</div>"
            )
        body = (
            '<div class="grid">' + "".join(cards) + "</div>"
            "<h3>Return Attribution</h3>"
            '<div class="grid">' + "".join(attribution_cards) + "</div>"
            + rolling_body
        )
    elif any(value is not None for value in (metrics.get("capm_beta"), metrics.get("capm_alpha_annualized"), metrics.get("capm_r_squared"))):
        beta = metrics.get("capm_beta")
        alpha = metrics.get("capm_alpha_annualized")
        r_squared = metrics.get("capm_r_squared")
        body = (
            '<div class="grid">'
            f'<div class="metric"><div class="label">Model</div><div class="value">{html.escape(str(metrics.get("factor_research_model") or "CAPM"))}</div></div>'
            f'<div class="metric"><div class="label">Market Beta</div><div class="value">{_fmt(beta)}</div></div>'
            f'<div class="metric"><div class="label">Annualized Alpha</div><div class="value">{_fmt_pct(alpha)}</div></div>'
            f'<div class="metric"><div class="label">R-Squared</div><div class="value">{_fmt_pct(r_squared)}</div></div>'
            "</div>"
        )
    else:
        body = (
            '<p class="muted">This historical snapshot predates V2.2 factor fields. '
            'The page is still compatible, but exact CAPM beta/alpha cannot be reconstructed '
            'from immutable snapshot metrics alone.</p>'
            '<div class="grid">'
            '<div class="metric"><div class="label">Available Now</div><div class="value">CAPM</div></div>'
            '<div class="metric"><div class="label">Requires Factor Data</div><div class="value">FF3 / FF5 / Carhart</div></div>'
            "</div>"
        )
    return '<section class="panel"><h2>V2.2 Factor Research</h2>' + body + "</section>"


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

    if route_id == route_id.upper() and _TICKER_RE.match(route_id):
        fallback = _dash_shell_response()
        if fallback is not None:
            return fallback

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
  <link rel="stylesheet" href="/assets/company_analysis.css">
  <script type="application/ld+json">{structured_data}</script>
</head>
<body class="historical-analysis-page">
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
  {_snapshot_factor_research_section(snapshot)}
  {_comparison_section(snapshot, comparison)}
  {_history_links(snapshot, history)}
  {_related_links_section(snapshot, related)}
</main>
</body>
</html>"""
    return flask.Response(body, mimetype="text/html")
