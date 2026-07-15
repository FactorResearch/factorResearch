from datetime import date
from pathlib import Path
from unittest.mock import patch

import flask

from codes.models.analysis_snapshot import AnalysisSnapshot, CustomAnalysisSnapshot
from codes.routes.analyze import _theme_for, analyze_pages
from codes.app_modules.tabs.analyze import _ticker_from_analyze_path
from codes.services.permissions import Feature, PermissionResult


ROOT = Path(__file__).resolve().parents[1]


def _official():
    return AnalysisSnapshot(
        ticker="AAPL", company_name="Apple Inc.", analysis_date=date(2026, 7, 9),
        algorithm_version="standard-v1", valuation_score=81, quality_score=74,
        growth_score=69, momentum_score=62, risk_score=58,
        final_rating="HIGH CONVICTION", intrinsic_value=220, market_price=195,
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


def test_uppercase_ticker_route_renders_company_history_without_slug_lookup():
    with patch("codes.routes.analyze.list_ticker_snapshots", return_value=[_official()]) as history, \
         patch("codes.routes.analyze.get_company_snapshots_by_slug") as snapshots, \
         patch("codes.routes.analyze.auth.get_authenticated_user_id", return_value=None):
        response = _client_with_dash_shell().get("/AAPL")

    assert response.status_code == 200
    assert "FactorResearch History" in response.get_data(as_text=True)
    history.assert_called_once_with("AAPL", limit=12)
    snapshots.assert_not_called()


def test_dash_analysis_parser_accepts_bare_and_dated_ticker_urls():
    assert _ticker_from_analyze_path("/analyze/NVDA") == "NVDA"
    assert _ticker_from_analyze_path("/analyze/NVDA/") == "NVDA"
    assert _ticker_from_analyze_path("/analyze/NVDA/20260710") == "NVDA"
    assert _ticker_from_analyze_path("/analyze/nvda/2026-07-10") == "NVDA"


def test_ticker_page_bootstraps_first_snapshot_from_cached_official_analysis():
    cached = {"symbol": "AAPL", "name": "Apple Inc."}
    with patch("codes.routes.analyze.list_ticker_snapshots", side_effect=[[], [_official()]]) as history, \
         patch("codes.routes.analyze.db.get_analysis", return_value=cached), \
         patch("codes.routes.analyze.save_standard_snapshot") as save, \
         patch("codes.routes.analyze.auth.get_authenticated_user_id", return_value=None):
        response = _client().get("/AAPL/")

    assert response.status_code == 200
    assert "FactorResearch History" in response.get_data(as_text=True)
    save.assert_called_once_with(cached)
    assert history.call_count == 2


def test_company_page_falls_back_to_dash_when_snapshot_database_is_unavailable():
    with patch(
        "codes.routes.analyze.get_company_snapshots_by_slug",
        side_effect=RuntimeError("database unavailable"),
    ):
        response = _client_with_dash_shell().get("/analyze/meta")

    assert response.status_code == 200
    assert response.get_data(as_text=True) == "dash shell for analyze/meta"


def test_company_slug_page_is_public_crawlable_and_shows_upgrade_without_private_data():
    with patch("codes.routes.analyze.list_ticker_snapshots", return_value=[_official()]), \
         patch("codes.routes.analyze.auth.get_authenticated_user_id", return_value=None), \
         patch("codes.routes.analyze.list_custom_snapshots") as custom:
        response = _client().get("/AAPL")

    body = response.get_data(as_text=True)
    assert response.status_code == 200
    assert "Apple Inc." in body and "(AAPL)" in body
    assert "FactorResearch History" in body
    assert "/AAPL/analyze/20260709" in body
    assert 'href="/analyze/AAPL?tab=analyze">Analyze</a>' in body
    assert "Sign in and upgrade" in body
    assert 'rel="canonical" href="http://localhost/AAPL"' in body
    assert "FactorResearch company dossier" in body
    assert "Company Research" in body
    assert "non-proprietary design elements" in body
    assert 'localStorage.getItem("fr-theme")' in body
    assert 'href="/assets/company_analysis.css"' in body
    assert "<style" not in body
    assert "style=" not in body
    styles = (ROOT / "assets/company_analysis.css").read_text()
    assert "body {\n  display: flex;\n  flex-direction: column;" in styles
    assert "main {" in styles and "max-width: 1360px;" in styles
    assert ".footer {" in styles and "background: var(--surface);" in styles
    assert "html.light .footer" in styles
    assert "prefers-color-scheme: light" in body
    assert "Intrinsic Value" in body
    assert "Financial Health" in body
    assert "Stability Score" in body
    assert "Moat Rating" in body
    assert "Graham" not in body
    assert "Piotroski" not in body
    assert "Altman Z" not in body
    assert "Beneish" not in body
    assert "Ohlson" not in body
    custom.assert_not_called()


def test_compact_historical_ticker_url_opens_dash_analyze_tab():
    response = _client_with_dash_shell().get("/analyze/NVDA/20260710")
    assert response.status_code == 200
    assert response.get_data(as_text=True) == "dash shell for analyze/NVDA/20260710"


def test_hyphenated_historical_ticker_url_opens_dash_analyze_tab():
    response = _client_with_dash_shell().get("/analyze/NVDA/2026-07-10")
    assert response.status_code == 200
    assert response.get_data(as_text=True) == "dash shell for analyze/NVDA/2026-07-10"


def test_company_page_analyze_nav_query_opens_dash_analyze_tab():
    response = _client_with_dash_shell().get("/analyze/AAPL?tab=analyze")
    assert response.status_code == 200
    assert response.get_data(as_text=True) == "dash shell for analyze/AAPL"


def test_company_visual_tokens_are_distinct_without_logo_assets():
    apple = _official()
    meta = AnalysisSnapshot(
        **{**apple.__dict__, "ticker": "META", "company_name": "Meta Platforms Inc."}
    )
    assert _theme_for(apple) != _theme_for(meta)
    assert _theme_for(meta)["motif"] == "network"

    bank = AnalysisSnapshot(
        **{**apple.__dict__, "ticker": "ZZBK", "company_name": "Example Holdings", "sector": "Financial Services"}
    )
    software = AnalysisSnapshot(
        **{**apple.__dict__, "ticker": "ZZSW", "company_name": "Example Systems", "sector": "Software"}
    )
    assert _theme_for(bank)["motif"] == "finance"
    assert _theme_for(software)["motif"] == "platform"
    assert _theme_for(bank)["accent"] != _theme_for(software)["accent"]


def test_snapshot_uses_exact_enhanced_verdict_and_factor_values():
    result = {
        "symbol": "META",
        "name": "Meta Platforms Inc.",
        "sector": "Communication Services",
        "price": 500,
        "enhanced": {
            "composite_score": 35,
            "verdict": "CAUTION",
            "verdict_label": "caution",
            "verdict_desc": "Several important metrics warrant closer examination.",
            "graham_pct": 41,
            "quality_pct": 72,
            "growth_quality_pct": 63,
            "momentum_pct": 28,
            "risk_pct": 54,
            "profitability_pct": 68,
            "value_trap_warning": True,
        },
        "graham": {"total_score": 9, "total_max": 15},
        "quality": {"total_score": 10},
        "growth_quality": {"growth_quality_score": 11},
        "momentum": {"total_score": 12},
        "risk": {"risk_score": 13},
    }

    snapshot = AnalysisSnapshot.from_analysis_result(result)

    assert snapshot.final_rating == "CAUTION"
    assert snapshot.quality_score == 72
    assert snapshot.growth_score == 63
    assert snapshot.momentum_score == 28
    assert snapshot.risk_score == 54
    assert snapshot.official_metrics["graham_score"] == 41
    assert snapshot.official_metrics["profitability_score"] == 68
    assert snapshot.official_metrics["verdict_desc"] == result["enhanced"]["verdict_desc"]


def test_legacy_payload_fallback_uses_enhanced_verdict_table():
    snapshot = AnalysisSnapshot.from_analysis_result({
        "symbol": "META", "name": "Meta Platforms Inc.",
        "enhanced": {"composite_score": 35},
    })
    assert snapshot.final_rating == "CAUTION"


def test_eligible_owner_sees_only_their_custom_history():
    allow = PermissionResult(True, Feature.BACKTEST, plan="premium", status="active")
    with patch("codes.routes.analyze.list_ticker_snapshots", return_value=[_official()]), \
         patch("codes.routes.analyze.auth.get_authenticated_user_id", return_value="user-1"), \
         patch("codes.routes.analyze.permissions.can_access_feature", return_value=allow), \
         patch("codes.routes.analyze.list_custom_snapshots", return_value=[_custom()]) as listing:
        response = _client().get("/AAPL")

    assert response.status_code == 200
    assert "Durable Growth" in response.get_data(as_text=True)
    listing.assert_called_once_with("user-1", "AAPL", limit=12)


def test_slug_date_route_resolves_company_to_internal_ticker():
    with patch("codes.routes.analyze.get_company_snapshots_by_slug", return_value=[_official()]), \
         patch("codes.routes.analyze.get_snapshot", return_value=_official()) as lookup, \
         patch("codes.routes.analyze.list_ticker_snapshots", return_value=[_official()]), \
         patch("codes.routes.analyze.list_related_snapshots", return_value={}):
        response = _client().get("/analyze/apple/2026-07-09")

    assert response.status_code == 308
    assert response.headers["Location"] == "/AAPL/analyze/20260709"
    lookup.assert_called_once_with("AAPL", "20260709")


def test_legacy_company_route_redirects_to_ticker_home():
    with patch("codes.routes.analyze.get_company_snapshots_by_slug", return_value=[_official()]):
        response = _client().get("/analyze/apple?page=2")

    assert response.status_code == 308
    assert response.headers["Location"] == "/AAPL?page=2"


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
