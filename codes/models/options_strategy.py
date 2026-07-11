"""Construct and rank transparent option strategy candidates.

Payoff and Greek calculations are delegated to ``options_pricing`` and remain
separate from ranking judgment.  Ranking scores remain heuristic unless a
walk-forward calibration profile is supplied.
"""

from __future__ import annotations

import math
from collections.abc import Callable

from codes.engine.scorer import verdict_for_score
from codes.models.options_pricing import (
    analyze_debit_spread,
    analyze_long_contract,
    analyze_long_volatility,
    contract_entry_price,
)

UNCALIBRATED_RANKING_METHOD = "PHASE_3_HEURISTIC_UNCALIBRATED"
CALIBRATED_RANKING_METHOD = "PHASE_4_WALK_FORWARD_CALIBRATED"


def _finite(value: object) -> float | None:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if math.isfinite(result) else None


def _clip(value: float, low: float = 0.0, high: float = 100.0) -> float:
    return max(low, min(high, value))


def _usable_contracts(contracts: list[dict]) -> list[dict]:
    output = []
    for contract in contracts:
        if not isinstance(contract, dict):
            continue
        option_type = str(contract.get("option_type") or "").upper()
        strike = _finite(contract.get("strike"))
        dte = _finite(contract.get("days_to_expiry"))
        if option_type not in {"CALL", "PUT"} or strike is None or strike <= 0:
            continue
        if dte is None or dte <= 0 or not contract.get("expiration_date"):
            continue
        normalized = dict(contract)
        normalized["option_type"] = option_type
        normalized["strike"] = strike
        normalized["days_to_expiry"] = int(dte)
        output.append(normalized)
    return output


def _chosen_expiry(contracts: list[dict], horizon_days: int) -> str | None:
    expirations: dict[str, int] = {}
    for contract in contracts:
        expiration = str(contract.get("expiration_date") or "")
        dte = int(contract["days_to_expiry"])
        if expiration:
            expirations[expiration] = dte
    if not expirations:
        return None
    return min(
        expirations,
        key=lambda expiration: (
            abs(expirations[expiration] - horizon_days),
            expirations[expiration] < horizon_days,
            expirations[expiration],
        ),
    )


def _select_contract(
    contracts: list[dict],
    *,
    option_type: str,
    horizon_days: int,
    target_strike: float,
    liquidity_risk: Callable[[dict | None], float],
    expiration_date: str | None = None,
    position: str = "LONG",
) -> dict | None:
    candidates = [
        contract for contract in contracts
        if contract["option_type"] == option_type
        and (expiration_date is None or contract.get("expiration_date") == expiration_date)
    ]
    if not candidates:
        return None
    expiry = expiration_date or _chosen_expiry(candidates, horizon_days)
    candidates = [contract for contract in candidates if contract.get("expiration_date") == expiry]
    if not candidates:
        return None
    executable = [
        contract for contract in candidates
        if contract_entry_price(contract, position)[0] is not None
    ]
    if executable:
        candidates = executable
    return min(
        candidates,
        key=lambda contract: (
            abs(contract["strike"] - target_strike),
            contract_entry_price(contract, position)[0] is None,
            _finite(contract.get("implied_volatility")) is None,
            liquidity_risk(contract),
        ),
    )


def _select_short_vertical_leg(
    contracts: list[dict],
    long_contract: dict,
    *,
    target_width: float,
    liquidity_risk: Callable[[dict | None], float],
) -> dict | None:
    option_type = long_contract["option_type"]
    long_strike = long_contract["strike"]
    candidates = [
        contract for contract in contracts
        if contract["option_type"] == option_type
        and contract.get("expiration_date") == long_contract.get("expiration_date")
        and (
            contract["strike"] > long_strike
            if option_type == "CALL"
            else contract["strike"] < long_strike
        )
    ]
    if not candidates:
        return None
    executable = [
        contract for contract in candidates
        if contract_entry_price(contract, "SHORT")[0] is not None
    ]
    if executable:
        candidates = executable
    target = long_strike + target_width if option_type == "CALL" else long_strike - target_width
    return min(
        candidates,
        key=lambda contract: (
            abs(contract["strike"] - target),
            contract_entry_price(contract, "SHORT")[0] is None,
            liquidity_risk(contract),
        ),
    )


