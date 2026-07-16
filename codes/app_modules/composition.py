"""Frontend composition root for the Dash shell and feature modules."""

from __future__ import annotations

from typing import Any

from codes.app_modules.analytics_context import FlaskAnalyticsContext
from codes.app_modules.layout import build_layout
from codes.services import product_analytics


def compose_dash_ui(app: Any, *, head_snippets: str = "") -> None:
    """Register feature callbacks and assemble the application presentation shell."""

    product_analytics.configure_context(FlaskAnalyticsContext())

    # Importing feature modules is their current callback-registration adapter.
    from codes.app_modules.tabs import (  # noqa: F401
        analyze,
        factor_lab,
        navigation,
        portfolio,
        pricing,
        profile,
        screener,
    )

    app.index_string = app.index_string.replace("<html>", '<html lang="en">')
    app.index_string = app.index_string.replace(
        "</head>",
        '<link rel="manifest" href="/manifest.webmanifest">'
        '<script>if("serviceWorker" in navigator){window.addEventListener("load",'
        '()=>navigator.serviceWorker.register("/service-worker.js"));}</script>'
        f"{head_snippets}</head>",
    )
    app.layout = build_layout()
    screener.register_clientside_callbacks(app)
