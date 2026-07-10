from datetime import date
from unittest.mock import patch

import flask

from codes.models.analysis_snapshot import AnalysisSnapshot, CustomAnalysisSnapshot
from codes.routes.analyze import analyze_pages
from codes.services.permissions import Feature, PermissionResult


def _official():
    return AnalysisSnapshot(
        ticker="AAPL", company_name="Apple Inc.", analysis_date=date(2026, 7, 9),
        algorithm_version="standard-v1", valuation_score=81, quality_score=74,
        growth_score=69, momentum_score=62, risk_score=58,
        final_rating="STRONG BUY", intrinsic_value=220, market_price=195,
        market_fear_score=31, sector="Technology",
    )


def _custom(owner="user-1"):
    return CustomAnalysisSnapshot(
        id="a8f4d2", user_id=owner, ticker="AAPL", company_name="Apple Inc.",
        formula_name="Durable Growth", formula_version="v3", composite_score=86,
        factors={"quality": 0.6, "growth": 0.4}, backtest_summary={"cagr": 14},
        default_comparison={"alpha": 2}, benchmark_comparison={"alpha": 3},
        notes="Long-term model", analysis_date=date(2026, 7, 9),
    )


def _client():
    app = flask.Flask(__name__)
    app.secret_key = "test"
    app.register_blueprint(analyze_pages)
    return app.test_client()


def _client_with_dash_shell():
    app = flask.Flask(__name__)
    app.secret_key = "test"
    app.register_blueprint(analyze_pages)
    app.add_url_rule(
        "/<path:path>", endpoint="/<path:path>",
        view_func=lambda path: flask.Response(f"dash shell for {path}"),
    )
    return app.test_client()


def test_uppercase_ticker_route_yields_to_dash_without_snapshot_lookup():
    with patch("codes.routes.analyze.get_company_snapshots_by_slug") as snapshots:
        response = _client_with_dash_shell().get("/analyze/META")

    assert response.status_code == 200
    assert response.get_data(as_text=True) == "dash shell for analyze/META"
    snapshots.assert_not_called()


def test_company_page_falls_back_to_dash_when_snapshot_database_is_unavailable():
    with patch(
        "codes.routes.analyze.get_company_snapshots_by_slug",
        side_effect=RuntimeError("database unavailable"),
    ):
        response = _client_with_dash_shell().get("/analyze/meta")

    assert response.status_code == 200
    assert response.get_data(as_text=True) == "dash shell for analyze/meta"


def test_company_slug_page_is_public_crawlable_and_shows_upgrade_without_private_data():
    with patch("codes.routes.analyze.get_company_snapshots_by_slug", return_value=[_official()]), \
         patch("codes.routes.analyze.auth.get_authenticated_user_id", return_value=None), \
         patch("codes.routes.analyze.list_custom_snapshots") as custom:
        response = _client().get("/analyze/apple")

    body = response.get_data(as_text=True)
    assert response.status_code == 200
    assert "Apple Inc. (AAPL)" in body
    assert "FactorResearch History" in body
    assert "/analyze/apple/2026-07-09" in body
    assert "Sign in and upgrade" in body
    assert 'rel="canonical" href="http://localhost/analyze/apple"' in body
    custom.assert_not_called()


def test_eligible_owner_sees_only_their_custom_history():
    allow = PermissionResult(True, Feature.BACKTEST, plan="premium", status="active")
    with patch("codes.routes.analyze.get_company_snapshots_by_slug", return_value=[_official()]), \
         patch("codes.routes.analyze.auth.get_authenticated_user_id", return_value="user-1"), \
         patch("codes.routes.analyze.permissions.can_access_feature", return_value=allow), \
         patch("codes.routes.analyze.list_custom_snapshots", return_value=[_custom()]) as listing:
        response = _client().get("/analyze/apple")

    assert response.status_code == 200
    assert "Durable Growth" in response.get_data(as_text=True)
    listing.assert_called_once_with("user-1", "AAPL", limit=12)


def test_slug_date_route_resolves_company_to_internal_ticker():
    with patch("codes.routes.analyze.get_company_snapshots_by_slug", return_value=[_official()]), \
         patch("codes.routes.analyze.get_snapshot", return_value=_official()) as lookup, \
         patch("codes.routes.analyze.list_ticker_snapshots", return_value=[_official()]), \
         patch("codes.routes.analyze.list_related_snapshots", return_value={}):
        response = _client().get("/analyze/apple/2026-07-09")

    assert response.status_code == 200
    assert 'rel="canonical" href="http://localhost/analyze/apple/2026-07-09"' in response.get_data(as_text=True)
    lookup.assert_called_once_with("AAPL", "20260709")


def test_custom_page_is_owner_scoped_and_noindex():
    allow = PermissionResult(True, Feature.BACKTEST, plan="premium", status="active")
    with patch("codes.routes.analyze.auth.get_authenticated_user_id", return_value="user-1"), \
         patch("codes.routes.analyze.permissions.can_access_feature", return_value=allow), \
         patch("codes.routes.analyze.get_custom_snapshot_for_owner", return_value=_custom()) as lookup:
        response = _client().get("/analyze/apple/custom/a8f4d2")

    assert response.status_code == 200
    assert response.headers["X-Robots-Tag"].startswith("noindex")
    assert 'name="robots" content="noindex,nofollow,noarchive"' in response.get_data(as_text=True)
    lookup.assert_called_once_with("a8f4d2", "user-1")


def test_other_users_custom_snapshot_returns_not_found():
    allow = PermissionResult(True, Feature.BACKTEST, plan="premium", status="active")
    with patch("codes.routes.analyze.auth.get_authenticated_user_id", return_value="user-2"), \
         patch("codes.routes.analyze.permissions.can_access_feature", return_value=allow), \
         patch("codes.routes.analyze.get_custom_snapshot_for_owner", return_value=None):
        response = _client().get("/analyze/apple/custom/a8f4d2")

    assert response.status_code == 404
