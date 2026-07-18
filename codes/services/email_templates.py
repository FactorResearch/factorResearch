"""Provider-independent branded email template rendering."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from jinja2 import Environment, FileSystemLoader, StrictUndefined, select_autoescape

_TEMPLATE_ROOT = Path(__file__).resolve().parents[1] / "templates" / "emails"
_SUBJECTS = {
    "waitlist_confirmation": "You're on the Cenvarn waitlist",
    "launch_announcement": "Cenvarn is ready",
    "account_message": "A message about your Cenvarn account",
    "feature_announcement": "What's new in Cenvarn",
    "maintenance_notice": "Cenvarn maintenance notice",
    "incident_update": "Cenvarn service update",
}


@dataclass(frozen=True)
class RenderedEmail:
    """Rendered email content ready for any delivery provider."""

    template_name: str
    subject: str
    html: str
    text: str


def _environment() -> Environment:
    """Create an autoescaping environment isolated from Flask request state."""
    return Environment(
        loader=FileSystemLoader(str(_TEMPLATE_ROOT)),
        autoescape=select_autoescape(("html", "xml")),
        undefined=StrictUndefined,
        trim_blocks=True,
        lstrip_blocks=True,
    )


def render_email(template_name: str, context: Mapping[str, Any] | None = None) -> RenderedEmail:
    """Render a branded HTML and plain-text email from an approved template.

    Args:
        template_name: Allowlisted template identifier without a file suffix.
        context: Template values. Text is passed as structured fields such as
            ``paragraphs`` and ``cta_url``; callers cannot inject unescaped HTML.

    Returns:
        A provider-neutral subject, HTML alternative, and plain-text body.

    Raises:
        ValueError: If template_name is not an approved email type.
        jinja2.UndefinedError: If a required template value is absent.
    """
    if template_name not in _SUBJECTS:
        raise ValueError(f"Unsupported email template: {template_name}")
    values = {
        "brand_name": "Cenvarn",
        "app_url": "",
        "cta_url": "",
        "cta_label": "Open Cenvarn",
        "unsubscribe_url": "",
        "first_name": "there",
        "maintenance_window": "",
        "status": "",
        "subject": _SUBJECTS[template_name],
        **dict(context or {}),
    }
    values["cta_url"] = values.get("cta_url") or values.get("app_url") or ""
    environment = _environment()
    return RenderedEmail(
        template_name=template_name,
        subject=str(values.get("subject") or _SUBJECTS[template_name]),
        html=environment.get_template(f"{template_name}.html").render(**values),
        text=environment.get_template(f"{template_name}.txt").render(**values),
    )
