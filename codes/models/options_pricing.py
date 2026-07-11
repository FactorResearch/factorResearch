"""Pure option pricing, Greeks, and bounded-risk payoff analytics.

The module uses Black-Scholes-Merton as a transparent European approximation.
US equity options can be American-style, so callers must expose the model and
its assumptions rather than presenting these values as exchange-provided facts.
"""

from __future__ import annotations

import math
from typing import Iterable


DAYS_PER_YEAR = 365.0
DEFAULT_CONTRACT_MULTIPLIER = 100
GREEK_KEYS = (
    "delta",
    "gamma",
    "theta_per_day",
    "vega_per_vol_point",
    "rho_per_rate_point",
)


def _finite(value: object) -> float | None:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if math.isfinite(result) else None


def _rounded(value: float | None, digits: int = 6) -> float | None:
    return round(value, digits) if value is not None and math.isfinite(value) else None


def normal_pdf(value: float) -> float:
    return math.exp(-0.5 * value * value) / math.sqrt(2.0 * math.pi)


def normal_cdf(value: float) -> float:
    return 0.5 * (1.0 + math.erf(value / math.sqrt(2.0)))


def black_scholes_metrics(
    option_type: str,
    spot: float,
    strike: float,
    time_years: float,
    volatility: float,
    risk_free_rate: float = 0.045,
    dividend_yield: float = 0.0,
) -> dict | None:
    """Return theoretical value and first-order Black-Scholes-Merton Greeks.

    Vega and rho are reported per one percentage-point change. Theta is per
    calendar day; all other values are per underlying share.
    """
    kind = str(option_type or "").upper().strip()
    s = _finite(spot)
    k = _finite(strike)
    t = _finite(time_years)
    sigma = _finite(volatility)
    rate = _finite(risk_free_rate)
    dividend = _finite(dividend_yield)
    if (
        kind not in {"CALL", "PUT"}
        or s is None or s <= 0
        or k is None or k <= 0
        or t is None or t <= 0
        or sigma is None or sigma <= 0
        or rate is None
        or dividend is None
    ):
        return None

    sqrt_t = math.sqrt(t)
    sigma_sqrt_t = sigma * sqrt_t
    d1 = (math.log(s / k) + (rate - dividend + 0.5 * sigma * sigma) * t) / sigma_sqrt_t
    d2 = d1 - sigma_sqrt_t
    discount_rate = math.exp(-rate * t)
    discount_dividend = math.exp(-dividend * t)
    density = normal_pdf(d1)

    if kind == "CALL":
        theoretical = s * discount_dividend * normal_cdf(d1) - k * discount_rate * normal_cdf(d2)
        delta = discount_dividend * normal_cdf(d1)
        theta_annual = (
            -(s * discount_dividend * density * sigma) / (2.0 * sqrt_t)
            - rate * k * discount_rate * normal_cdf(d2)
            + dividend * s * discount_dividend * normal_cdf(d1)
        )
        rho = k * t * discount_rate * normal_cdf(d2) / 100.0
        probability_itm = normal_cdf(d2)
        intrinsic = max(s - k, 0.0)
    else:
        theoretical = k * discount_rate * normal_cdf(-d2) - s * discount_dividend * normal_cdf(-d1)
        delta = discount_dividend * (normal_cdf(d1) - 1.0)
        theta_annual = (
            -(s * discount_dividend * density * sigma) / (2.0 * sqrt_t)
            + rate * k * discount_rate * normal_cdf(-d2)
            - dividend * s * discount_dividend * normal_cdf(-d1)
        )
        rho = -k * t * discount_rate * normal_cdf(-d2) / 100.0
        probability_itm = normal_cdf(-d2)
        intrinsic = max(k - s, 0.0)

    gamma = discount_dividend * density / (s * sigma_sqrt_t)
    vega = s * discount_dividend * density * sqrt_t / 100.0
    return {
        "model": "BLACK_SCHOLES_MERTON",
        "theoretical_value": _rounded(max(theoretical, 0.0)),
        "intrinsic_value": _rounded(intrinsic),
        "time_value": _rounded(max(theoretical - intrinsic, 0.0)),
        "delta": _rounded(delta, 8),
        "gamma": _rounded(gamma, 8),
        "theta_per_day": _rounded(theta_annual / DAYS_PER_YEAR, 8),
        "vega_per_vol_point": _rounded(vega, 8),
        "rho_per_rate_point": _rounded(rho, 8),
        "probability_itm_risk_neutral": _rounded(min(max(probability_itm, 0.0), 1.0), 6),
        "d1": _rounded(d1, 8),
        "d2": _rounded(d2, 8),
    }


