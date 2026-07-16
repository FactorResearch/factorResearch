"""Map runtime display state to stylesheet classes without inline CSS."""

from __future__ import annotations

from .config import AMBER, BLUE, GREEN, MUTED, RED, TEXT


def tone_class(color: str | None) -> str:
    return {
        GREEN: "tone-positive",
        BLUE: "tone-info",
        AMBER: "tone-caution",
        RED: "tone-danger",
        MUTED: "tone-muted",
        TEXT: "tone-text",
        "#ff6d00": "tone-orange",
        "#f97316": "tone-orange",
    }.get(color, "tone-muted")
