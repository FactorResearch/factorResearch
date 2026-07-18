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
        assert b"Cenvarn" in response.data


def test_landing_entry_uses_pre_b_without_ab_assignment(monkeypatch):
    client = _client(monkeypatch)
    first = client.get("/landing")
    second = client.get("/landing?phase=pre")

    assert first.status_code == second.status_code == 302
    assert first.headers["Location"].endswith("/landing/pre-b")
    assert second.headers["Location"].endswith("/landing/pre-b")


def test_pre_a_is_retired(monkeypatch):
    client = _client(monkeypatch)

    assert client.get("/landing/pre-a").status_code == 404
    assert client.post(
        "/landing/waitlist",
        data={"email": "investor@example.com", "variant": "pre-a"},
    ).status_code == 400


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
    response = client.post("/landing/waitlist", data={"email": "investor@example.com", "variant": "pre-b"})

    assert response.status_code == 302
    assert response.headers["Location"].endswith("/landing/pre-b?waitlist=email_unavailable")


def test_pre_b_renders_app_like_preview_and_expect_panel(monkeypatch):
    response = _client(monkeypatch).get("/landing/pre-b")
    body = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "Join the Founding Waitlist" in body
    assert "Get early access" in body
    assert "Why Cenvarn?" not in body
    assert "Great investing isn't about predicting the future." not in body
    assert "<style" not in body
    assert "style=" not in body


def test_pre_b_footer_opens_all_legal_content_as_popups(monkeypatch):
    body = _client(monkeypatch).get("/landing/pre-b").get_data(as_text=True)

    for modal_id in ("legal-methodology", "legal-privacy", "legal-terms"):
        assert f'id="{modal_id}"' in body
    assert 'href="#legal-methodology"' in body
    assert 'data-legal-fullscreen="true"' in body


def test_pre_b_short_viewport_reserves_space_for_footer():
    css = (Path(__file__).parents[1] / "assets" / "landing_pre.css").read_text()

    assert "height: calc(100svh - 56px - 48px);" in css
    assert "min-height: 640px" not in css
    assert "position: absolute !important" in css