def expected_option_payoff(
    option_type: str,
    spot: float,
    strike: float,
    time_years: float,
    volatility: float,
    drift: float,
    dividend_yield: float = 0.0,
) -> float | None:
    """Expected undiscounted expiry payoff under a lognormal distribution."""
    kind = str(option_type or "").upper().strip()
    values = tuple(_finite(value) for value in (
        spot, strike, time_years, volatility, drift, dividend_yield,
    ))
    if any(value is None for value in values):
        return None
    s, k, t, sigma, mu, dividend = values
    if kind not in {"CALL", "PUT"} or s <= 0 or k <= 0 or t <= 0 or sigma <= 0:
        return None

    sigma_sqrt_t = sigma * math.sqrt(t)
    d1 = (math.log(s / k) + (mu - dividend + 0.5 * sigma * sigma) * t) / sigma_sqrt_t
    d2 = d1 - sigma_sqrt_t
    expected_underlying = s * math.exp((mu - dividend) * t)
    if kind == "CALL":
        return expected_underlying * normal_cdf(d1) - k * normal_cdf(d2)
    return k * normal_cdf(-d2) - expected_underlying * normal_cdf(-d1)


def terminal_probability(
    *,
    spot: float,
    threshold: float,
    time_years: float,
    volatility: float,
    drift: float,
    dividend_yield: float = 0.0,
    above: bool,
) -> float | None:
    """Probability terminal spot finishes above/below ``threshold``."""
    values = tuple(_finite(value) for value in (
        spot, threshold, time_years, volatility, drift, dividend_yield,
    ))
    if any(value is None for value in values):
        return None
    s, boundary, t, sigma, mu, dividend = values
    if s <= 0 or t <= 0 or sigma <= 0:
        return None
    if boundary <= 0:
        return 1.0 if above else 0.0
    mean_log_return = (mu - dividend - 0.5 * sigma * sigma) * t
    z_score = (math.log(boundary / s) - mean_log_return) / (sigma * math.sqrt(t))
    below_probability = normal_cdf(z_score)
    probability = 1.0 - below_probability if above else below_probability
    return min(max(probability, 0.0), 1.0)


def contract_entry_price(contract: dict, position: str) -> tuple[float | None, str | None]:
    """Choose a conservative executable quote for a long or short leg."""
    side = str(position or "").upper().strip()
    fields = (
        (("ask", "ASK"), ("mid", "MID"), ("last_price", "LAST"), ("bid", "BID"))
        if side == "LONG"
        else (("bid", "BID"), ("mid", "MID"), ("last_price", "LAST"), ("ask", "ASK"))
    )
    for field, source in fields:
        value = _finite(contract.get(field))
        if value is not None and value > 0:
            return value, source
    return None, None


def _multiplier(contract: dict) -> int:
    value = _finite(contract.get("contract_multiplier"))
    return int(value) if value is not None and value > 0 else DEFAULT_CONTRACT_MULTIPLIER


def _time_years(contract: dict) -> float | None:
    days = _finite(contract.get("days_to_expiry"))
    return days / DAYS_PER_YEAR if days is not None and days > 0 else None


def _provider_greeks(contract: dict) -> dict | None:
    fields = {
        "delta": _finite(contract.get("delta")),
        "gamma": _finite(contract.get("gamma")),
        "theta": _finite(contract.get("theta")),
        "vega": _finite(contract.get("vega")),
        "rho": _finite(contract.get("rho")),
    }
    if not any(value is not None for value in fields.values()):
        return None
    fields["units"] = "PROVIDER_NATIVE"
    return fields


def _leg(contract: dict, position: str, entry_price: float, price_source: str) -> dict:
    return {
        "position": position,
        "quantity": 1,
        "option_type": str(contract.get("option_type") or "").upper(),
        "contract_symbol": contract.get("contract_symbol"),
        "expiration_date": contract.get("expiration_date"),
        "days_to_expiry": contract.get("days_to_expiry"),
        "strike": _finite(contract.get("strike")),
        "entry_price": _rounded(entry_price),
        "entry_price_source": price_source,
        "implied_volatility": _finite(contract.get("implied_volatility")),
        "multiplier": _multiplier(contract),
    }


