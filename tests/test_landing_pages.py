from pathlib import Path

import flask

from codes.landing_pages import VARIANTS, register_landing_pages


def _client(monkeypatch):
    app = flask.Flask(__name__, template_folder=str(Path(__file__).parents[1] / "codes" / "templates"))
    app.secret_key = "test-secret"
    monkeypatch.setattr("codes.landing_pages.product_analytics.track_event", lambda *args, **kwargs: None)
    register_landing_pages(app)
    return app.test_client()


def test_each_landing_variant_renders(monkeypatch):
    client = _client(monkeypatch)
    for variant in VARIANTS:
        response = client.get(f"/landing/{variant}")
        assert response.status_code == 200
        assert b"Research Factor" in response.data


def test_ab_entry_assigns_and_persists_a_post_launch_variant(monkeypatch):
    client = _client(monkeypatch)
    first = client.get("/landing?phase=post")
    second = client.get("/landing?phase=post")

    assert first.status_code == second.status_code == 302
    assert first.headers["Location"] == second.headers["Location"]
    assert first.headers["Location"].endswith(("post-a", "post-b"))
