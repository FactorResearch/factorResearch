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
    assert 'x1="58" y1="150" x2="242" y2="150"' in svg
    assert 'paint-order="stroke"' in svg
