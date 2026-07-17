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


def test_waitlist_submission_captures_email_and_variant(monkeypatch):
    client = _client(monkeypatch)
    captured = {}

    def subscribe(email, source):
        captured.update(email=email, source=source)
        return "confirmed"

    monkeypatch.setattr("codes.landing_pages.waitlist.subscribe", subscribe)
    response = client.post("/landing/waitlist", data={"email": "investor@example.com", "variant": "pre-b"})

    assert response.status_code == 302
    assert response.headers["Location"].endswith("/landing/pre-b?waitlist=confirmed")
    assert captured == {"email": "investor@example.com", "source": "pre-b"}


def test_waitlist_submission_shows_success_when_email_confirmation_is_unavailable(monkeypatch):
    client = _client(monkeypatch)

    def subscribe(email, source):
        return "confirmed_no_email"

    monkeypatch.setattr("codes.landing_pages.waitlist.subscribe", subscribe)
    response = client.post("/landing/waitlist", data={"email": "investor@example.com", "variant": "pre-b"})

    assert response.status_code == 302
    assert response.headers["Location"].endswith("/landing/pre-b?waitlist=confirmed_no_email")

    page = client.get("/landing/pre-b?waitlist=confirmed_no_email")
    assert "You're on the list. Confirmation email is temporarily unavailable." in page.get_data(as_text=True)


def test_waitlist_submission_does_not_crash_when_backend_is_unavailable(monkeypatch):
    client = _client(monkeypatch)

    def subscribe(email, source):
        raise RuntimeError("DATABASE_USERS_URL is not set")

    monkeypatch.setattr("codes.landing_pages.waitlist.subscribe", subscribe)
    response = client.post("/landing/waitlist", data={"email": "investor@example.com", "variant": "pre-a"})

    assert response.status_code == 302
    assert response.headers["Location"].endswith("/landing/pre-a?waitlist=email_unavailable")


def test_pre_b_renders_app_like_preview_and_expect_panel(monkeypatch):
    response = _client(monkeypatch).get("/landing/pre-b")
    body = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "product-preview-analysis" in body
    assert "CenvarnAnalysis" in body
    assert "Composite Score" in body
    assert "Intrinsic Value" in body
    assert "<h2>What you can expect</h2>" in body
    assert "What you<br>can expect" not in body
    assert "◇" not in body
    assert "<style" not in body
    assert "style=" not in body
