"""Central financial formatting and meaning-preserving components."""

from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from enum import StrEnum

from dash import html

from .primitives import badge


class FinancialFormat(StrEnum):
    CURRENCY = "currency"
    PERCENT = "percent"
    RATIO = "ratio"
    MULTIPLE = "multiple"
    COMPACT = "compact"
    NUMBER = "number"


def _number(value) -> Decimal | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None


def format_financial(
    value,
    kind: FinancialFormat | str = FinancialFormat.NUMBER,
    *,
    decimals: int = 1,
    currency: str = "$",
) -> str:
    number = _number(value)
    if number is None:
        return "Not available"
    kind = FinancialFormat(kind)
    numeric = float(number)
    if kind == FinancialFormat.COMPACT:
        for divisor, suffix in ((1e12, "T"), (1e9, "B"), (1e6, "M"), (1e3, "K")):
            if abs(numeric) >= divisor:
                return f"{numeric / divisor:.{decimals}f}{suffix}"
    suffix = (
        "%" if kind == FinancialFormat.PERCENT else "×" if kind == FinancialFormat.MULTIPLE else ""
    )
    prefix = currency if kind == FinancialFormat.CURRENCY else ""
    return f"{prefix}{numeric:,.{decimals}f}{suffix}"


def score_badge(score, *, label: str = "Score"):
    numeric = float(_number(score) or 0)
    tone, word = (
        ("positive", "Strong")
        if numeric >= 70
        else ("warning", "Mixed")
        if numeric >= 40
        else ("danger", "Weak")
    )
    return badge(
        [html.Span(f"{label}: {numeric:.0f}"), html.Span(f" — {word}", className="sr-only")],
        tone=tone,
        **{"data-score": f"{numeric:.0f}"},
    )


def model_verdict(verdict: str | None):
    normalized = (verdict or "Unavailable").replace("_", " ").title()
    lower = normalized.lower()
    tone = (
        "positive"
        if any(word in lower for word in ("buy", "strong", "pass"))
        else "danger"
        if any(word in lower for word in ("avoid", "weak", "fail"))
        else "warning"
    )
    return badge(normalized, tone=tone, className="ds-verdict")


def metric_value(
    label: str,
    value,
    *,
    kind: FinancialFormat | str = FinancialFormat.NUMBER,
    decimals: int = 1,
    unit: str = "",
    hint: str = "",
):
    formatted = format_financial(value, kind, decimals=decimals)
    return html.Div(
        [
            html.Div(label, className="ds-metric__label"),
            html.Div(
                [formatted, html.Span(unit, className="ds-metric__unit")],
                className="ds-metric__value",
            ),
            html.Div(hint, className="ds-metric__hint") if hint else None,
        ],
        className="ds-metric",
    )


def delta(value, *, label: str = "Change"):
    numeric = float(_number(value) or 0)
    cue, tone = (
        ("▲", "positive") if numeric > 0 else ("▼", "danger") if numeric < 0 else ("●", "neutral")
    )
    return html.Span(
        [html.Span(cue, **{"aria-hidden": "true"}), f" {label} {numeric:+.1f}%"],
        className=f"ds-delta ds-delta--{tone}",
    )


def data_freshness(updated_at, *, source: str = ""):
    if not updated_at:
        return badge("Freshness unavailable", tone="warning")
    if isinstance(updated_at, str):
        try:
            updated_at = datetime.fromisoformat(updated_at.replace("Z", "+00:00"))
        except ValueError:
            return badge("Freshness unavailable", tone="warning")
    if updated_at.tzinfo is None:
        updated_at = updated_at.replace(tzinfo=timezone.utc)
    age_hours = max(0, (datetime.now(timezone.utc) - updated_at).total_seconds() / 3600)
    state, tone = ("Current", "positive") if age_hours <= 24 else ("Stale", "warning")
    source_text = f" · {source}" if source else ""
    return badge(f"{state} · {age_hours:.0f}h old{source_text}", tone=tone)


def missing_data(reason: str = "Data is not available"):
    return html.Span(
        [html.Span("—", **{"aria-hidden": "true"}), html.Span(reason, className="sr-only")],
        className="ds-missing",
    )