def _combine_greeks(weighted_metrics: Iterable[tuple[dict | None, float]]) -> dict | None:
    pairs = list(weighted_metrics)
    if not pairs or any(metrics is None for metrics, _weight in pairs):
        return None
    combined = {}
    for key in GREEK_KEYS:
        values = [(_finite(metrics.get(key)), weight) for metrics, weight in pairs]
        if any(value is None for value, _weight in values):
            combined[key] = None
        else:
            combined[key] = _rounded(sum(value * weight for value, weight in values), 8)
    theoretical_values = [
        (_finite(metrics.get("theoretical_value")), weight)
        for metrics, weight in pairs
    ]
    combined["theoretical_value"] = (
        _rounded(sum(value * weight for value, weight in theoretical_values))
        if all(value is not None for value, _weight in theoretical_values)
        else None
    )
    return combined


def analyze_long_contract(
    contract: dict,
    *,
    spot: float,
    risk_free_rate: float,
    dividend_yield: float,
) -> dict | None:
    """Greeks and expiry payoff analytics for one long call or put."""
    option_type = str(contract.get("option_type") or "").upper()
    strike = _finite(contract.get("strike"))
    time_years = _time_years(contract)
    volatility = _finite(contract.get("implied_volatility"))
    entry_price, price_source = contract_entry_price(contract, "LONG")
    if option_type not in {"CALL", "PUT"} or strike is None or time_years is None:
        return None

    multiplier = _multiplier(contract)
    breakeven = None
    max_loss = None
    max_profit = None
    if entry_price is not None:
        breakeven = strike + entry_price if option_type == "CALL" else strike - entry_price
        max_loss = entry_price * multiplier
        if option_type == "PUT":
            max_profit = max(strike - entry_price, 0.0) * multiplier

    model = black_scholes_metrics(
        option_type, spot, strike, time_years, volatility,
        risk_free_rate, dividend_yield,
    ) if volatility is not None else None

    probability_profit = expected_value = expected_value_pct = model_edge = None
    if model is not None and entry_price is not None and breakeven is not None:
        probability_profit = terminal_probability(
            spot=spot,
            threshold=breakeven,
            time_years=time_years,
            volatility=volatility,
            drift=risk_free_rate,
            dividend_yield=dividend_yield,
            above=option_type == "CALL",
        )
        expected_payoff = expected_option_payoff(
            option_type, spot, strike, time_years, volatility,
            risk_free_rate, dividend_yield,
        )
        if expected_payoff is not None:
            financed_debit = entry_price * math.exp(risk_free_rate * time_years)
            expected_value = (expected_payoff - financed_debit) * multiplier
            expected_value_pct = expected_value / max_loss * 100.0 if max_loss else None
        theoretical = _finite(model.get("theoretical_value"))
        if theoretical is not None:
            model_edge = (theoretical - entry_price) * multiplier

    strategy_type = f"LONG_{option_type}"
    return {
        "strategy_type": strategy_type,
        "strategy_name": "Long Call" if option_type == "CALL" else "Long Put",
        "direction": "BULLISH" if option_type == "CALL" else "BEARISH",
        "calculation_status": "COMPLETE" if model is not None and entry_price is not None else "PARTIAL",
        "legs": [_leg(contract, "LONG", entry_price, price_source)] if entry_price is not None else [],
        "net_debit": _rounded(entry_price * multiplier if entry_price is not None else None, 2),
        "net_debit_per_share": _rounded(entry_price),
        "breakevens": [_rounded(breakeven)] if breakeven is not None else [],
        "max_loss": _rounded(max_loss, 2),
        "max_profit": _rounded(max_profit, 2),
        "max_profit_unbounded": option_type == "CALL",
        "probability_profit_risk_neutral": _rounded(probability_profit, 6),
        "expected_value_risk_neutral": _rounded(expected_value, 2),
        "expected_value_pct_of_max_loss": _rounded(expected_value_pct, 2),
        "model_edge_at_entry": _rounded(model_edge, 2),
        "greeks": ({key: model.get(key) for key in GREEK_KEYS} if model else None),
        "theoretical_value_per_share": model.get("theoretical_value") if model else None,
        "provider_greeks": _provider_greeks(contract),
        "pricing_model": "BLACK_SCHOLES_MERTON" if model else None,
        "expected_value_model": "RISK_NEUTRAL_LOGNORMAL" if model else None,
        "contract_multiplier": multiplier,
    }


