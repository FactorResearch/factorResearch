from codes.app_modules.analysis_ui import _factor_hexagon


def test_factor_hexagon_has_six_labeled_axes_and_accessible_summary():
    factors = [("Composite", 72), ("Intrinsic", 80), ("Quality", 70), ("Momentum", 60), ("Safety", 90), ("Profit.", 65)]
    figure = _factor_hexagon(factors, "#00c853")
    image = figure.children[0]

    assert "Six-factor score profile" in image.alt
    assert "Safety 90" in image.alt
    assert image.src.startswith("data:image/svg+xml,")
