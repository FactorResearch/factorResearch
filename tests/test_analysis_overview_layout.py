from pathlib import Path


def test_overview_layout_uses_a_single_desktop_summary_row():
    css = (Path(__file__).parents[1] / "assets" / "zz_analysis_overview_layout.css").read_text()

    assert "grid-template-columns: minmax(175px, 205px) minmax(290px, 360px) minmax(280px, 1fr)" in css
    assert ".company-identity-header .stats-row" in css