def analyze_debit_spread(
    long_contract: dict,
    short_contract: dict,
    *,
    spot: float,
    risk_free_rate: float,
    dividend_yield: float,
) -> dict | None:
    """Analytics for a bull-call or bear-put vertical debit spread."""
    option_type = str(long_contract.get("option_type") or "").upper()
    if option_type != str(short_contract.get("option_type") or "").upper():
        return None
    if long_contract.get("expiration_date") != short_contract.get("expiration_date"):
        return None

    long_strike = _finite(long_contract.get("strike"))
    short_strike = _finite(short_contract.get("strike"))
    time_years = _time_years(long_contract)
    if option_type not in {"CALL", "PUT"} or None in {long_strike, short_strike, time_years}:
        return None
    if (option_type == "CALL" and short_strike <= long_strike) or (
        option_type == "PUT" and short_strike >= long_strike
    ):
        return None

    long_price, long_source = contract_entry_price(long_contract, "LONG")
    short_price, short_source = contract_entry_price(short_contract, "SHORT")
    if long_price is None or short_price is None:
        return None
    debit = long_price - short_price
    width = abs(short_strike - long_strike)
    # A debit at or above spread width cannot produce a positive payoff and is
    # normally a crossed/stale quote rather than an actionable candidate.
    if debit <= 0 or width <= 0 or debit >= width:
        return None

    multiplier = min(_multiplier(long_contract), _multiplier(short_contract))
    max_loss = debit * multiplier
    max_profit = (width - debit) * multiplier
    breakeven = long_strike + debit if option_type == "CALL" else long_strike - debit

    long_iv = _finite(long_contract.get("implied_volatility"))
    short_iv = _finite(short_contract.get("implied_volatility")) or long_iv
    long_model = black_scholes_metrics(
        option_type, spot, long_strike, time_years, long_iv,
        risk_free_rate, dividend_yield,
    ) if long_iv is not None else None
    short_model = black_scholes_metrics(
        option_type, spot, short_strike, time_years, short_iv,
        risk_free_rate, dividend_yield,
    ) if short_iv is not None else None
    net_greeks = _combine_greeks(((long_model, 1.0), (short_model, -1.0)))

    probability_profit = expected_value = expected_value_pct = model_edge = None
    if long_model is not None and short_model is not None:
        probability_vol = (long_iv + short_iv) / 2.0
        probability_profit = terminal_probability(
            spot=spot,
            threshold=breakeven,
            time_years=time_years,
            volatility=probability_vol,
            drift=risk_free_rate,
            dividend_yield=dividend_yield,
            above=option_type == "CALL",
        )
        long_payoff = expected_option_payoff(
            option_type, spot, long_strike, time_years, long_iv,
            risk_free_rate, dividend_yield,
        )
        short_payoff = expected_option_payoff(
            option_type, spot, short_strike, time_years, short_iv,
            risk_free_rate, dividend_yield,
        )
        if long_payoff is not None and short_payoff is not None:
            financed_debit = debit * math.exp(risk_free_rate * time_years)
            expected_value = (long_payoff - short_payoff - financed_debit) * multiplier
            expected_value_pct = expected_value / max_loss * 100.0 if max_loss else None
        theoretical = _finite(net_greeks.get("theoretical_value")) if net_greeks else None
        if theoretical is not None:
            model_edge = (theoretical - debit) * multiplier

    is_call = option_type == "CALL"
    return {
        "strategy_type": "BULL_CALL_SPREAD" if is_call else "BEAR_PUT_SPREAD",
        "strategy_name": "Bull Call Spread" if is_call else "Bear Put Spread",
        "direction": "BULLISH" if is_call else "BEARISH",
        "calculation_status": "COMPLETE" if net_greeks is not None else "PARTIAL",
        "legs": [
            _leg(long_contract, "LONG", long_price, long_source),
            _leg(short_contract, "SHORT", short_price, short_source),
        ],
        "net_debit": _rounded(max_loss, 2),
        "net_debit_per_share": _rounded(debit),
        "spread_width": _rounded(width),
        "breakevens": [_rounded(breakeven)],
        "max_loss": _rounded(max_loss, 2),
        "max_profit": _rounded(max_profit, 2),
        "max_profit_unbounded": False,
        "probability_profit_risk_neutral": _rounded(probability_profit, 6),
        "expected_value_risk_neutral": _rounded(expected_value, 2),
        "expected_value_pct_of_max_loss": _rounded(expected_value_pct, 2),
        "model_edge_at_entry": _rounded(model_edge, 2),
        "greeks": ({key: net_greeks.get(key) for key in GREEK_KEYS} if net_greeks else None),
        "theoretical_value_per_share": net_greeks.get("theoretical_value") if net_greeks else None,
        "provider_greeks": None,
        "pricing_model": "BLACK_SCHOLES_MERTON" if net_greeks else None,
        "expected_value_model": "RISK_NEUTRAL_LOGNORMAL" if net_greeks else None,
        "contract_multiplier": multiplier,
    }


