"""Waitlist persistence and SMTP confirmation delivery."""

from __future__ import annotations

import os
import smtplib
from email.message import EmailMessage

from codes.data import db
from codes.security import validate_email


class WaitlistEmailError(RuntimeError):
    pass


def _send_confirmation(email: str) -> None:
    host = os.environ.get("SMTP_HOST")
    sender = os.environ.get("SMTP_FROM_EMAIL")
    if not host or not sender:
        raise WaitlistEmailError("Waitlist email is not configured.")
    message = EmailMessage()
    message["Subject"] = "You're on the Research Factor waitlist"
    message["From"] = sender
    message["To"] = email
    message.set_content("You're on the Research Factor waitlist. We'll email you when we launch.\n\nThank you,\nResearch Factor")
    username = os.environ.get("SMTP_USERNAME")
    with smtplib.SMTP(host, int(os.environ.get("SMTP_PORT", "587")), timeout=10) as smtp:
        if os.environ.get("SMTP_USE_TLS", "true").lower() not in {"0", "false", "no"}:
            smtp.starttls()
        if username:
            smtp.login(username, os.environ.get("SMTP_PASSWORD", ""))
        smtp.send_message(message)


def subscribe(email: str, source: str) -> str:
    normalized = (email or "").strip().lower()
    if not validate_email(normalized):
        return "invalid"
    if not db.create_waitlist_signup(normalized, source):
        return "already_confirmed"
    try:
        _send_confirmation(normalized)
    except WaitlistEmailError:
        return "confirmed_no_email"
    db.mark_waitlist_confirmation_sent(normalized)
    return "confirmed"