def _volatility_pair(
    contracts: list[dict],
    *,
    spot: float,
    horizon_days: int,
    expected_move_dollar: float,
    liquidity_risk: Callable[[dict | None], float],
) -> tuple[dict, dict] | None:
    by_expiration: dict[str, list[dict]] = {}
    for contract in contracts:
        by_expiration.setdefault(contract["expiration_date"], []).append(contract)
    eligible = {
        expiration: rows
        for expiration, rows in by_expiration.items()
        if {row["option_type"] for row in rows} == {"CALL", "PUT"}
    }
    if not eligible:
        return None
    expiration = _chosen_expiry(
        [row for rows in eligible.values() for row in rows], horizon_days
    )
    rows = eligible.get(expiration, [])
    calls = [row for row in rows if row["option_type"] == "CALL"]
    puts = [row for row in rows if row["option_type"] == "PUT"]
    common_strikes = sorted({row["strike"] for row in calls} & {row["strike"] for row in puts})
    if common_strikes:
        strike = min(common_strikes, key=lambda value: abs(value - spot))
        call = _select_contract(
            calls, option_type="CALL", horizon_days=horizon_days,
            target_strike=strike, expiration_date=expiration,
            liquidity_risk=liquidity_risk,
        )
        put = _select_contract(
            puts, option_type="PUT", horizon_days=horizon_days,
            target_strike=strike, expiration_date=expiration,
            liquidity_risk=liquidity_risk,
        )
    else:
        offset = max(expected_move_dollar * 0.25, spot * 0.02)
        call = _select_contract(
            calls, option_type="CALL", horizon_days=horizon_days,
            target_strike=spot + offset, expiration_date=expiration,
            liquidity_risk=liquidity_risk,
        )
        put = _select_contract(
            puts, option_type="PUT", horizon_days=horizon_days,
            target_strike=max(spot - offset, 0.01), expiration_date=expiration,
            liquidity_risk=liquidity_risk,
        )
    return (call, put) if call is not None and put is not None else None


def _direction_score(direction: str, bias: str, confidence: float) -> float:
    if bias == "NEUTRAL":
        return 75.0 if direction == "VOLATILITY" else 45.0
    aligned = (
        (bias == "CALL" and direction == "BULLISH")
        or (bias == "PUT" and direction == "BEARISH")
    )
    opposed = (
        (bias == "CALL" and direction == "BEARISH")
        or (bias == "PUT" and direction == "BULLISH")
    )
    if aligned:
        return 50.0 + confidence * 0.5
    if opposed:
        return 50.0 - confidence * 0.5
    return max(25.0, 55.0 - confidence * 0.25)


def _iv_fit_score(strategy_type: str, iv_level: str) -> float:
    is_spread = strategy_type.endswith("SPREAD")
    is_volatility = strategy_type in {"LONG_STRADDLE", "LONG_STRANGLE"}
    if iv_level == "LOW":
        return 90.0 if is_volatility else (70.0 if is_spread else 85.0)
    if iv_level == "HIGH":
        return 20.0 if is_volatility else (75.0 if is_spread else 30.0)
    if iv_level == "NORMAL":
        return 55.0 if is_volatility else (75.0 if is_spread else 60.0)
    return 50.0


def _risk_reward_score(candidate: dict) -> float:
    if candidate.get("max_profit_unbounded"):
        return 75.0
    maximum_loss = _finite(candidate.get("max_loss"))
    maximum_profit = _finite(candidate.get("max_profit"))
    if maximum_loss is None or maximum_loss <= 0 or maximum_profit is None:
        return 40.0
    ratio = maximum_profit / maximum_loss
    return _clip(30.0 + ratio * 25.0)


def _sample_profitable(sample: dict) -> bool | None:
    profitable = sample.get("profitable")
    if isinstance(profitable, bool):
        return profitable
    outcome_return = _finite(sample.get("outcome_return"))
    if outcome_return is not None:
        return outcome_return > 0
    outcome_pnl = _finite(sample.get("outcome_pnl"))
    if outcome_pnl is not None:
        return outcome_pnl > 0
    return None


