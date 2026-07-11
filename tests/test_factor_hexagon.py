from codes.app_modules import analysis_ui
from codes.app_modules.analysis_ui import _factor_hexagon
from urllib.parse import unquote


def test_factor_hexagon_has_six_labeled_axes_and_accessible_summary():
    factors = [("Composite", 72), ("Intrinsic", 80), ("Quality", 70), ("Momentum", 60), ("Safety", 90), ("Profit.", 65)]
    figure = _factor_hexagon(factors, "#00c853")
    image = figure.children[0]

    assert "Six-factor score profile" in image.alt
    assert "Safety 90" in image.alt
    assert image.src.startswith("data:image/svg+xml,")
    svg = unquote(image.src.split(",", 1)[1])
    assert 'filter id="hex-glow"' in svg
    assert 'x1="80" y1="180" x2="280" y2="180"' in svg
    assert 'paint-order="stroke"' in svg


def test_composite_trend_chart_reports_score_direction(monkeypatch):
    monkeypatch.setattr(analysis_ui.db, "list_composite_score_history", lambda _: [
        {"snapshot_date": "2026-07-01", "composite_score": 62.0, "verdict": "WATCH"},
        {"snapshot_date": "2026-07-10", "composite_score": 70.5, "verdict": "BUY"},
    ])

    chart = analysis_ui._composite_trend_chart("AAPL", "#1764bd")

    assert "Score trend ↑ 8.5 pts" in chart.children[0].children
