from pathlib import Path

from codes.app_modules.layout import build_layout


ROOT = Path(__file__).resolve().parents[1]


def _find_by_id(component, target_id):
    if getattr(component, "id", None) == target_id:
        return component
    children = getattr(component, "children", None)
    if children is None:
        return None
    if not isinstance(children, (list, tuple)):
        children = [children]
    for child in children:
        found = _find_by_id(child, target_id)
        if found is not None:
            return found
    return None


def _collect_hrefs(component):
    hrefs = []
    href = getattr(component, "href", None)
    if href:
        hrefs.append(href)
    children = getattr(component, "children", None)
    if children is None:
        return hrefs
    if not isinstance(children, (list, tuple)):
        children = [children]
    for child in children:
        hrefs.extend(_collect_hrefs(child))
    return hrefs


def test_footer_legal_links_open_in_app_modals():
    layout = build_layout()
    hrefs = _collect_hrefs(layout)

    assert "#legal-terms" in hrefs
    assert "#legal-privacy" in hrefs
    assert _find_by_id(layout, "legal-terms") is not None
    assert _find_by_id(layout, "legal-privacy") is not None

    terms_modal = _find_by_id(layout, "legal-terms")
    assert "legal-modal-fullscreen" in str(terms_modal)


def test_legal_pages_have_real_content_and_external_assets():
    terms = (ROOT / "codes/templates/terms.html").read_text()
    privacy = (ROOT / "codes/templates/privacy.html").read_text()

    assert "PLACEHOLDER" not in terms + privacy
    assert "[placeholder" not in terms + privacy
    assert "No Investment Advice" in terms
    assert "Accuracy of Information" in terms
    assert "Information We Collect" in privacy
    assert "Retention and Deletion" in privacy
    assert '<link rel="stylesheet" href="/assets/legal_pages.css">' in terms
    assert '<link rel="stylesheet" href="/assets/legal_pages.css">' in privacy
    assert '<script src="/assets/legal_pages.js"></script>' in privacy
    assert "<style" not in terms + privacy
    assert "style=" not in terms + privacy
    assert "(function" not in privacy


def test_methodology_page_uses_public_methodology_source():
    methodology = (ROOT / "codes/templates/methodology.html").read_text()

    assert "Transparent. Auditable. Deterministic." in methodology
    assert "Data Sources" in methodology
    assert "Composite Score" in methodology


def test_legal_modal_css_supports_popup_and_full_page_feel():
    css = (ROOT / "assets/legal_pages.css").read_text()

    assert ".legal-modal-overlay:target" in css
    assert "max-height: min(82vh, 760px);" in css
    assert ".legal-modal-primary" in css
    assert "body.light .legal-modal-card" in css
