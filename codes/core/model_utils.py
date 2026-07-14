"""Shared model utility helpers.

These helpers are intentionally small and dependency-light. They centralize
common validation and normalization behavior without changing existing model
output schemas.
"""

from __future__ import annotations

import math
from typing import Any


def safe_float(value: Any, fallback: float | None = None) -> float | None:
    """Return a finite float or fallback."""
    try:
        number = float(value)
    except (TypeError, ValueError):
        return fallback
    return number if math.isfinite(number) else fallback


def clamp(value: float, low: float = 0.0, high: float = 100.0) -> float:
    """Clamp a numeric value to inclusive bounds."""
    return max(low, min(high, float(value)))


def first_record_value(records: list, *, field: str = "value") -> float | None:
    """Return the first finite numeric field value from records."""
    for record in records or []:
        if not isinstance(record, dict):
            continue
        value = safe_float(record.get(field))
        if value is not None:
            return value
    return None


def record_values(records: list, *, field: str = "value", limit: int | None = None) -> list[float]:
    """Return finite numeric values from records, preserving order."""
    values: list[float] = []
    for record in records or []:
        if not isinstance(record, dict):
            continue
        value = safe_float(record.get(field))
        if value is not None:
            values.append(value)
            if limit is not None and len(values) >= limit:
                break
    return values


def records_by_year(records: list, *, field: str = "value") -> dict[int, float]:
    """Return {year: value} for records with finite year and value."""
    output: dict[int, float] = {}
    for record in records or []:
        if not isinstance(record, dict):
            continue
        year = safe_float(record.get("year"))
        value = safe_float(record.get(field))
        if year is not None and value is not None:
            output[int(year)] = value
    return output


def percent_change(old: Any, new: Any) -> float | None:
    """Percentage change using abs(old) in the denominator."""
    old_value = safe_float(old)
    new_value = safe_float(new)
    if old_value is None or new_value is None or abs(old_value) < 1e-10:
        return None
    return (new_value - old_value) / abs(old_value) * 100.0


def linear_slope_percent(values: list) -> float | None:
    """OLS slope of a sequence, normalized by absolute mean, in percent."""
    numeric = [value for value in (safe_float(item) for item in values or []) if value is not None]
    n = len(numeric)
    if n < 2:
        return None
    mean_value = sum(numeric) / n
    if abs(mean_value) < 1e-10:
        return None
    x_mean = (n - 1) / 2.0
    numerator = sum((index - x_mean) * (value - mean_value) for index, value in enumerate(numeric))
    denominator = sum((index - x_mean) ** 2 for index in range(n))
    if denominator < 1e-10:
        return None
    return (numerator / denominator) / abs(mean_value) * 100.0


def score_from_criteria(criteria: list[dict]) -> tuple[float, float]:
    """Return total score and max score from criteria dictionaries."""
    total = sum(safe_float(item.get("score"), 0.0) or 0.0 for item in criteria or [])
    total_max = sum(safe_float(item.get("max"), 0.0) or 0.0 for item in criteria or [])
    return total, total_max
