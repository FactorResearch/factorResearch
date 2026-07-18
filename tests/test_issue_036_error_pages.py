from pathlib import Path

import flask

from codes.error_pages import register_error_pages


ROOT = Path(__file__).resolve().parents[1]


def _client():
    app = flask.Flask(__name__, template_folder=str(ROOT / "codes/templates"))
    app.secret_key = "test"
    register_error_pages(app)

    @app.route("/abort/<int:status_code>")
    def abort_status(status_code):
        flask.abort(status_code)

    @app.route("/explode")
    def explode():
        raise RuntimeError("database secret should not render")

    return app.test_client()


def test_error_pages_exist_for_required_status_codes():
    for status_code in (400, 401, 403, 404, 500):
        assert (ROOT / f"codes/templates/errors/{status_code}.html").exists()


def test_error_pages_use_external_css_and_no_inline_styles():
    for status_code in (400, 401, 403, 404):
        response = _client().get(f"/abort/{status_code}")
        body = response.get_data(as_text=True)

        assert response.status_code == status_code
        assert f'<body class="error-page error-page-{status_code}">' in body
        assert 'href="/assets/error_pages.css"' in body
        assert "<style" not in body
        assert "style=" not in body
        assert "Cenvarn" in body
        assert f">{status_code}<" in body


def test_unhandled_exception_uses_generic_500_page():
    response = _client().get("/explode")
    body = response.get_data(as_text=True)

    assert response.status_code == 500
    assert '<body class="error-page error-page-500">' in body
    assert "The research engine hit an unexpected error." in body
    assert "database secret should not render" not in body


def test_error_page_stylesheet_is_external_asset():
    css = (ROOT / "assets/error_pages.css").read_text()

    assert ".error-card" in css
    assert "body.error-page" in css
    assert "html.light body.error-page" in css


def test_touched_flask_templates_do_not_use_inline_css():
    template_paths = [
        ROOT / "codes/templates/terms.html",
        ROOT / "codes/templates/privacy.html",
        *sorted((ROOT / "codes/templates/errors").glob("*.html")),
    ]

    for path in template_paths:
        body = path.read_text()
        assert "<style" not in body
        assert "style=" not in body
