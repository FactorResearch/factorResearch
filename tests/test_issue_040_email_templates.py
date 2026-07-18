from __future__ import annotations

import pytest

from codes.services.email_templates import render_email


@pytest.mark.parametrize(
    ("template_name", "context"),
    [
        ("waitlist_confirmation", {}),
        ("launch_announcement", {"message": "Access is now available."}),
        ("account_message", {"message": "Your account settings changed."}),
        ("feature_announcement", {"message": "Historical snapshots are here."}),
        ("maintenance_notice", {"message": "A short maintenance window is planned."}),
        ("incident_update", {"message": "The service is recovering.", "status": "Monitoring"}),
    ],
)
def test_all_issue_040_templates_render_html_and_plain_text(template_name, context):
    rendered = render_email(template_name, {"app_url": "https://example.com", **context})

    assert rendered.subject
    assert "{{" not in rendered.html
    assert "{%" not in rendered.html
    assert "{{" not in rendered.text
    assert rendered.html.startswith("<!doctype html>")
    assert "Cenvarn" in rendered.text


def test_template_context_is_html_escaped():
    rendered = render_email(
        "feature_announcement",
        {"message": "<script>alert('x')</script>"},
    )

    assert "<script>" not in rendered.html
    assert "&lt;script&gt;" in rendered.html


def test_unknown_template_is_rejected():
    with pytest.raises(ValueError, match="Unsupported email template"):
        render_email("password_reset")
