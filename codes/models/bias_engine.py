"""
Bias Engine — pure classification layer.

Python port of BiasEngine.swift (see BiasEngine_Python_Rewrite.md).

IntrinsicIQ never outputs Buy/Sell/Avoid. All verdicts are expressed as
Outperform Bias / Neutral / Underperform Bias. This is the ONLY place in
the codebase permitted to produce that verdict-like label.

Inputs are the outputs of scorer.py (composite_score), risk_metrics.py
(risk level), and spy_benchmark_model.py (probability_outperform), plus
the Altman distress flag from altman.py / scorer.py.

Pure function, no networking / no I/O — trivially testable.
"""

from __future__ import annotations

from enum import Enum
from typing import Any


# ── Enums ─────────────────────────────────────────────────────────────────────

class RiskLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class Bias(str, Enum):
    OUTPERFORM = "Outperform Bias"
    NEUTRAL = "Neutral"
    UNDERPERFORM = "Underperform Bias"


# ── Thresholds (placeholders — tune later against backtests) ─────────────────

OUTPERFORM_PROB_THRESHOLD = 0.6
OUTPERFORM_SCORE_THRESHOLD = 60.0
UNDERPERFORM_PROB_THRESHOLD = 0.4
UNDERPERFORM_SCORE_THRESHOLD = 35.0


def _clamp(v: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, v))


def _confidence(composite_score: float, probability_outperform: float,
                 bias: Bias) -> float:
    """
    0..1, monotonic with distance from the nearest classification boundary.
    Combines how far the score/probability sit past the relevant threshold(s),
    normalised against the remaining headroom to the scale's edge.
    """
    if bias is Bias.OUTPERFORM:
        score_dist = (composite_score - OUTPERFORM_SCORE_THRESHOLD) / (100 - OUTPERFORM_SCORE_THRESHOLD)
        prob_dist = (probability_outperform - OUTPERFORM_PROB_THRESHOLD) / (1 - OUTPERFORM_PROB_THRESHOLD)
        return round(_clamp((score_dist + prob_dist) / 2), 4)

    if bias is Bias.UNDERPERFORM:
        score_dist = (UNDERPERFORM_SCORE_THRESHOLD - composite_score) / UNDERPERFORM_SCORE_THRESHOLD
        prob_dist = (UNDERPERFORM_PROB_THRESHOLD - probability_outperform) / UNDERPERFORM_PROB_THRESHOLD
        return round(_clamp(max(score_dist, prob_dist)), 4)

    # Neutral: confidence = closeness to the exact midpoint between the two
    # nearest boundaries (1.0 = dead centre, 0.0 = right at an edge).
    mid_score = (OUTPERFORM_SCORE_THRESHOLD + UNDERPERFORM_SCORE_THRESHOLD) / 2
    mid_prob = (OUTPERFORM_PROB_THRESHOLD + UNDERPERFORM_PROB_THRESHOLD) / 2
    score_half_range = (OUTPERFORM_SCORE_THRESHOLD - UNDERPERFORM_SCORE_THRESHOLD) / 2
    prob_half_range = (OUTPERFORM_PROB_THRESHOLD - UNDERPERFORM_PROB_THRESHOLD) / 2
    score_closeness = 1 - abs(composite_score - mid_score) / score_half_range if score_half_range else 1.0
    prob_closeness = 1 - abs(probability_outperform - mid_prob) / prob_half_range if prob_half_range else 1.0
    return round(_clamp((score_closeness + prob_closeness) / 2), 4)


# ── Main ──────────────────────────────────────────────────────────────────────

def classify(
    composite_score: float,
    risk_level: RiskLevel | str,
    probability_outperform: float,
    distress_flag: bool = False,
) -> dict[str, Any]:
    """
    Map composite score + risk + probability-of-outperformance to one of the
    three allowed bias states.

    Classification logic:
      distress_flag == True                                   → Underperform (cap overrides everything)
      probability_outperform >= 0.6 AND composite_score >= 60  → Outperform
      probability_outperform <= 0.4 OR  composite_score <= 35  → Underperform
      otherwise                                                → Neutral

    Args:
        composite_score:         0-100, from scorer.py
        risk_level:               RiskLevel | "low"|"medium"|"high" — carried
                                   through for display; not itself a threshold
                                   in the placeholder logic above.
        probability_outperform:   0..1, from spy_benchmark_model.compute_benchmark()
        distress_flag:            e.g. Altman distress-zone cap triggered

    Returns dict:
        bias:                    str (Bias.value)
        confidence:               float 0..1
        probability_outperform:   float (pass-through, for display)
        risk_level:                str
    """
    if isinstance(risk_level, RiskLevel):
        risk_level_val = risk_level.value
    else:
        risk_level_val = str(risk_level).lower()

    prob = _clamp(float(probability_outperform))
    score = float(composite_score)

    if distress_flag:
        bias = Bias.UNDERPERFORM
    elif prob >= OUTPERFORM_PROB_THRESHOLD and score >= OUTPERFORM_SCORE_THRESHOLD:
        bias = Bias.OUTPERFORM
    elif prob <= UNDERPERFORM_PROB_THRESHOLD or score <= UNDERPERFORM_SCORE_THRESHOLD:
        bias = Bias.UNDERPERFORM
    else:
        bias = Bias.NEUTRAL

    # Distress override always reports max confidence — the cap is absolute,
    # not a matter of degree.
    confidence = 1.0 if distress_flag else _confidence(score, prob, bias)

    return {
        "bias":                   bias.value,
        "confidence":             round(confidence, 4),
        "probability_outperform": prob,
        "risk_level":             risk_level_val,
    }