def analyze_long_volatility(
    call_contract: dict,
    put_contract: dict,
    *,
    spot: float,
    risk_free_rate: float,
    dividend_yield: float,
) -> dict | None:
    """Analytics for a long straddle/strangle using same-expiry contracts."""
    if (
        str(call_contract.get("option_type") or "").upper() != "CALL"
        or str(put_contract.get("option_type") or "").upper() != "PUT"
        or call_contract.get("expiration_date") != put_contract.get("expiration_date")
    ):
        return None
    call_strike = _finite(call_contract.get("strike"))
    put_strike = _finite(put_contract.get("strike"))
    time_years = _time_years(call_contract)
    if call_strike is None or put_strike is None or time_years is None:
        return None

    call_price, call_source = contract_entry_price(call_contract, "LONG")
    put_price, put_source = contract_entry_price(put_contract, "LONG")
    if call_price is None or put_price is None:
        return None
    debit = call_price + put_price
    multiplier = min(_multiplier(call_contract), _multiplier(put_contract))
    max_loss = debit * multiplier
    lower_breakeven = put_strike - debit
    upper_breakeven = call_strike + debit

    call_iv = _finite(call_contract.get("implied_volatility"))
    put_iv = _finite(put_contract.get("implied_volatility"))
    call_model = black_scholes_metrics(
        "CALL", spot, call_strike, time_years, call_iv,
        risk_free_rate, dividend_yield,
    ) if call_iv is not None else None
    put_model = black_scholes_metrics(
        "PUT", spot, put_strike, time_years, put_iv,
        risk_free_rate, dividend_yield,
    ) if put_iv is not None else None
    net_greeks = _combine_greeks(((call_model, 1.0), (put_model, 1.0)))

    probability_profit = expected_value = expected_value_pct = model_edge = None
    if call_model is not None and put_model is not None:
        probability_vol = (call_iv + put_iv) / 2.0
        below = terminal_probability(
            spot=spot, threshold=lower_breakeven, time_years=time_years,
            volatility=probability_vol, drift=risk_free_rate,
            dividend_yield=dividend_yield, above=False,
        )
        above = terminal_probability(
            spot=spot, threshold=upper_breakeven, time_years=time_years,
            volatility=probability_vol, drift=risk_free_rate,
            dividend_yield=dividend_yield, above=True,
        )
        probability_profit = min((below or 0.0) + (above or 0.0), 1.0)
        call_payoff = expected_option_payoff(
            "CALL", spot, call_strike, time_years, call_iv,
            risk_free_rate, dividend_yield,
        )
        put_payoff = expected_option_payoff(
            "PUT", spot, put_strike, time_years, put_iv,
            risk_free_rate, dividend_yield,
        )
        if call_payoff is not None and put_payoff is not None:
            financed_debit = debit * math.exp(risk_free_rate * time_years)
            expected_value = (call_payoff + put_payoff - financed_debit) * multiplier
            expected_value_pct = expected_value / max_loss * 100.0 if max_loss else None
        theoretical = _finite(net_greeks.get("theoretical_value")) if net_greeks else None
        if theoretical is not None:
            model_edge = (theoretical - debit) * multiplier

    is_straddle = abs(call_strike - put_strike) < 1e-9
    return {
        "strategy_type": "LONG_STRADDLE" if is_straddle else "LONG_STRANGLE",
        "strategy_name": "Long Straddle" if is_straddle else "Long Strangle",
        "direction": "VOLATILITY",
        "calculation_status": "COMPLETE" if net_greeks is not None else "PARTIAL",
        "legs": [
            _leg(call_contract, "LONG", call_price, call_source),
            _leg(put_contract, "LONG", put_price, put_source),
        ],
        "net_debit": _rounded(max_loss, 2),
        "net_debit_per_share": _rounded(debit),
        "breakevens": [_rounded(lower_breakeven), _rounded(upper_breakeven)],
        "max_loss": _rounded(max_loss, 2),
        "max_profit": None,
        "max_profit_unbounded": True,
        "probability_profit_risk_neutral": _rounded(probability_profit, 6),
        "expected_value_risk_neutral": _rounded(expected_value, 2),
        "expected_value_pct_of_max_loss": _rounded(expected_value_pct, 2),
        "model_edge_at_entry": _rounded(model_edge, 2),
        "greeks": ({key: net_greeks.get(key) for key in GREEK_KEYS} if net_greeks else None),
        "theoretical_value_per_share": net_greeks.get("theoretical_value") if net_greeks else None,
        "provider_greeks": None,
        "pricing_model": "BLACK_SCHOLES_MERTON" if net_greeks else None,
        "expected_value_model": "RISK_NEUTRAL_LOGNORMAL" if net_greeks else None,
        "contract_multiplier": multiplier,
    }
