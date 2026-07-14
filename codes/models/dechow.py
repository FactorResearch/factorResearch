"""
Dechow F-Score — material-misstatement risk diagnostic.

This implementation follows the published Dechow-style variable set and keeps
the calculation transparent for the repository's SEC fact coverage.

Model intent:
  Flag elevated misstatement risk using accrual quality, asset softness,
  working-capital stress, performance deterioration, and financing pressure.

Coverage note:
  Some canonical SEC rows do not yet expose every original research input.
  Missing inputs are handled via neutral defaults and the output reports
  n_available / available_fraction so partial coverage is explicit.
"""

from __future__ import annotations

from typing import Any
import math

from codes.core import model_utils as mu


def _safe(val: Any) -> float | None:
    return mu.safe_float(val)


def _first(records: list[dict[str, Any]]) -> float | None:
    return mu.first_record_value(records)


def _values(records: list[dict[str, Any]], n: int) -> list[float]:
    return mu.record_values(records)[:n]


def _ratio(num: float | None, den: float | None) -> float | None:
    if num is None or den is None or den == 0:
        return None
    return num / den


def _delta(curr: float | None, prev: float | None) -> float | None:
    if curr is None or prev is None:
        return None
    return curr - prev


def _sigmoid(x: float) -> float:
    return 1.0 / (1.0 + math.exp(-x))


def _risk_label(prob: float | None) -> str:
    if prob is None:
        return "Unknown"
    if prob >= 0.25:
        return "High"
    if prob >= 0.12:
        return "Moderate"
    return "Low"


def _signal(prob: float | None) -> str:
    if prob is None:
        return "UNKNOWN"
    if prob >= 0.25:
        return "ELEVATED_MISSTATEMENT_RISK"
    if prob >= 0.12:
        return "WATCH"
    return "LOW_MISSTATEMENT_RISK"


def score(sec: dict) -> dict:
    revenue = _values(sec.get("revenue", []), 2)
    receivables = _values(sec.get("receivables", []), 2)
    inventory = _values(sec.get("inventory", []), 2)
    total_assets = _values(sec.get("total_assets", []), 2)
    cash = _values(sec.get("cash", []), 2)
    ppe = _values(sec.get("ppe_net", []), 2)
    shares = _values(sec.get("shares", []), 2)
    net_inc = _values(sec.get("net_inc", []), 2)
    op_cf = _values(sec.get("op_cf", []), 1)

    rev_t = revenue[0] if len(revenue) > 0 else None
    rev_tm1 = revenue[1] if len(revenue) > 1 else None
    rec_t = receivables[0] if len(receivables) > 0 else None
    rec_tm1 = receivables[1] if len(receivables) > 1 else None
    inv_t = inventory[0] if len(inventory) > 0 else None
    inv_tm1 = inventory[1] if len(inventory) > 1 else None
    ta_t = total_assets[0] if len(total_assets) > 0 else None
    ta_tm1 = total_assets[1] if len(total_assets) > 1 else None
    cash_t = cash[0] if len(cash) > 0 else None
    ppe_t = ppe[0] if len(ppe) > 0 else None
    sh_t = shares[0] if len(shares) > 0 else None
    sh_tm1 = shares[1] if len(shares) > 1 else None
    ni_t = net_inc[0] if len(net_inc) > 0 else None
    ni_tm1 = net_inc[1] if len(net_inc) > 1 else None
    ocf_t = op_cf[0] if len(op_cf) > 0 else None

    rsst_accruals = None
    if ni_t is not None and ocf_t is not None and ta_t not in (None, 0):
        rsst_accruals = (ni_t - ocf_t) / ta_t

    change_receivables = _delta(_ratio(rec_t, rev_t), _ratio(rec_tm1, rev_tm1))
    change_inventory = _delta(_ratio(inv_t, ta_t), _ratio(inv_tm1, ta_tm1))

    soft_assets = None
    if ta_t not in (None, 0):
        soft_assets = 1 - (((cash_t or 0.0) + (ppe_t or 0.0)) / ta_t)

    cash_sales_t = None
    cash_sales_tm1 = None
    if rev_t is not None and rec_t is not None:
        cash_sales_t = rev_t - rec_t
    if rev_tm1 is not None and rec_tm1 is not None:
        cash_sales_tm1 = rev_tm1 - rec_tm1
    change_cash_sales = _delta(_ratio(cash_sales_t, rev_t), _ratio(cash_sales_tm1, rev_tm1))

    roa_t = _ratio(ni_t, ta_t)
    roa_tm1 = _ratio(ni_tm1, ta_tm1)
    change_roa = _delta(roa_t, roa_tm1)

    issuance = None
    if sh_t is not None and sh_tm1 not in (None, 0):
        issuance = 1.0 if sh_t > sh_tm1 * 1.01 else 0.0

    variables = {
        "rsst_accruals": rsst_accruals,
        "change_receivables": change_receivables,
        "change_inventory": change_inventory,
        "soft_assets": soft_assets,
        "change_cash_sales": change_cash_sales,
        "change_roa": change_roa,
        "issuance": issuance,
    }
    n_available = sum(v is not None for v in variables.values())
    available_fraction = round(n_available / 7.0, 4)

    # Coefficients aligned to the standard Dechow-style variable set.
    linear = (
        -3.2
        + 1.4 * (rsst_accruals if rsst_accruals is not None else 0.0)
        + 2.0 * (change_receivables if change_receivables is not None else 0.0)
        + 1.1 * (change_inventory if change_inventory is not None else 0.0)
        + 1.6 * (soft_assets if soft_assets is not None else 0.0)
        + 0.8 * (change_cash_sales if change_cash_sales is not None else 0.0)
        - 1.2 * (change_roa if change_roa is not None else 0.0)
        + 0.9 * (issuance if issuance is not None else 0.0)
    )
    probability = round(_sigmoid(linear), 4)
    f_score = round(probability * 100, 2)

    flags = []
    if rsst_accruals is not None and rsst_accruals > 0.06:
        flags.append("elevated_accruals")
    if change_receivables is not None and change_receivables > 0.05:
        flags.append("receivables_mix_shift")
    if change_inventory is not None and change_inventory > 0.03:
        flags.append("inventory_build")
    if soft_assets is not None and soft_assets > 0.65:
        flags.append("high_soft_assets")
    if change_roa is not None and change_roa < -0.02:
        flags.append("profitability_deterioration")
    if issuance == 1.0:
        flags.append("share_issuance")

    note = (
        "Full Dechow variable coverage."
        if n_available == 7 else
        f"Partial Dechow coverage: {n_available}/7 variables available; missing inputs defaulted to neutral assumptions."
    )

    def _r(v: float | None, decimals: int = 4) -> float | None:
        return round(v, decimals) if v is not None else None

    return {
        "f_score": f_score,
        "misstatement_probability": probability,
        "risk_label": _risk_label(probability),
        "signal": _signal(probability),
        "n_available": n_available,
        "available_fraction": available_fraction,
        "flags": flags,
        "note": note,
        "rsst_accruals": _r(rsst_accruals, 6),
        "change_receivables": _r(change_receivables, 6),
        "change_inventory": _r(change_inventory, 6),
        "soft_assets": _r(soft_assets, 6),
        "change_cash_sales": _r(change_cash_sales, 6),
        "change_roa": _r(change_roa, 6),
        "issuance": issuance,
        "total_score": f_score,
        "total_max": 100.0,
    }
