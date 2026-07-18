from __future__ import annotations

import re
from datetime import date
from unittest.mock import patch

import flask

from codes.models.analysis_snapshot import AnalysisSnapshot
from codes.routes.analyze import analyze_pages
from codes.sitemap_generator import generate_analysis_sitemap


def _snapshot() -> AnalysisSnapshot:
    """Build a deterministic official snapshot for route and sitemap tests."""
    return AnalysisSnapshot(
        ticker="AAPL",
        company_name="Apple Inc.",
        analysis_date=date(2026, 7, 8),
        algorithm_version="standard-v1",
        valuation_score=80,
        quality_score=70,
        growth_score=65,
        momentum_score=60,
        risk_score=55,
        final_rating="HIGH CONVICTION",
        intrinsic_value=190,
        market_price=180,
        market_fear_score=35,
        sector="Technology",
    )


def _client() -> flask.testing.FlaskClient:
    """Create a minimal client containing only the historical-page blueprint."""
    app = flask.Flask(__name__)
    app.register_blueprint(analyze_pages)
    return app.test_client()


def test_seo_historical_route_renders_with_requested_canonical_url():
    snapshot = _snapshot()
    with patch("codes.routes.analyze.get_snapshot", return_value=snapshot), \
         patch("codes.routes.analyze.list_ticker_snapshots", return_value=[snapshot]), \
         patch("codes.routes.analyze.list_related_snapshots", return_value={}):
        response = _client().get("/analyze/AAPL/20260708")

    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert '<meta name="robots" content="index,follow' in body
    assert '<link rel="canonical" href="http://localhost/analyze/AAPL/20260708">' in body
    assert "http://localhost/AAPL/analyze/20260708" not in body


def test_analysis_sitemap_lists_seo_path_and_not_legacy_path():
    snapshot = _snapshot()
    with patch("codes.sitemap_generator.list_public_snapshots", return_value=[snapshot]):
        sitemap = generate_analysis_sitemap("https://example.com")

    assert "https://example.com/analyze/AAPL/20260708" in sitemap
    assert "https://example.com/AAPL/analyze/20260708" not in sitemap
    assert len(re.findall(r"<url>", sitemap)) == 2
