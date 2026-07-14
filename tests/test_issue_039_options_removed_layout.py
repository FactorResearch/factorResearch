from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_factor_momentum_card_is_rendered_after_options_card_removal():
    source = (ROOT / "codes/app_modules/analysis_ui.py").read_text()
    layout_source = source.split("sections = [", 1)[1]

    assert "factor_momentum_card = _factor_momentum_card(data)" in source
    assert "children=[momentum_card, factor_momentum_card]" in layout_source


def test_signals_section_keeps_visible_cards_without_options_card():
    source = (ROOT / "codes/app_modules/analysis_ui.py").read_text()
    layout_source = source.split("sections = [", 1)[1]

    assert "insider_card" in layout_source
    assert "alternative_data_card" in layout_source
    assert "_options_signal_card(data)" not in layout_source
    assert "options_signal_model" not in (ROOT / "codes/app_modules/analysis.py").read_text()
