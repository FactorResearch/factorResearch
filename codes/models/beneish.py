"""
Beneish M-Score — forensic earnings-manipulation diagnostic.

Reference formula:
  M = -4.84 + 0.92*DSRI + 0.528*GMI + 0.404*AQI + 0.892*SGI
      + 0.115*DEPI - 0.172*SGAI + 4.679*TATA - 0.327*LVGI

Interpretation:
  M > -1.78 suggests elevated manipulation risk.

Implementation note:
  Some cached historical rows predate Beneish-specific SEC extractions
  (receivables, depreciation, SG&A). To keep old analyses backfillable,
  missing index-style components default to a neutral "no change" value of 1.0
  and missing TATA defaults to 0.0. The result exposes n_available and
  available_fraction so callers can see when the calculation is partial.
"""

from __future__ import annotations

from typing import Any

from codes.core import model_utils as mu


def _safe(val: Any) -> float | None:
    return mu.safe_float(val)


def _first(records: list[dict[str, Any]]) -> float | None:
    return mu.first_record_value(records)


def _values(records: list[dict[str, Any]], n: int) -> list[float]:
    return mu.record_values(records)[:n]


def _clamp(v: float, lo: float, hi: float) -> float:
    return mu.clamp(v, lo, hi)


def _ratio(num: float | None, den: float | None) -> float | None:
    if num is None or den is None or den == 0:
        return None
    return num / den


def _index(current: float | None, prior: float | None) -> float | None:
    if current is None or prior is None or prior == 0:
        return None
    return current / prior


def _neutral_index(v: float | None) -> float:
    return v if v is not None else 1.0


def _signal(m_score: float | None) -> str:
    if m_score is None:
        return "UNKNOWN"
    if m_score > -1.78:
        return "ELEVATED_MANIPULATION_RISK"
    if m_score > -2.22:
        return "WATCH"
    return "LOW_MANIPULATION_RISK"


def _risk_label(m_score: float | None) -> str:
    if m_score is None:
        return "Unknown"
    if m_score > -1.78:
        return "High"
    if m_score > -2.22:
        return "Moderate"
    return "Low"


def _risk_score(m_score: float | None) -> float:
    if m_score is None:
        return 50.0
    # Map a practical Beneish range [-3.0, 0.0] to [0, 100].
    return round(_clamp((m_score + 3.0) / 3.0 * 100, 0.0, 100.0), 2)


