"""Typed, framework-neutral source of truth for visual design tokens."""

from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType


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
            # Dark theme — canonical default, matched to the approved prototype.
            "surface-canvas": "#090d0b",
            "surface-base": "#101612",
            "surface-raised": "#141c17",
            "surface-overlay": "#1a241e",
            "text-primary": "#edf4ef",
            "text-muted": "#91a097",
            "text-subtle": "#68756d",
            "border-default": "#253229",
            "border-strong": "#34433a",
            "action-primary": "#39b873",
            "action-primary-hover": "#55ce8a",
            "focus-ring": "#39b873",
            "action-primary-soft": "#12291d",
            "status-positive": "#39b873",
            "status-positive-soft": "#12291d",
            "status-warning": "#e8af45",
            "status-warning-soft": "#332713",
            "status-danger": "#ef6b70",
            "status-danger-soft": "#32191b",
            "status-info": "#2f66dd",
            "chart-1": "#2f66dd",
            "chart-2": "#2cbc55",
            "chart-3": "#d8a322",
            "chart-4": "#8739c9",
            "chart-5": "#ef6b70",
        },
    ),
    TokenGroup(
        "font",
        {
            "family-body": (
                "'Inter', ui-sans-serif, system-ui, -apple-system, "
                "BlinkMacSystemFont, 'Segoe UI', sans-serif"
            ),
            "family-numeric": (
                "'Inter', ui-sans-serif, system-ui, -apple-system, "
                "BlinkMacSystemFont, 'Segoe UI', sans-serif"
            ),
            "weight-regular": "400",
            "weight-medium": "500",
            "weight-semibold": "650",
            "weight-bold": "750",
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
    TokenGroup(
        "radius",
        {
            "sm": "9px",
            "md": "10px",
            "lg": "14px",
            "pill": "999px",
        },
    ),
    TokenGroup(
        "shadow",
        {
            "sm": "0 4px 12px rgba(0, 0, 0, 0.18)",
            "md": "0 10px 30px rgba(0, 0, 0, 0.26)",
            "lg": "0 24px 60px rgba(0, 0, 0, 0.32)",
        },
    ),
    TokenGroup(
        "layer",
        {
            "base": "0",
            "sticky": "20",
            "dropdown": "40",
            "overlay": "60",
            "toast": "80",
        },
    ),
    TokenGroup(
        "breakpoint",
        {
            "sm": "36rem",
            "md": "48rem",
            "lg": "72rem",
        },
    ),
    TokenGroup(
        "container",
        {
            "reading": "52rem",
            "content": "76rem",
            "wide": "96rem",
        },
    ),
    TokenGroup(
        "motion",
        {
            "fast": "120ms",
            "normal": "200ms",
            "slow": "360ms",
            "ease": "cubic-bezier(.2, .8, .2, 1)",
            "reduced": "1ms",
        },
    ),
    TokenGroup(
        "density",
        {
            "compact": "0.75",
            "comfortable": "1",
            "spacious": "1.25",
        },
    ),
    TokenGroup("target", {"minimum": "44px"}),
    TokenGroup(
        "chart",
        {
            "height-sm": "16rem",
            "height-md": "24rem",
            "height-lg": "32rem",
        },
    ),
    TokenGroup(
        "table",
        {
            "row-compact": "2.25rem",
            "row-default": "2.75rem",
        },
    ),
)


LIGHT_OVERRIDES = MappingProxyType(
    {
        "color-surface-canvas": "#f5f7f8",
        "color-surface-base": "#ffffff",
        "color-surface-raised": "#f8faf9",
        "color-surface-overlay": "#eef3f0",
        "color-text-primary": "#152019",
        "color-text-muted": "#68756d",
        "color-text-subtle": "#7f8d84",
        "color-border-default": "#dce5df",
        "color-border-strong": "#cbd7cf",
        "color-action-primary": "#16834c",
        "color-action-primary-hover": "#0e683b",
        "color-focus-ring": "#16834c",
        "color-action-primary-soft": "#e7f5ed",
        "color-status-positive": "#16834c",
        "color-status-positive-soft": "#e7f5ed",
        "color-status-warning": "#b77910",
        "color-status-warning-soft": "#fff3d8",
        "color-status-danger": "#c33d42",
        "color-status-danger-soft": "#fae9ea",
        "color-status-info": "#2f66dd",
        "color-chart-1": "#2f66dd",
        "color-chart-2": "#2cbc55",
        "color-chart-3": "#d8a322",
        "color-chart-4": "#8739c9",
        "color-chart-5": "#c33d42",
    }
)


def token_map() -> dict[str, str]:
    """Return all canonical design tokens as a flat mapping."""
    return {
        f"{group.name}-{name}": value
        for group in TOKEN_GROUPS
        for name, value in group.values.items()
    }


def theme_token_map(theme: str = "dark") -> dict[str, str]:
    """Return the flattened token map with the selected theme applied."""
    tokens = token_map()

    if theme == "dark":
        return tokens

    if theme == "light":
        tokens.update(LIGHT_OVERRIDES)
        return tokens

    raise ValueError(f"Unsupported theme: {theme!r}. Expected 'dark' or 'light'.")


def css_variable(name: str) -> str:
    """Return the CSS custom-property reference for a known token."""
    if name not in token_map():
        raise KeyError(f"Unknown design token: {name}")

    return f"var(--fr-{name})"