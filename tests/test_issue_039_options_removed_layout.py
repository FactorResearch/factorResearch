from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_factor_momentum_card_is_rendered_after_options_card_removal():
    source = (ROOT / "codes/app_modules/analysis_ui.py").read_text()
    layout_source = source.split("sections = [", 1)[1]

    assert "factor_momentum_card = _factor_momentum_card(data)" in source
    assert "children=[fcf_quality_card, factor_momentum_card]" in layout_source
    assert "children=[fcf_quality_card]" not in layout_source


def test_signals_section_keeps_two_card_pair_without_options_card():
    source = (ROOT / "codes/app_modules/analysis_ui.py").read_text()
    layout_source = source.split("sections = [", 1)[1]

    assert "children=[_insider_activity_card(data), alternative_data_card]" in layout_source
    assert "_options_signal_card(data)" not in layout_source
