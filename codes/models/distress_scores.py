"""V2.1 distress risk models: Ohlson O-Score and Zmijewski Score."""

from __future__ import annotations

import math
from typing import Any

from codes.models import altman
from codes.core import model_utils as mu


def score(price: float | None, sec: dict, altman_result: dict | None = None) -> dict[str, Any]:
    """Compute distress score bundle from normalized SEC facts."""
    ohlson = ohlson_o_score(sec)
    zmijewski = zmijewski_score(sec)
    altman_payload = altman_result if altman_result is not None else altman.score(price, sec)
    consensus = _consensus(ohlson, zmijewski, altman_payload)
    return {
        "ohlson": ohlson,
        "zmijewski": zmijewski,
        "altman": {
            "z_score": altman_payload.get("z_score"),
            "zone": altman_payload.get("zone"),
            "risk_score": altman_payload.get("risk_score"),
        },
        "consensus": consensus,
    }


def ohlson_o_score(sec: dict) -> dict[str, Any]:
    """
    Approximate Ohlson O-Score.

    The original size term uses a macro GNP price-level index. The app only
    stores normalized company facts, so this implementation uses
    log(total_assets_millions) as a stable company-size proxy and exposes that
    choice in the returned components.
    """
    total_assets = _first(sec.get("total_assets", []))
    total_liabilities = _first(sec.get("tot_lib", []))
    current_assets = _first(sec.get("cur_ast", []))
    current_liabilities = _first(sec.get("cur_lib", []))
    net_income = _first(sec.get("net_inc", []))
    op_cf = _first(sec.get("op_cf", []))
    ni_values = _values(sec.get("net_inc", []), 2)

    required = [total_assets, total_liabilities, current_assets, current_liabilities, net_income]
    if any(value is None for value in required) or not total_assets or total_assets <= 0:
        return _unknown("Insufficient data for Ohlson O-Score")

    working_capital = current_assets - current_liabilities
    size = math.log(max(total_assets / 1_000_000, 1e-9))
    tl_ta = total_liabilities / total_assets
    wc_ta = working_capital / total_assets
    cl_ca = current_liabilities / current_assets if current_assets and current_assets > 0 else None
    ni_ta = net_income / total_assets
    ffo_tl = op_cf / total_liabilities if op_cf is not None and total_liabilities and total_liabilities > 0 else None
    oeneg = 1.0 if total_liabilities > total_assets else 0.0
    intwo = 1.0 if len(ni_values) >= 2 and ni_values[0] < 0 and ni_values[1] < 0 else 0.0
    chin = _chin(ni_values)

    components_available = [size, tl_ta, wc_ta, cl_ca, ni_ta, ffo_tl, oeneg, intwo, chin]
    if sum(value is not None for value in components_available) < 7:
        return _unknown("Insufficient data for Ohlson O-Score")

    raw = (
        -1.32
        - 0.407 * size
        + 6.03 * tl_ta
        - 1.43 * wc_ta
        + (0.0757 * cl_ca if cl_ca is not None else 0.0)
        - 2.37 * ni_ta
        - (1.83 * ffo_tl if ffo_tl is not None else 0.0)
        + 0.285 * intwo
        - 1.72 * oeneg
        - (0.521 * chin if chin is not None else 0.0)
    )
    probability = _logistic(raw)
    return {
        "o_score": round(raw, 3),
        "probability": round(probability * 100, 2),
        "zone": _probability_zone(probability),
        "note": _probability_note("Ohlson", probability),
        "components": {
            "size_log_assets_millions": round(size, 4),
            "total_liabilities_to_assets": round(tl_ta, 4),
            "working_capital_to_assets": round(wc_ta, 4),
            "current_liabilities_to_assets": round(cl_ca, 4) if cl_ca is not None else None,
            "net_income_to_assets": round(ni_ta, 4),
            "operating_cash_flow_to_liabilities": round(ffo_tl, 4) if ffo_tl is not None else None,
            "liabilities_exceed_assets": bool(oeneg),
            "two_year_losses": bool(intwo),
            "net_income_change": round(chin, 4) if chin is not None else None,
        },
        "error": None,
    }


