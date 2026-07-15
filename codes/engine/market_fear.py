"""Market Fear Gauge based on VIX and VIXEQ.

This module is informational only. It must not alter valuation, stock scores,
rankings, or portfolio sizing.
"""

from __future__ import annotations

from statistics import mean, stdev
from typing import Iterable

from codes.core import model_utils as mu


VERY_LOW_FEAR = "VERY_LOW_FEAR"
NORMAL = "NORMAL"
ELEVATED = "ELEVATED"
HIGH = "HIGH"
EXTREME = "EXTREME"

_REGIME_META = {
    VERY_LOW_FEAR: {
        "badge": "Low Market Fear",
        "color": "green",
        "score": 10.0,
        "interpretation": (
            "Market participants are generally optimistic. High-quality "
            "businesses may continue performing well, but broad undervaluation "
            "is less common. Continue demanding a strong margin of safety."
        ),
    },
    NORMAL: {
        "badge": "Normal Market Conditions",
        "color": "blue",
        "score": 35.0,
        "interpretation": (
            "Market sentiment is balanced. Continue evaluating businesses "
            "solely on intrinsic value."
        ),
    },
    ELEVATED: {
        "badge": "Elevated Market Fear",
        "color": "amber",
        "score": 60.0,
        "interpretation": (
            "Investors are becoming increasingly defensive. Volatility may "
            "create additional buying opportunities if prices fall faster than "
            "intrinsic value. Consider monitoring watchlists closely."
        ),
    },
    HIGH: {
        "badge": "High Market Fear",
        "color": "orange",
        "score": 80.0,
        "interpretation": (
            "Fear is spreading across the broader market. Many businesses may "
            "begin trading closer to or below intrinsic value. This environment "
            "deserves increased research activity."
        ),
    },
    EXTREME: {
        "badge": "Extreme Market Fear",
        "color": "red",
        "score": 95.0,
        "interpretation": (
            "Market stress is unusually high. Historically these periods have "
            "often produced exceptional long-term buying opportunities for "
            "financially strong businesses, while still requiring caution."
        ),
    },
}


def _safe_float(value) -> float | None:
    v = mu.safe_float(value)
    return v if v is not None and v > 0 else None


def _spread_stats(spread_history: Iterable[float] | None) -> tuple[float | None, float | None]:
    if not spread_history:
        return None, None
    vals = []
    for item in spread_history:
        v = _safe_float(item)
        if v is not None:
            vals.append(v)
    if len(vals) < 60:
        return None, None
    sigma = stdev(vals)
    if sigma <= 0:
        return mean(vals), None
    return mean(vals), sigma


def _classify(vix: float, spread: float, ratio: float, z_score: float | None) -> str:
    if z_score is not None:
        if vix < 15 and z_score <= -0.50:
            return VERY_LOW_FEAR
        if z_score < 0.75:
            return NORMAL
        if z_score < 1.25:
            return ELEVATED
        if z_score < 2.00:
            return HIGH
        return EXTREME

    if vix < 15 and spread <= 1.5 and ratio <= 1.08:
        return VERY_LOW_FEAR
    if spread <= 3.0 and ratio <= 1.15:
        return NORMAL
    if spread <= 5.0 and ratio <= 1.30:
        return ELEVATED
    if spread <= 8.0 and ratio <= 1.50:
        return HIGH
    return EXTREME


def analyze(vix, vixeq, spread_history: Iterable[float] | None = None) -> dict:
    """Return a display-ready Market Fear Gauge result."""
    vix_val = _safe_float(vix)
    vixeq_val = _safe_float(vixeq)
    if vix_val is None or vixeq_val is None:
        return {
            "vix": vix_val,
            "vixeq": vixeq_val,
            "spread": None,
            "ratio": None,
            "spread_mean_252d": None,
            "spread_std_252d": None,
            "z_score": None,
            "regime": None,
            "badge": None,
            "color": None,
            "market_fear_score": None,
            "interpretation": None,
            "error": "VIX and VIXEQ readings are required",
        }

    spread = vixeq_val - vix_val
    ratio = vixeq_val / vix_val
    spread_mean, spread_std = _spread_stats(spread_history)
    z_score = None
    if spread_mean is not None and spread_std is not None:
        z_score = (spread - spread_mean) / spread_std

    regime = _classify(vix_val, spread, ratio, z_score)
    meta = _REGIME_META[regime]

    return {
        "vix": round(vix_val, 2),
        "vixeq": round(vixeq_val, 2),
        "spread": round(spread, 2),
        "ratio": round(ratio, 3),
        "spread_mean_252d": round(spread_mean, 2) if spread_mean is not None else None,
        "spread_std_252d": round(spread_std, 2) if spread_std is not None else None,
        "z_score": round(z_score, 2) if z_score is not None else None,
        "regime": regime,
        "badge": meta["badge"],
        "color": meta["color"],
        "market_fear_score": meta["score"],
        "interpretation": meta["interpretation"],
        "error": None,
    }