def calibrate_strategy_thresholds(
    samples: list[dict],
    *,
    min_samples: int = 30,
    min_bucket_samples: int = 8,
) -> dict:
    """Derive score thresholds from historical walk-forward outcomes.

    Each sample should include ``ranking_score`` and either ``profitable``,
    ``outcome_return``, or ``outcome_pnl``.  The function is pure so production
    storage/backtest jobs can feed it without coupling the live signal path to a
    specific database.
    """
    valid = []
    for sample in samples or []:
        if not isinstance(sample, dict):
            continue
        score = _finite(sample.get("ranking_score"))
        profitable = _sample_profitable(sample)
        if score is None or profitable is None:
            continue
        valid.append({"ranking_score": _clip(score), "profitable": profitable})

    if len(valid) < min_samples:
        return {
            "calibration_status": "INSUFFICIENT_DATA",
            "sample_count": len(valid),
            "min_samples": min_samples,
            "ranking_method": UNCALIBRATED_RANKING_METHOD,
            "thresholds": None,
        }

    def bucket_stats(predicate) -> tuple[int, float] | None:
        rows = [row for row in valid if predicate(row["ranking_score"])]
        if len(rows) < min_bucket_samples:
            return None
        wins = sum(1 for row in rows if row["profitable"])
        return len(rows), wins / len(rows)

    favorable = None
    favorable_separation = -1.0
    high_conviction = None
    for threshold in range(40, 91, 5):
        upper_stats = bucket_stats(lambda score, t=threshold: score >= t)
        lower_stats = bucket_stats(lambda score, t=threshold: score < t)
        if upper_stats is None:
            continue
        _count, win_rate = upper_stats
        lower_win_rate = lower_stats[1] if lower_stats is not None else 0.0
        separation = win_rate - lower_win_rate
        if win_rate >= 0.52 and separation > favorable_separation:
            favorable = threshold
            favorable_separation = separation
        if high_conviction is None and win_rate >= 0.60:
            high_conviction = threshold

    unfavorable = None
    for threshold in range(60, 14, -5):
        stats = bucket_stats(lambda score, t=threshold: score <= t)
        if stats is None:
            continue
        _count, win_rate = stats
        if win_rate <= 0.45:
            unfavorable = threshold
            break

    thresholds = {
        "favorable": favorable if favorable is not None else 60,
        "high_conviction": high_conviction if high_conviction is not None else 75,
        "unfavorable": unfavorable if unfavorable is not None else 30,
    }
    if thresholds["high_conviction"] < thresholds["favorable"]:
        thresholds["high_conviction"] = thresholds["favorable"]

    return {
        "calibration_status": "CALIBRATED",
        "sample_count": len(valid),
        "min_samples": min_samples,
        "min_bucket_samples": min_bucket_samples,
        "ranking_method": CALIBRATED_RANKING_METHOD,
        "thresholds": thresholds,
    }


def _calibrated_verdict(score: float, calibration_profile: dict | None) -> tuple[str, str, str, str]:
    if not isinstance(calibration_profile, dict):
        verdict, label, description = verdict_for_score(score, enhanced=True)
        return verdict, label, description, UNCALIBRATED_RANKING_METHOD
    if calibration_profile.get("calibration_status") != "CALIBRATED":
        verdict, label, description = verdict_for_score(score, enhanced=True)
        return verdict, label, description, UNCALIBRATED_RANKING_METHOD
    thresholds = calibration_profile.get("thresholds") or {}
    favorable = _finite(thresholds.get("favorable"))
    high_conviction = _finite(thresholds.get("high_conviction"))
    unfavorable = _finite(thresholds.get("unfavorable"))
    if favorable is None or high_conviction is None or unfavorable is None:
        verdict, label, description = verdict_for_score(score, enhanced=True)
        return verdict, label, description, UNCALIBRATED_RANKING_METHOD
    if score >= high_conviction:
        return "HIGH CONVICTION", "high-conviction", "Calibrated high-quality option setup", CALIBRATED_RANKING_METHOD
    if score >= favorable:
        return "FAVORABLE", "favorable", "Calibrated favorable option setup", CALIBRATED_RANKING_METHOD
    if score <= unfavorable:
        return "UNFAVORABLE", "unfavorable", "Calibrated weak option setup", CALIBRATED_RANKING_METHOD
    return "BALANCED", "balanced", "Calibrated middle-range option setup", CALIBRATED_RANKING_METHOD


