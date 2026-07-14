"""Reusable company logo with a dependency-free monogram fallback."""

import os
from urllib.parse import urlencode

from dash import html
from dotenv import load_dotenv

load_dotenv()


def logo_provider_enabled() -> bool:
    return bool(os.environ.get("LOGO_DEV_PUBLISHABLE_KEY", "").strip())


def company_logo(symbol: str, name: str = "", class_name: str = "company-logo"):
    symbol = (symbol or "?").strip().upper()
    label = (name or symbol).strip()
    token = os.environ.get("LOGO_DEV_PUBLISHABLE_KEY", "").strip()
    if token:
        src = f"/company-logo?{urlencode({'symbol': symbol, 'name': label})}"
        return html.Img(src=src, alt=f"{label} logo", className=class_name)
    return html.Span(symbol[:2], className=f"{class_name} company-logo--fallback", **{"aria-label": f"{label} monogram"})


def logo_attribution():
    if not logo_provider_enabled():
        return None
    return html.Span([
        html.Span(" · "),
        html.A("Logos provided by Logo.dev", href="https://logo.dev", target="_blank", className="clr-muted"),
    ])
