"""Typed, framework-neutral source of truth for visual design tokens."""

from dataclasses import dataclass
from types import MappingProxyType
from typing import Mapping


@dataclass(frozen=True)
class TokenGroup:
    name: str
    values: Mapping[str, str]

    def __post_init__(self) -> None:
        object.__setattr__(self, "values", MappingProxyType(dict(self.values)))


TOKEN_GROUPS = (
    TokenGroup(
        "color",
        {
            "surface-canvas": "#0f1b2d",
            "surface-base": "#15243a",
            "surface-raised": "#1c2e49",
            "surface-overlay": "#243955",
            "text-primary": "#f3f6fa",
            "text-muted": "#a9b5c7",
            "text-subtle": "#7f8da3",
            "border-default": "#40516a",
            "border-strong": "#60728d",
            "action-primary": "#4f9cf9",
            "action-primary-hover": "#78b4ff",
            "focus-ring": "#9dccff",
            "status-positive": "#54c59b",
            "status-warning": "#e2b85b",
            "status-danger": "#ef8178",
            "status-info": "#65b8d8",
            "chart-1": "#4f9cf9",
            "chart-2": "#54c59b",
            "chart-3": "#e2b85b",
            "chart-4": "#ba91e8",
            "chart-5": "#ef8178",
        },
    ),
    TokenGroup(
        "font",
        {
            "family-body": "'Manrope', 'Segoe UI', sans-serif",
            "family-numeric": "'IBM Plex Mono', monospace",
            "weight-regular": "400",
            "weight-medium": "500",
            "weight-bold": "700",
        },
    ),
    TokenGroup(
        "text",
        {
            "xs": "0.75rem",
            "sm": "0.875rem",
            "md": "1rem",
            "lg": "1.25rem",
            "xl": "1.75rem",
            "line-compact": "1.25",
            "line-body": "1.55",
        },
    ),
    TokenGroup(
        "space",
        {
            "0": "0",
            "1": "0.25rem",
            "2": "0.5rem",
            "3": "0.75rem",
            "4": "1rem",
            "5": "1.5rem",
            "6": "2rem",
            "section": "2.5rem",
        },
    ),
    TokenGroup("border", {"thin": "1px", "strong": "2px"}),
    TokenGroup("radius", {"sm": "0.25rem", "md": "0.5rem", "lg": "0.75rem", "pill": "999px"}),
    TokenGroup(
        "shadow",
        {
            "sm": "0 4px 12px rgba(0,0,0,.18)",
            "md": "0 12px 30px rgba(0,0,0,.24)",
            "lg": "0 24px 60px rgba(0,0,0,.32)",
        },
    ),
    TokenGroup(
        "layer", {"base": "0", "sticky": "20", "dropdown": "40", "overlay": "60", "toast": "80"}
    ),
    TokenGroup("breakpoint", {"sm": "36rem", "md": "48rem", "lg": "72rem"}),
    TokenGroup("container", {"reading": "52rem", "content": "76rem", "wide": "96rem"}),
    TokenGroup(
        "motion",
        {
            "fast": "120ms",
            "normal": "200ms",
            "slow": "360ms",
            "ease": "cubic-bezier(.2,.8,.2,1)",
            "reduced": "1ms",
        },
    ),
    TokenGroup("density", {"compact": "0.75", "comfortable": "1", "spacious": "1.25"}),
    TokenGroup("target", {"minimum": "44px"}),
    TokenGroup("chart", {"height-sm": "16rem", "height-md": "24rem", "height-lg": "32rem"}),
    TokenGroup("table", {"row-compact": "2.25rem", "row-default": "2.75rem"}),
)

LIGHT_OVERRIDES = {
    "color-surface-canvas": "#f4efe7",
    "color-surface-base": "#fbf7f1",
    "color-surface-raised": "#fffdfa",
    "color-surface-overlay": "#ffffff",
    "color-text-primary": "#1c2736",
    "color-text-muted": "#5b6776",
    "color-text-subtle": "#718093",
    "color-border-default": "#d6cbbd",
    "color-border-strong": "#a89d90",
    "color-action-primary": "#174b7f",
    "color-action-primary-hover": "#0c345f",
    "color-focus-ring": "#174b7f",
    "color-status-positive": "#215f4d",
    "color-status-warning": "#7a5818",
    "color-status-danger": "#9a3e37",
    "color-status-info": "#255f98",
}


def token_map() -> dict[str, str]:
    return {
        f"{group.name}-{name}": value
        for group in TOKEN_GROUPS
        for name, value in group.values.items()
    }


def css_variable(name: str) -> str:
    if name not in token_map():
        raise KeyError(f"Unknown design token: {name}")
    return f"var(--fr-{name})"