def zmijewski_score(sec: dict) -> dict[str, Any]:
    """Compute Zmijewski bankruptcy score and probability."""
    total_assets = _first(sec.get("total_assets", []))
    total_liabilities = _first(sec.get("tot_lib", []))
    current_assets = _first(sec.get("cur_ast", []))
    current_liabilities = _first(sec.get("cur_lib", []))
    net_income = _first(sec.get("net_inc", []))
    if any(value is None for value in [total_assets, total_liabilities, current_assets, current_liabilities, net_income]):
        return _unknown("Insufficient data for Zmijewski Score")
    if total_assets <= 0 or current_liabilities <= 0:
        return _unknown("Invalid denominator for Zmijewski Score")

    roa = net_income / total_assets
    leverage = total_liabilities / total_assets
    liquidity = current_assets / current_liabilities
    raw = -4.3 - 4.5 * roa + 5.7 * leverage - 0.004 * liquidity
    probability = _logistic(raw)
    return {
        "x_score": round(raw, 3),
        "probability": round(probability * 100, 2),
        "zone": _probability_zone(probability),
        "note": _probability_note("Zmijewski", probability),
        "components": {
            "return_on_assets": round(roa, 4),
            "liabilities_to_assets": round(leverage, 4),
            "current_ratio": round(liquidity, 4),
        },
        "error": None,
    }


def _first(records: list) -> float | None:
    for record in records or []:
        value = mu.safe_float(record.get("value"))
        if value is not None:
            return value
    return None


def _values(records: list, n: int) -> list[float]:
    values: list[float] = []
    for record in records or []:
        value = mu.safe_float(record.get("value"))
        if value is not None:
            values.append(value)
            if len(values) >= n:
                break
    return values


def _chin(values: list[float]) -> float | None:
    if len(values) < 2:
        return None
    current, prior = values[0], values[1]
    denominator = abs(current) + abs(prior)
    if denominator <= 0:
        return None
    return (current - prior) / denominator


def _logistic(value: float) -> float:
    if value >= 700:
        return 1.0
    if value <= -700:
        return 0.0
    return 1.0 / (1.0 + math.exp(-value))


def _probability_zone(probability: float) -> str:
    if probability >= 0.50:
        return "high"
    if probability >= 0.20:
        return "elevated"
    return "low"


def _probability_note(model: str, probability: float) -> str:
    zone = _probability_zone(probability)
    if zone == "high":
        return f"{model} probability {probability * 100:.1f}% — high distress risk"
    if zone == "elevated":
        return f"{model} probability {probability * 100:.1f}% — elevated distress risk"
    return f"{model} probability {probability * 100:.1f}% — low distress risk"


def _unknown(note: str) -> dict[str, Any]:
    return {
        "probability": None,
        "zone": "unknown",
        "note": note,
        "components": {},
        "error": note,
    }


def _consensus(ohlson: dict, zmijewski: dict, altman_payload: dict) -> dict[str, Any]:
    zones = []
    if ohlson.get("zone") in {"high", "elevated", "low"}:
        zones.append(ohlson["zone"])
    if zmijewski.get("zone") in {"high", "elevated", "low"}:
        zones.append(zmijewski["zone"])
    altman_zone = altman_payload.get("zone")
    if altman_zone == "distress":
        zones.append("high")
    elif altman_zone == "grey":
        zones.append("elevated")
    elif altman_zone == "safe":
        zones.append("low")

    if not zones:
        return {"zone": "unknown", "note": "No distress models available"}
    if "high" in zones:
        zone = "high"
    elif "elevated" in zones:
        zone = "elevated"
    else:
        zone = "low"
    return {
        "zone": zone,
        "models_available": len(zones),
        "note": f"{len(zones)} distress model(s) available; consensus risk is {zone}",
    }
