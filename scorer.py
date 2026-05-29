"""
Composite scorer: Graham 40% + Quality 35% + Momentum 25%.

Verdicts:
  >= 70  STRONG BUY   — all pillars aligned
  55-70  BUY          — mostly positive signals
  40-55  WATCH        — mixed signals, monitor
  25-40  HOLD/WEAK    — significant concerns
  < 25   AVOID        — fails on multiple pillars
"""

WEIGHTS = {
    "graham":   0.40,
    "quality":  0.35,
    "momentum": 0.25,
}

VERDICTS = [
    (70, "STRONG BUY",  "strong-buy",  "All three pillars aligned — rare Graham+Quality+Momentum signal"),
    (55, "BUY",         "buy",         "Mostly positive — good value with quality confirmation"),
    (40, "WATCH",       "watch",       "Mixed signals — monitor for entry point"),
    (25, "HOLD/WEAK",   "hold",        "Significant concerns — not a high-conviction idea"),
    (0,  "AVOID",       "avoid",       "Fails on multiple pillars — skip"),
]


def composite(graham_result: dict, quality_result: dict,
              momentum_result: dict) -> dict:
    """
    Combine three scoring results into a final composite score.
    All inputs are the dict returns from their respective score() functions.
    """
    g_score = graham_result.get("total_score", 0)
    g_max   = graham_result.get("total_max", 100)
    q_score = quality_result.get("total_score", 0)
    q_max   = quality_result.get("total_max", 100)
    m_score = momentum_result.get("total_score", 0)
    m_max   = momentum_result.get("total_max", 100)

    # Normalise each to 0-100
    g_pct = (g_score / g_max * 100) if g_max else 0
    q_pct = (q_score / q_max * 100) if q_max else 0
    m_pct = (m_score / m_max * 100) if m_max else 0

    composite_score = (
        g_pct * WEIGHTS["graham"] +
        q_pct * WEIGHTS["quality"] +
        m_pct * WEIGHTS["momentum"]
    )

    # Determine verdict
    verdict = label = description = ""
    for threshold, v, l, d in VERDICTS:
        if composite_score >= threshold:
            verdict, label, description = v, l, d
            break

    # Value trap check: good Graham but bad momentum
    value_trap_warning = (
        g_pct >= 60 and
        m_pct < 30 and
        quality_result.get("roe") is not None and
        quality_result.get("roe", 0) < 10
    )

    return {
        "graham_pct":       round(g_pct, 1),
        "quality_pct":      round(q_pct, 1),
        "momentum_pct":     round(m_pct, 1),
        "composite_score":  round(composite_score, 1),
        "verdict":          verdict,
        "verdict_label":    label,
        "verdict_desc":     description,
        "value_trap_warning": value_trap_warning,
        "weights":          WEIGHTS,
    }


def fundamental_only(graham_result: dict, quality_result: dict) -> dict:
    """
    Score without momentum — used for screener pre-filter.
    Weights re-normalised to Graham 53% / Quality 47%.
    """
    g_score = graham_result.get("total_score", 0)
    g_max   = graham_result.get("total_max", 100)
    q_score = quality_result.get("total_score", 0)
    q_max   = quality_result.get("total_max", 100)

    g_pct = (g_score / g_max * 100) if g_max else 0
    q_pct = (q_score / q_max * 100) if q_max else 0

    score = g_pct * 0.53 + q_pct * 0.47

    return {
        "graham_pct":       round(g_pct, 1),
        "quality_pct":      round(q_pct, 1),
        "momentum_pct":     None,
        "composite_score":  round(score, 1),
        "verdict":          "PENDING",
        "verdict_label":    "pending",
        "verdict_desc":     "Momentum not yet loaded",
        "value_trap_warning": False,
    }
