from unittest.mock import Mock

from codes.services import waitlist


def test_subscribe_stores_email_sends_confirmation_and_marks_delivery(monkeypatch):
    monkeypatch.setattr(waitlist.db, "create_waitlist_signup", Mock(return_value=True))
    monkeypatch.setattr(waitlist.db, "mark_waitlist_confirmation_sent", Mock())
    monkeypatch.setattr(waitlist, "_send_confirmation", Mock())

    assert waitlist.subscribe(" Investor@Example.com ", "pre-a") == "confirmed"
    waitlist.db.create_waitlist_signup.assert_called_once_with("investor@example.com", "pre-a")
    waitlist._send_confirmation.assert_called_once_with("investor@example.com")
    waitlist.db.mark_waitlist_confirmation_sent.assert_called_once_with("investor@example.com")


def test_subscribe_does_not_resend_to_confirmed_email(monkeypatch):
    monkeypatch.setattr(waitlist.db, "create_waitlist_signup", Mock(return_value=False))
    monkeypatch.setattr(waitlist, "_send_confirmation", Mock())

    assert waitlist.subscribe("investor@example.com", "pre-a") == "already_confirmed"
    waitlist._send_confirmation.assert_not_called()
