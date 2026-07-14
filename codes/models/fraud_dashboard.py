"""
Advanced Fraud Dashboard — aggregate forensic accounting view.

Combines Accounting Quality, Beneish, and Dechow outputs into one summary
object for the Accounting section of the UI.
"""

from __future__ import annotations


def build(
    *,
    accounting_quality_result: dict | None,
    beneish_result: dict | None,
    dechow_result: dict | None,
) -> dict:
    aq = accounting_quality_result or {}
    ben = beneish_result or {}
    dec = dechow_result or {}

    aq_score = aq.get("accounting_quality_score")
    ben_score = ben.get("risk_score")
    dec_score = dec.get("f_score")

    components = [v for v in (aq_score, ben_score, dec_score) if isinstance(v, (int, float))]
    composite = round(sum(components) / len(components), 2) if components else 50.0

    high_votes = sum(
        1 for label in (
            aq.get("manipulation_risk"),
            ben.get("risk_label"),
            dec.get("risk_label"),
        )
        if str(label).lower() == "high"
    )

    if high_votes >= 2 or composite >= 70:
        risk = "High"
    elif composite >= 45:
        risk = "Moderate"
    else:
        risk = "Low"

    red_flags = []
    red_flags.extend(aq.get("warning_flags") or [])
    red_flags.extend((ben.get("stressed_indices") or [])[:4])
    red_flags.extend(dec.get("flags") or [])

    # keep order, dedupe
    seen = set()
    deduped_flags = []
    for flag in red_flags:
        if flag in seen:
            continue
        seen.add(flag)
        deduped_flags.append(flag)

    return {
        "fraud_risk_score": composite,
        "fraud_risk_level": risk,
        "accounting_quality_score": aq_score,
        "beneish_m_score": ben.get("m_score"),
        "beneish_risk_label": ben.get("risk_label"),
        "dechow_f_score": dec.get("f_score"),
        "dechow_risk_label": dec.get("risk_label"),
        "red_flags": deduped_flags,
        "red_flag_count": len(deduped_flags),
        "signal": f"{risk.upper()}_FRAUD_RISK",
    }