def score(sec: dict) -> dict:
    revenue = _values(sec.get("revenue", []), 2)
    receivables = _values(sec.get("receivables", []), 2)
    gross_profit = _values(sec.get("gross_profit", []), 2)
    cur_ast = _values(sec.get("cur_ast", []), 2)
    ppe_net = _values(sec.get("ppe_net", []), 2)
    securities = _values(sec.get("marketable_securities", []), 2)
    total_assets = _values(sec.get("total_assets", []), 2)
    depreciation = _values(sec.get("depreciation", []), 2)
    sga_expense = _values(sec.get("sga_expense", []), 2)
    cur_lib = _values(sec.get("cur_lib", []), 2)
    lt_debt = _values(sec.get("lt_debt", []), 2)

    net_inc = _first(sec.get("income_from_continuing_operations", []))
    if net_inc is None:
        net_inc = _first(sec.get("net_inc", []))
    op_cf = _first(sec.get("op_cf", []))
    total_assets_current = total_assets[0] if total_assets else None

    rev_t = revenue[0] if len(revenue) > 0 else None
    rev_tm1 = revenue[1] if len(revenue) > 1 else None
    rec_t = receivables[0] if len(receivables) > 0 else None
    rec_tm1 = receivables[1] if len(receivables) > 1 else None
    gp_t = gross_profit[0] if len(gross_profit) > 0 else None
    gp_tm1 = gross_profit[1] if len(gross_profit) > 1 else None
    ca_t = cur_ast[0] if len(cur_ast) > 0 else None
    ca_tm1 = cur_ast[1] if len(cur_ast) > 1 else None
    ppe_t = ppe_net[0] if len(ppe_net) > 0 else None
    ppe_tm1 = ppe_net[1] if len(ppe_net) > 1 else None
    sec_t = securities[0] if len(securities) > 0 else 0.0
    sec_tm1 = securities[1] if len(securities) > 1 else 0.0
    ta_t = total_assets[0] if len(total_assets) > 0 else None
    ta_tm1 = total_assets[1] if len(total_assets) > 1 else None
    dep_t = depreciation[0] if len(depreciation) > 0 else None
    dep_tm1 = depreciation[1] if len(depreciation) > 1 else None
    sga_t = sga_expense[0] if len(sga_expense) > 0 else None
    sga_tm1 = sga_expense[1] if len(sga_expense) > 1 else None
    cl_t = cur_lib[0] if len(cur_lib) > 0 else None
    cl_tm1 = cur_lib[1] if len(cur_lib) > 1 else None
    ltd_t = lt_debt[0] if len(lt_debt) > 0 else None
    ltd_tm1 = lt_debt[1] if len(lt_debt) > 1 else None

    dsri = _index(_ratio(rec_t, rev_t), _ratio(rec_tm1, rev_tm1))

    gm_t = _ratio((rev_t - gp_t) if rev_t is not None and gp_t is not None else None, rev_t)
    gm_tm1 = _ratio((rev_tm1 - gp_tm1) if rev_tm1 is not None and gp_tm1 is not None else None, rev_tm1)
    gmi = _index(gm_tm1, gm_t)

    aq_component_t = None
    aq_component_tm1 = None
    if ta_t not in (None, 0):
        aq_component_t = 1 - ((ca_t or 0.0) + (ppe_t or 0.0) + (sec_t or 0.0)) / ta_t
    if ta_tm1 not in (None, 0):
        aq_component_tm1 = 1 - ((ca_tm1 or 0.0) + (ppe_tm1 or 0.0) + (sec_tm1 or 0.0)) / ta_tm1
    aqi = _index(aq_component_t, aq_component_tm1)

    sgi = _index(rev_t, rev_tm1)

    dep_rate_t = _ratio(dep_t, (ppe_t or 0.0) + (dep_t or 0.0))
    dep_rate_tm1 = _ratio(dep_tm1, (ppe_tm1 or 0.0) + (dep_tm1 or 0.0))
    depi = _index(dep_rate_tm1, dep_rate_t)

    sgai = _index(_ratio(sga_t, rev_t), _ratio(sga_tm1, rev_tm1))

    lev_t = _ratio((cl_t or 0.0) + (ltd_t or 0.0), ta_t)
    lev_tm1 = _ratio((cl_tm1 or 0.0) + (ltd_tm1 or 0.0), ta_tm1)
    lvgi = _index(lev_t, lev_tm1)

    tata = None
    if net_inc is not None and op_cf is not None and total_assets_current not in (None, 0):
        tata = (net_inc - op_cf) / total_assets_current

    inputs = {
        "dsri": dsri,
        "gmi": gmi,
        "aqi": aqi,
        "sgi": sgi,
        "depi": depi,
        "sgai": sgai,
        "lvgi": lvgi,
        "tata": tata,
    }
    n_available = sum(v is not None for v in inputs.values())
    available_fraction = round(n_available / 8.0, 4)

    m_score = (
        -4.84
        + 0.92 * _neutral_index(dsri)
        + 0.528 * _neutral_index(gmi)
        + 0.404 * _neutral_index(aqi)
        + 0.892 * _neutral_index(sgi)
        + 0.115 * _neutral_index(depi)
        - 0.172 * _neutral_index(sgai)
        + 4.679 * (tata if tata is not None else 0.0)
        - 0.327 * _neutral_index(lvgi)
    )
    m_score = round(m_score, 4)

    stressed_indices = []
    if dsri is not None and dsri > 1.1:
        stressed_indices.append("DSRI")
    if gmi is not None and gmi > 1.0:
        stressed_indices.append("GMI")
    if aqi is not None and aqi > 1.0:
        stressed_indices.append("AQI")
    if sgi is not None and sgi > 1.2:
        stressed_indices.append("SGI")
    if depi is not None and depi > 1.0:
        stressed_indices.append("DEPI")
    if sgai is not None and sgai > 1.0:
        stressed_indices.append("SGAI")
    if lvgi is not None and lvgi > 1.0:
        stressed_indices.append("LVGI")
    if tata is not None and tata > 0.04:
        stressed_indices.append("TATA")

    note = (
        "Full 8-variable Beneish coverage."
        if n_available == 8 else
        f"Partial Beneish coverage: {n_available}/8 variables available; missing inputs defaulted to neutral assumptions."
    )

    def _r(v: float | None, decimals: int = 4) -> float | None:
        return round(v, decimals) if v is not None else None

    return {
        "m_score": m_score,
        "signal": _signal(m_score),
        "risk_label": _risk_label(m_score),
        "risk_score": _risk_score(m_score),
        "likely_manipulator": m_score > -1.78,
        "threshold": -1.78,
        "n_available": n_available,
        "available_fraction": available_fraction,
        "stressed_indices": stressed_indices,
        "note": note,
        "dsri": _r(dsri),
        "gmi": _r(gmi),
        "aqi": _r(aqi),
        "sgi": _r(sgi),
        "depi": _r(depi),
        "sgai": _r(sgai),
        "lvgi": _r(lvgi, 6),
        "tata": _r(tata, 6),
        "total_score": _risk_score(m_score),
        "total_max": 100.0,
    }
