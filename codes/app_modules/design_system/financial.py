"""Central financial formatting and meaning-preserving components."""

from datetime import UTC, datetime
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


def format_financial_spoken(
    value,
    kind: FinancialFormat | str = FinancialFormat.NUMBER,
    *,
    decimals: int = 1,
    currency: str = "$",
) -> str:
    """Spell out financial signs and units for assistive technology."""
    number = _number(value)
    if number is None:
        return "Not available"
    kind = FinancialFormat(kind)
    numeric = float(number)
    sign = "negative " if numeric < 0 else ""
    magnitude = f"{abs(numeric):,.{decimals}f}"
    if kind == FinancialFormat.CURRENCY:
        unit = "US dollars" if currency == "$" else f"{currency} currency units"
        return f"{sign}{magnitude} {unit}"
    if kind == FinancialFormat.PERCENT:
        return f"{sign}{magnitude} percent"
    if kind == FinancialFormat.MULTIPLE:
        return f"{sign}{magnitude} times"
    if kind == FinancialFormat.RATIO:
        return f"{sign}{magnitude} ratio"
    return f"{sign}{magnitude}"


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
    spoken = format_financial_spoken(value, kind, decimals=decimals)
    return html.Div(
        [
            html.Div(label, className="ds-metric__label"),
            html.Div(
                [
                    html.Span(
                        [formatted, html.Span(unit, className="ds-metric__unit")],
                        **{"aria-hidden": "true"},
                    ),
                    html.Span(f"{label}: {spoken}{f' {unit}' if unit else ''}", className="sr-only"),
                ],
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
        [
            html.Span(f"{cue} {label} {numeric:+.1f}%", **{"aria-hidden": "true"}),
            html.Span(
                f"{label}: {'negative ' if numeric < 0 else 'positive ' if numeric > 0 else ''}{abs(numeric):.1f} percent",
                className="sr-only",
            ),
        ],
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
        updated_at = updated_at.replace(tzinfo=UTC)
    age_hours = max(0, (datetime.now(UTC) - updated_at).total_seconds() / 3600)
    state, tone = ("Current", "positive") if age_hours <= 24 else ("Stale", "warning")
    source_text = f" · {source}" if source else ""
    return badge(f"{state} · {age_hours:.0f}h old{source_text}", tone=tone)


def missing_data(reason: str = "Data is not available"):
    return html.Span(
        [html.Span("—", **{"aria-hidden": "true"}), html.Span(reason, className="sr-only")],
        className="ds-missing",
    )


def methodology_disclosure(
    model_name: str,
    *,
    summary: str,
    limitations: str,
):
    """Keep methodology and limitations reachable at the point of use."""
    return html.Details(
        className="ds-methodology",
        children=[
            html.Summary(f"{model_name} methodology and limitations"),
            html.P(summary),
            html.P([html.Strong("Limitations: "), limitations]),
        ],
    )


def data_trust_panel(data: dict | None, *, compact: bool = False):
    """Render explicit provenance without implying undocumented confidence."""
    analysis = data or {}
    provenance = analysis.get("provenance") or {}
    generated = provenance.get("analysis_date") or analysis.get("generated_at") or analysis.get("updated_at")
    reporting_period = provenance.get("filing_period") or "Not available"
    source = provenance.get("source_category") or "Source category unavailable"
    currency = provenance.get("currency") or analysis.get("currency") or "Not available"
    normalization = provenance.get("normalization_status") or "Normalization status unavailable"
    calculation = provenance.get("calculation_status") or (
        "cached" if analysis.get("cache_hit") else "newly calculated"
    )
    price_time = provenance.get("price_timestamp") or "Quote timestamp unavailable"
    model_scope = provenance.get("model_scope") or "Cenvarn default models"
    effects = list(provenance.get("missing_effects") or [])
    if analysis.get("secondary_status") == "failed":
        effects.append("Optional sources failed; their signals are excluded from the displayed support.")
    historical = bool(provenance.get("historical") or analysis.get("cache_stale"))
    custom = bool(provenance.get("custom_model"))

    rows = [
        ("Analysis date", _format_trust_date(generated)),
        ("Market price", price_time),
        ("Reporting period", str(reporting_period)),
        ("Source", str(source)),
        ("Currency", str(currency)),
        ("Normalization", str(normalization)),
        ("Calculation", str(calculation)),
        ("Model", str(model_scope)),
    ]
    state_labels = []
    if historical:
        state_labels.append(badge("Historical snapshot", tone="warning"))
    if custom:
        state_labels.append(badge("User-customized model", tone="neutral"))
    if effects:
        state_labels.append(badge("Partial inputs", tone="warning"))

    return html.Section(
        className="ds-trust-panel" + (" ds-trust-panel--compact" if compact else ""),
        **{"aria-label": "Data trust and provenance", "data-trust-state": "partial" if effects else "supported"},
        children=[
            html.Div([
                html.H3("Data trust", className="ds-trust-panel__title"),
                html.Div(state_labels, className="ds-trust-panel__states"),
            ], className="ds-trust-panel__header"),
            html.Dl([
                html.Div([html.Dt(label), html.Dd(value)], className="ds-trust-panel__item")
                for label, value in rows
            ], className="ds-trust-panel__grid"),
            html.Div(
                [html.Strong("Missing-data effects: "), html.Ul([html.Li(effect) for effect in effects])],
                className="ds-trust-panel__effects",
                role="alert",
            ) if effects else html.P(
                "No known missing input changes the displayed calculation scope.",
                className="ds-trust-panel__effects",
            ),
            html.P(
                "Scores are research estimates based on available inputs, not guarantees or personalized financial advice.",
                className="ds-trust-panel__disclaimer",
            ),
        ],
    )


def _format_trust_date(value) -> str:
    if not value:
        return "Not available"
    if isinstance(value, str):
        try:
            value = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return value[:32]
    if isinstance(value, datetime):
        if value.tzinfo is None:
            value = value.replace(tzinfo=UTC)
        return value.astimezone(UTC).strftime("%Y-%m-%d %H:%M UTC")
    return str(value)[:32]
