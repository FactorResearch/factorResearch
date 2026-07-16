#!/usr/bin/env python3
"""Standalone local workshop for browser accessibility and visual checks."""

from dash import Dash
from pathlib import Path

from codes.app_modules.design_system.catalogue import build_catalogue

app = Dash(
    __name__,
    title="Factor Research design system",
    assets_folder=str(Path(__file__).resolve().parents[1] / "assets"),
    assets_ignore=r"^(?!(style\.css|adaptive_loading\.js|design_system\.js)$).*",
)
app.layout = build_catalogue()
server = app.server


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=8056, debug=False)
