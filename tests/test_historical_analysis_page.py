import json
import re
from datetime import date
from pathlib import Path
from unittest.mock import patch

import flask

from codes.models.analysis_snapshot import AnalysisSnapshot
from codes.routes.analyze import analyze_pages


ROOT = Path(__file__).resolve().parents[1]


def _snapshot(yyyymmdd, *, ticker="AAPL", name="Apple Inc.", valuation=80, rating="HIGH CONVICTION", sector="Technology"):
    analysis_date = date(
        int(yyyymmdd[:4]),
        int(yyyymmdd[4:6]),
        int(yyyymmdd[6:8]),
    )
    return AnalysisSnapshot(
        ticker=ticker,
        company_name=name,
        analysis_date=analysis_date,
        algorithm_version="standard-v1",
        valuation_score=valuation,
        quality_score=70,
        growth_score=65,
        momentum_score=60,
        risk_score=55,
        final_rating=rating,
        intrinsic_value=190,
        market_price=180,
        market_fear_score=35,
        sector=sector,
    )


def _client():
    app = flask.Flask(__name__)
    app.register_blueprint(analyze_pages)
    return app.test_client()


def test_historical_page_falls_back_to_dash_shell_when_snapshot_db_unavailable():
    app = flask.Flask(__name__)
    app.register_blueprint(analyze_pages)

    def dash_shell(path):
        return flask.Response(f"dash shell for {path}", mimetype="text/html")

    app.add_url_rule("/<path:path>", endpoint="/<path:path>", view_func=dash_shell)

    with patch("codes.routes.analyze.get_snapshot", side_effect=RuntimeError("database missing")):
        response = app.test_client().get("/NVDA/analyze/20260709")

    assert response.status_code == 200
    assert response.get_data(as_text=True) == "dash shell for NVDA/analyze/20260709"


def test_interactive_historical_link_uses_dash_shell():
    app = flask.Flask(__name__)
    app.register_blueprint(analyze_pages)
    app.add_url_rule(
        "/<path:path>", endpoint="/<path:path>",
        view_func=lambda path: flask.Response(f"dash shell for {path}"),
    )

    response = app.test_client().get("/NVDA/analyze/20260709?tab=analyze")

    assert response.status_code == 200
    assert response.get_data(as_text=True) == "dash shell for NVDA/analyze/20260709"


def test_historical_page_renders_compare_picker_and_history_links():
    current = _snapshot("20260708")
    previous = _snapshot("20260608", valuation=74, rating="FAVORABLE")

    with patch("codes.routes.analyze.get_snapshot", return_value=current), \
         patch("codes.routes.analyze.list_ticker_snapshots", return_value=[current, previous]), \
         patch("codes.routes.analyze.list_related_snapshots", return_value={}):
        response = _client().get("/AAPL/analyze/20260708")

    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert "Compare Previous Analysis" in body
    assert 'href="/assets/company_analysis.css"' in body
    assert '<body class="historical-analysis-page">' in body
    assert "<style" not in body
    assert "style=" not in body
    styles = (ROOT / "assets/company_analysis.css").read_text()
    assert ".historical-analysis-page main {" in styles
    assert "max-width: 960px;" in styles
    assert 'name="compare"' in body
    assert "2026-06-08 - FAVORABLE" in body
    assert 'href="/AAPL/analyze/20260608?tab=analyze"' in body
    assert "/AAPL/analyze/20260708?compare=20260608" in body


def test_historical_page_renders_selected_comparison_deltas():
    current = _snapshot("20260708", valuation=82, rating="HIGH CONVICTION")
    previous = _snapshot("20260608", valuation=74, rating="FAVORABLE")

    with patch("codes.routes.analyze.get_snapshot", side_effect=[current, previous]), \
         patch("codes.routes.analyze.list_ticker_snapshots", return_value=[current, previous]), \
         patch("codes.routes.analyze.list_related_snapshots", return_value={}):
        response = _client().get("/AAPL/analyze/20260708?compare=20260608")

    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert "Historical Comparison" in body
    assert "Comparing 2026-07-08 against 2026-06-08." in body
    assert "+8.00/100" in body
    assert "FAVORABLE to HIGH CONVICTION" in body


def test_historical_page_rejects_invalid_compare_date():
    current = _snapshot("20260708")

    with patch("codes.routes.analyze.get_snapshot", return_value=current):
        response = _client().get("/AAPL/analyze/20260708?compare=not-a-date")

    assert response.status_code == 404


def test_historical_page_renders_related_internal_links():
    current = _snapshot("20260708")
    msft = _snapshot("20260708", ticker="MSFT", name="Microsoft Corporation", valuation=78)
    googl = _snapshot("20260708", ticker="GOOGL", name="Alphabet Inc.", valuation=76)
    jpm = _snapshot("20260708", ticker="JPM", name="JPMorgan Chase", valuation=72, sector="Finance")

    related = {
        "similar_factor_stocks": [msft],
        "industry_competitors": [googl],
        "related_market_sectors": [jpm],
    }

    with patch("codes.routes.analyze.get_snapshot", return_value=current), \
         patch("codes.routes.analyze.list_ticker_snapshots", return_value=[current]), \
         patch("codes.routes.analyze.list_related_snapshots", return_value=related):
        response = _client().get("/AAPL/analyze/20260708")

    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert "Similar Factor Stocks" in body
    assert "Technology Competitors" in body
    assert "Related Market Sectors" in body
    assert 'href="/MSFT/analyze/20260708?tab=analyze"' in body
    assert 'href="/GOOGL/analyze/20260708?tab=analyze"' in body
    assert "Finance · HIGH CONVICTION" in body


def test_historical_page_renders_schema_org_json_ld():
    current = _snapshot("20260708")

    with patch("codes.routes.analyze.get_snapshot", return_value=current), \
         patch("codes.routes.analyze.list_ticker_snapshots", return_value=[current]), \
         patch("codes.routes.analyze.list_related_snapshots", return_value={}):
        response = _client().get("/AAPL/analyze/20260708")

    assert response.status_code == 200
    body = response.get_data(as_text=True)
    match = re.search(
        r'<script type="application/ld\+json">(.+?)</script>',
        body,
    )
    assert match is not None

    schema = json.loads(match.group(1))
    assert schema["@context"] == "https://schema.org"

    article = schema["@graph"][0]
    assert article["@type"] == "Article"
    assert article["headline"] == "Apple Inc. Stock Analysis July 8 2026 | Cenvarn"
    assert article["url"] == "http://localhost/AAPL/analyze/20260708"
    assert article["about"]["@type"] == "Corporation"
    assert article["about"]["tickerSymbol"] == "AAPL"

    metric_names = {
        metric["name"]
        for metric in article["mentions"]["itemListElement"]
    }
    assert {"Valuation score", "Final rating", "Algorithm version"} <= metric_names

    breadcrumbs = schema["@graph"][1]
    assert breadcrumbs["@type"] == "BreadcrumbList"
    assert breadcrumbs["itemListElement"][1]["name"] == "AAPL Analysis"


def test_legacy_historical_route_redirects_to_canonical_path():
    current = _snapshot("20260708")
    with patch("codes.routes.analyze.get_snapshot", return_value=current):
        response = _client().get("/analyze/AAPL/2026-07-08?compare=20260608")

    assert response.status_code == 308
    assert response.headers["Location"] == "/AAPL/analyze/20260708?compare=20260608"