def rank_strategy_candidates(
    candidates: list[dict],
    *,
    bias: str,
    confidence: float,
    iv_level: str,
    calibration_profile: dict | None = None,
) -> list[dict]:
    """Rank candidates, using calibrated labels when a valid profile exists."""
    ranked = []
    for candidate in candidates:
        direction_score = _direction_score(candidate["direction"], bias, confidence)
        expected_pct = _finite(candidate.get("expected_value_pct_of_max_loss"))
        valuation_score = 35.0 if expected_pct is None else _clip(55.0 + expected_pct * 2.0)
        probability = _finite(candidate.get("probability_profit_risk_neutral"))
        probability_score = probability * 100.0 if probability is not None else 35.0
        liquidity_risk_value = _finite(candidate.get("liquidity_risk"))
        if liquidity_risk_value is None:
            liquidity_risk_value = 50.0
        liquidity_score = 100.0 - _clip(liquidity_risk_value)
        iv_fit_score = _iv_fit_score(candidate["strategy_type"], iv_level)
        risk_reward_score = _risk_reward_score(candidate)

        ranking_score = (
            direction_score * 0.35
            + valuation_score * 0.20
            + probability_score * 0.10
            + liquidity_score * 0.15
            + iv_fit_score * 0.10
            + risk_reward_score * 0.10
        )
        if candidate.get("calculation_status") != "COMPLETE":
            ranking_score *= 0.80
        ranking_score = round(_clip(ranking_score), 1)
        verdict, label, description, ranking_method = _calibrated_verdict(
            ranking_score, calibration_profile,
        )

        enriched = dict(candidate)
        enriched.update({
            "ranking_score": ranking_score,
            "ranking_verdict": verdict,
            "ranking_label": label,
            "ranking_description": description,
            "ranking_components": {
                "direction_alignment": round(direction_score, 1),
                "risk_neutral_value": round(valuation_score, 1),
                "probability_profit": round(probability_score, 1),
                "liquidity": round(liquidity_score, 1),
                "iv_fit": round(iv_fit_score, 1),
                "risk_reward": round(risk_reward_score, 1),
            },
            "ranking_method": ranking_method,
            "calibration_status": (
                calibration_profile.get("calibration_status")
                if isinstance(calibration_profile, dict)
                else "UNAVAILABLE"
            ),
        })
        ranked.append(enriched)

    ranked.sort(
        key=lambda candidate: (
            -candidate["ranking_score"],
            candidate["strategy_type"],
        )
    )
    for index, candidate in enumerate(ranked, start=1):
        candidate["rank"] = index
    return ranked


def build_ranked_strategy_candidates(
    contracts: list[dict],
    *,
    spot: float,
    horizon_days: int,
    expected_move_dollar: float | None,
    bias: str,
    confidence: float,
    iv_level: str,
    risk_free_rate: float,
    dividend_yield: float,
    liquidity_risk: Callable[[dict | None], float],
    calibration_profile: dict | None = None,
) -> list[dict]:
    """Build long-option, vertical-spread, and volatility candidates."""
    rows = _usable_contracts(contracts)
    if not rows or spot <= 0:
        return []
    move_dollar = max(_finite(expected_move_dollar) or spot * 0.08, spot * 0.02)
    target_call = spot + move_dollar * 0.5
    target_put = max(spot - move_dollar * 0.5, 0.01)
    long_call = _select_contract(
        rows, option_type="CALL", horizon_days=horizon_days,
        target_strike=target_call, liquidity_risk=liquidity_risk,
    )
    long_put = _select_contract(
        rows, option_type="PUT", horizon_days=horizon_days,
        target_strike=target_put, liquidity_risk=liquidity_risk,
    )

    candidates = []
    for contract in (long_call, long_put):
        if contract is None:
            continue
        candidate = analyze_long_contract(
            contract,
            spot=spot,
            risk_free_rate=risk_free_rate,
            dividend_yield=dividend_yield,
        )
        if candidate is not None:
            candidate["liquidity_risk"] = liquidity_risk(contract)
            candidates.append(candidate)

    target_width = max(move_dollar * 0.5, spot * 0.03)
    for long_contract in (long_call, long_put):
        if long_contract is None:
            continue
        short_contract = _select_short_vertical_leg(
            rows,
            long_contract,
            target_width=target_width,
            liquidity_risk=liquidity_risk,
        )
        if short_contract is None:
            continue
        candidate = analyze_debit_spread(
            long_contract,
            short_contract,
            spot=spot,
            risk_free_rate=risk_free_rate,
            dividend_yield=dividend_yield,
        )
        if candidate is not None:
            candidate["liquidity_risk"] = round(
                (liquidity_risk(long_contract) + liquidity_risk(short_contract)) / 2.0,
                1,
            )
            candidates.append(candidate)

    pair = _volatility_pair(
        rows,
        spot=spot,
        horizon_days=horizon_days,
        expected_move_dollar=move_dollar,
        liquidity_risk=liquidity_risk,
    )
    if pair is not None:
        call_contract, put_contract = pair
        candidate = analyze_long_volatility(
            call_contract,
            put_contract,
            spot=spot,
            risk_free_rate=risk_free_rate,
            dividend_yield=dividend_yield,
        )
        if candidate is not None:
            candidate["liquidity_risk"] = round(
                (liquidity_risk(call_contract) + liquidity_risk(put_contract)) / 2.0,
                1,
            )
            candidates.append(candidate)

    return rank_strategy_candidates(
        candidates,
        bias=bias,
        confidence=confidence,
        iv_level=iv_level,
        calibration_profile=calibration_profile,
    )
