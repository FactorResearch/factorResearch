from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_light_theme_defines_semantic_surface_text_and_status_tokens():
    tokens = (ROOT / "assets/style/_tokens.scss").read_text()
    assert "body.light" in tokens
    for token in ("--fr-bg", "--fr-surface", "--fr-text", "--fr-text-muted", "--fr-positive", "--fr-danger"):
        assert token in tokens


def test_analysis_uses_semantic_tone_classes_and_company_link():
    css = (ROOT / "assets/style.css").read_text()
    source = (ROOT / "codes/app_modules/analysis_ui.py").read_text()
    assert ".tone-positive" in css
    assert 'href=f"/analyze/{symbol}/"' in source
    assert 'className="company-title-link"' in source
