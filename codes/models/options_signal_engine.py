"""Options signal engine (PROJECT_MAP.md — P4 expansion).

Models short-horizon option mark-to-market movement, not expiry payoff.

The model is deliberately read-only.  Network providers normalize live chains
before passing them here; absent or unusable chain data falls back to realized
volatility proxies without raising.
"""

from __future__ import annotations

import math
from datetime import date

import numpy as np
import pandas as pd

from codes.engine.scorer import verdict_for_score
from codes.models.options_pricing import analyze_long_contract, contract_entry_price
from codes.models.options_strategy import (
    CALIBRATED_RANKING_METHOD,
    UNCALIBRATED_RANKING_METHOD,
    build_ranked_strategy_candidates,
)

MONTHS_PER_YEAR = 12
DAYS_PER_YEAR = 365
DEFAULT_RISK_FREE_RATE = 0.045
EVENT_AWARENESS_MODEL = "PHASE_4_EVENT_AWARENESS_RULES"


# ══════════════════════════════════════════════════════════════════════════════
# Pure helpers
# ══════════════════════════════════════════════════════════════════════════════

def _clip(v, lo=0.0, hi=100.0):
    return max(lo, min(hi, v))


def _finite_float(v) -> float | None:
    try:
        f = float(v)
        return f if math.isfinite(f) else None
    except (TypeError, ValueError):
        return None


def _finite_int(v) -> int | None:
    number = _finite_float(v)
    if number is None or number < 0:
        return None
    return int(number)


def _price_series(price_hist: pd.DataFrame | None) -> pd.Series | None:
    """Return a clean, oldest-first price series for return calculations.

    Prefer ``AdjClose`` so splits and dividends do not distort momentum and
    realized volatility.  Fall back to ``Close`` for older callers.
    """
    if price_hist is None or price_hist.empty:
        return None

    hist = price_hist.copy()
    col = "AdjClose" if "AdjClose" in hist.columns else "Close"
    if col not in hist.columns:
        return None

    if "Date" in hist.columns:
        hist["Date"] = pd.to_datetime(hist["Date"], errors="coerce")
        hist = hist.dropna(subset=["Date"]).sort_values("Date")

    prices = pd.to_numeric(hist[col], errors="coerce")
    prices = prices[prices > 0].dropna()
    return prices.reset_index(drop=True) if len(prices) else None


def _norm_momentum(ret_pct: float | None) -> float | None:
    """Map a return (for example +0.10) to 0-100; +/-20% maps to 100/0."""
    ret_pct = _finite_float(ret_pct)
    if ret_pct is None:
        return None
    return _clip((ret_pct + 0.20) / 0.40 * 100.0)


def calc_momentum(price_hist: pd.DataFrame | None, lookback_months: int = 3) -> float | None:
    """Total return over the last ``lookback_months`` monthly closes."""
    closes = _price_series(price_hist)
    if closes is None or len(closes) < lookback_months + 1:
        return None
    start, end = closes.iloc[-(lookback_months + 1)], closes.iloc[-1]
    if start <= 0:
        return None
    ret = (end / start) - 1.0
    return float(ret) if math.isfinite(ret) else None


def calc_monthly_volatility(price_hist: pd.DataFrame | None) -> float | None:
    """Sample standard deviation of monthly log returns."""
    closes = _price_series(price_hist)
    if closes is None or len(closes) < 3:
        return None
    log_rets = np.log(closes / closes.shift(1)).dropna().values
    if len(log_rets) < 2:
        return None
    vol = float(np.std(log_rets, ddof=1))
    return vol if math.isfinite(vol) else None


def _signal(score: float) -> str:
    verdict, label, _description = verdict_for_score(score, enhanced=True)
    return f"{verdict}|{label}"


def _contract_days_to_expiry(contract: dict) -> int | None:
    raw_expiration = contract.get("expiration_date")
    if raw_expiration:
        try:
            return (date.fromisoformat(str(raw_expiration)[:10]) - date.today()).days
        except ValueError:
            pass
    return _finite_int(contract.get("days_to_expiry"))


def _contract_output(contract: dict | None) -> dict | None:
    """Return only the normalized contract fields safe for persisted output."""
    if not isinstance(contract, dict):
        return None
    keys = (
        "contract_symbol", "option_type", "expiration_date", "days_to_expiry",
        "strike", "bid", "ask", "mid", "spread_pct", "last_price", "volume",
        "open_interest", "implied_volatility", "delta", "gamma", "theta", "vega",
        "rho", "theoretical_value", "intrinsic_value", "time_value", "contract_size",
        "contract_multiplier", "currency", "in_the_money", "last_trade_at",
        "updated_at",
    )
    output = {key: contract.get(key) for key in keys}
    dte = _contract_days_to_expiry(contract)
    if dte is not None:
        output["days_to_expiry"] = dte
    return output


def _parse_calendar_date(value) -> date | None:
    if isinstance(value, date):
        return value
    if value is None:
        return None
    try:
        parsed = pd.to_datetime(value, errors="coerce")
    except (TypeError, ValueError):
        return None
    if pd.isna(parsed):
        return None
    return parsed.date()


def _event_severity(value) -> str:
    text = str(value or "NORMAL").upper().strip()
    if text in {"MAJOR", "HIGH", "CRITICAL", "FOMC", "CPI", "JOBS"}:
        return "MAJOR"
    if text in {"LOW", "MINOR"}:
        return "LOW"
    return "NORMAL"


# ══════════════════════════════════════════════════════════════════════════════
# OptionsSignalEngine
# ══════════════════════════════════════════════════════════════════════════════

class OptionsSignalEngine:
    """Build a directional options signal from stock, regime, and chain data.

    Args:
        ticker: Stock symbol.
        price_hist: Monthly Date/Close or Date/AdjClose history.
        regime_result: Output from ``codes.models.regime.score``.
        risk_result: Output from ``codes.models.risk_metrics.score``.
        current_price: Latest underlying price; falls back to history.
        option_chain: Normalized provider snapshot from
            ``codes.data.api_fetcher.get_options_chain``.
        risk_free_rate: Annual pricing rate as a decimal; falls back to the
            risk model and then 4.5%.
        dividend_yield: Annual continuous dividend yield as a decimal.
        event_calendar: Optional dict containing earnings, ex-dividend, and
            macro event dates.
        calibration_profile: Optional walk-forward ranking calibration profile.
    """

    def __init__(
        self,
        ticker: str,
        price_hist: pd.DataFrame | None = None,
        regime_result: dict | None = None,
        risk_result: dict | None = None,
        current_price: float | None = None,
        option_chain: dict | None = None,
        risk_free_rate: float | None = None,
        dividend_yield: float | None = None,
        event_calendar: dict | None = None,
        calibration_profile: dict | None = None,
    ):
        self.ticker = ticker.upper().strip()
        self.price_hist = price_hist
        self.regime_result = regime_result or {}
        self.risk_result = risk_result or {}
        self.option_chain = option_chain if isinstance(option_chain, dict) else {}
        self.event_calendar = event_calendar if isinstance(event_calendar, dict) else None
        self.calibration_profile = calibration_profile if isinstance(calibration_profile, dict) else None

        explicit_rate = _finite_float(risk_free_rate)
        risk_result_rate = _finite_float(self.risk_result.get("risk_free_rate"))
        if explicit_rate is not None and -0.05 <= explicit_rate <= 0.25:
            self.risk_free_rate = explicit_rate
            self.risk_free_rate_source = "EXPLICIT_INPUT"
        elif risk_result_rate is not None and -0.05 <= risk_result_rate <= 0.25:
            self.risk_free_rate = risk_result_rate
            self.risk_free_rate_source = "RISK_METRICS"
        else:
            self.risk_free_rate = DEFAULT_RISK_FREE_RATE
            self.risk_free_rate_source = "DEFAULT_ASSUMPTION"

        supplied_dividend = _finite_float(dividend_yield)
        if supplied_dividend is not None and 0 <= supplied_dividend <= 0.25:
            self.dividend_yield = supplied_dividend
            self.dividend_yield_source = "CAPITAL_ALLOCATION_OR_INPUT"
        else:
            self.dividend_yield = 0.0
            self.dividend_yield_source = "ZERO_FALLBACK"

        supplied_price = _finite_float(current_price)
        if supplied_price is not None and supplied_price > 0:
            self.current_price = supplied_price
        else:
            prices = _price_series(price_hist)
            self.current_price = _finite_float(prices.iloc[-1]) if prices is not None else None

    def pricing_assumptions(self) -> dict:
        """Expose model inputs and limitations used by Phase 3 calculations."""
        calibration_status = (
            self.calibration_profile.get("calibration_status")
            if isinstance(self.calibration_profile, dict)
            else "UNAVAILABLE"
        )
        ranking_method = (
            CALIBRATED_RANKING_METHOD
            if calibration_status == "CALIBRATED"
            else UNCALIBRATED_RANKING_METHOD
        )
        return {
            "pricing_model": "BLACK_SCHOLES_MERTON",
            "exercise_style_approximation": "EUROPEAN",
            "risk_free_rate": round(self.risk_free_rate, 6),
            "risk_free_rate_source": self.risk_free_rate_source,
            "dividend_yield": round(self.dividend_yield, 6),
            "dividend_yield_source": self.dividend_yield_source,
            "entry_pricing": "LONG_AT_ASK_SHORT_AT_BID_WITH_MID_LAST_FALLBACK",
            "expected_value_model": "RISK_NEUTRAL_LOGNORMAL_NOT_RETURN_FORECAST",
            "ranking_method": ranking_method,
            "calibration_status": calibration_status,
            "event_awareness_model": EVENT_AWARENESS_MODEL,
        }

    # ── Event awareness ─────────────────────────────────────────────────────

    def _calendar_events(self) -> tuple[str, list[dict]]:
        calendar = self.event_calendar
        if not isinstance(calendar, dict):
            return "UNAVAILABLE", []

        recognized = {
            "earnings_date", "next_earnings_date", "earnings_dates", "earnings",
            "ex_dividend_date", "next_ex_dividend_date", "ex_dividend_dates",
            "dividends", "macro_events", "major_macro_events",
        }
        if not any(key in calendar for key in recognized):
            return "UNAVAILABLE", []

        events: list[dict] = []

        def add_event(raw, event_type: str, default_name: str, default_severity: str = "NORMAL"):
            if raw is None:
                return
            if isinstance(raw, (list, tuple)):
                for item in raw:
                    add_event(item, event_type, default_name, default_severity)
                return
            if isinstance(raw, dict):
                event_date = _parse_calendar_date(
                    raw.get("date")
                    or raw.get("event_date")
                    or raw.get("earnings_date")
                    or raw.get("ex_dividend_date")
                )
                name = raw.get("name") or raw.get("event") or raw.get("title") or default_name
                severity = _event_severity(raw.get("severity") or default_severity)
            else:
                event_date = _parse_calendar_date(raw)
                name = default_name
                severity = _event_severity(default_severity)
            if event_date is None:
                return
            events.append({
                "type": event_type,
                "name": str(name),
                "date": event_date.isoformat(),
                "severity": severity,
            })

        add_event(calendar.get("earnings_date"), "EARNINGS", "Earnings", "MAJOR")
        add_event(calendar.get("next_earnings_date"), "EARNINGS", "Earnings", "MAJOR")
        add_event(calendar.get("earnings_dates"), "EARNINGS", "Earnings", "MAJOR")
        add_event(calendar.get("earnings"), "EARNINGS", "Earnings", "MAJOR")
        add_event(calendar.get("ex_dividend_date"), "EX_DIVIDEND", "Ex-dividend", "NORMAL")
        add_event(calendar.get("next_ex_dividend_date"), "EX_DIVIDEND", "Ex-dividend", "NORMAL")
        add_event(calendar.get("ex_dividend_dates"), "EX_DIVIDEND", "Ex-dividend", "NORMAL")
        add_event(calendar.get("dividends"), "EX_DIVIDEND", "Ex-dividend", "NORMAL")
        add_event(calendar.get("macro_events"), "MACRO", "Macro event", "NORMAL")
        add_event(calendar.get("major_macro_events"), "MACRO", "Macro event", "MAJOR")

        unique = {}
        for event in events:
            unique[(event["type"], event["date"], event["name"])] = event
        return "AVAILABLE", sorted(unique.values(), key=lambda item: (item["date"], item["type"]))

    def calc_event_risk(self, horizon_days: int = 30, bias: str = "NEUTRAL") -> dict:
        """Return event risk and whether new option entries should be suppressed."""
        coverage, events = self._calendar_events()
        if coverage == "UNAVAILABLE":
            return {
                "coverage": "UNAVAILABLE",
                "model": EVENT_AWARENESS_MODEL,
                "risk_score": 0.0,
                "risk_level": "UNKNOWN",
                "events": [],
                "entry_suppressed": False,
                "suppression_reasons": [],
            }

        horizon = max(1, int(horizon_days))
        today = date.today()
        relevant = []
        risk_score = 0.0
        suppression_reasons = []

        for event in events:
            event_date = _parse_calendar_date(event.get("date"))
            if event_date is None:
                continue
            days_until = (event_date - today).days
            if days_until < 0 or days_until > horizon:
                continue

            event_risk = 25.0
            suppress = False
            if event["type"] == "EARNINGS":
                event_risk = 95.0 if days_until <= 5 else 65.0
                suppress = days_until <= 5
            elif event["type"] == "EX_DIVIDEND":
                event_risk = 75.0 if bias == "CALL" and days_until <= 3 else 45.0
                suppress = bias == "CALL" and days_until <= 3
            elif event["type"] == "MACRO":
                major = event.get("severity") == "MAJOR"
                event_risk = 90.0 if major and days_until <= 2 else 60.0 if major else 40.0
                suppress = major and days_until <= 2

            enriched = dict(event)
            enriched.update({
                "days_until": days_until,
                "risk_score": round(event_risk, 1),
                "entry_suppressed": suppress,
            })
            relevant.append(enriched)
            risk_score = max(risk_score, event_risk)
            if suppress:
                suppression_reasons.append(
                    f"{event['type']} within {days_until}d"
                )

        if risk_score >= 75:
            risk_level = "HIGH"
        elif risk_score >= 50:
            risk_level = "MODERATE"
        elif risk_score > 0:
            risk_level = "LOW"
        else:
            risk_level = "LOW"

        return {
            "coverage": "AVAILABLE",
            "model": EVENT_AWARENESS_MODEL,
            "risk_score": round(risk_score, 1),
            "risk_level": risk_level,
            "events": relevant,
            "entry_suppressed": bool(suppression_reasons),
            "suppression_reasons": suppression_reasons,
        }

    # ── Directional bias ────────────────────────────────────────────────────

    def calc_directional_bias(self) -> tuple[str, float]:
        """Return CALL/PUT/NEUTRAL and confidence from trend plus momentum."""
        trend_score = _finite_float(self.regime_result.get("market_trend_score"))
        mom_score = _norm_momentum(calc_momentum(self.price_hist))

        parts = []
        if trend_score is not None:
            parts.append((trend_score, 0.6))
        if mom_score is not None:
            parts.append((mom_score, 0.4))
        if not parts:
            return "NEUTRAL", 0.0

        total_weight = sum(weight for _, weight in parts)
        combined = sum(value * weight for value, weight in parts) / total_weight
        if combined >= 60:
            bias = "CALL"
        elif combined <= 40:
            bias = "PUT"
        else:
            bias = "NEUTRAL"
        return bias, round(_clip(abs(combined - 50) * 2), 1)

    # ── Volatility and IV regime ────────────────────────────────────────────

    def calc_realized_annual_volatility(self) -> float | None:
        monthly = calc_monthly_volatility(self.price_hist)
        if monthly is None:
            return None
        return monthly * math.sqrt(MONTHS_PER_YEAR)

    def calc_iv_vs_realized_ratio(self, implied_volatility: float | None) -> float | None:
        iv = _finite_float(implied_volatility)
        realized = self.calc_realized_annual_volatility()
        # Treat sub-1% estimates as numerically uninformative rather than
        # producing an enormous IV/RV ratio for near-constant price histories.
        if iv is None or iv <= 0 or realized is None or realized <= 0.01:
            return None
        return round(iv / realized, 4)

    def calc_iv_regime(self, implied_volatility: float | None = None) -> tuple[str, str]:
        """Return volatility level and trend with an honest source boundary.

        With a valid contract IV, level compares true annualized IV with the
        underlying's annualized realized volatility.  One chain snapshot cannot
        establish a time trend, so trend is ``UNKNOWN``.  Without chain IV, the
        existing market realized-volatility proxy is used for compatibility.
        """
        iv = _finite_float(implied_volatility)
        if iv is not None and iv > 0:
            ratio = self.calc_iv_vs_realized_ratio(iv)
            if ratio is not None:
                if ratio >= 1.25:
                    level = "HIGH"
                elif ratio <= 0.85:
                    level = "LOW"
                else:
                    level = "NORMAL"
            elif iv >= 0.50:
                level = "HIGH"
            elif iv <= 0.25:
                level = "LOW"
            else:
                level = "NORMAL"
            return level, "UNKNOWN"

        vol_pct = _finite_float(self.regime_result.get("volatility_percentile"))
        if vol_pct is None:
            level = "UNKNOWN"
        elif vol_pct >= 75:
            level = "HIGH"
        elif vol_pct <= 25:
            level = "LOW"
        else:
            level = "NORMAL"

        vol_20d = _finite_float(self.regime_result.get("vol_20d"))
        vol_60d = _finite_float(self.regime_result.get("vol_60d"))
        if vol_20d is not None and vol_60d is not None and vol_60d > 0:
            ratio = vol_20d / vol_60d
            if ratio >= 1.15:
                trend = "EXPANDING"
            elif ratio <= 0.85:
                trend = "CONTRACTING"
            else:
                trend = "STABLE"
        else:
            trend = "UNKNOWN"
        return level, trend

    # ── Expected move ────────────────────────────────────────────────────────

    def calc_expected_move(
        self,
        horizon_days: int = 30,
        implied_volatility: float | None = None,
    ) -> tuple[float | None, float | None]:
        """Return one-standard-deviation move over ``horizon_days``.

        True annualized contract IV is preferred.  The fallback scales monthly
        realized volatility, preserving the pre-chain behavior.
        """
        days = max(1, int(horizon_days))
        iv = _finite_float(implied_volatility)
        if iv is not None and iv > 0:
            move_pct = iv * math.sqrt(days / DAYS_PER_YEAR)
        else:
            monthly_vol = calc_monthly_volatility(self.price_hist)
            if monthly_vol is None:
                return None, None
            move_pct = monthly_vol * math.sqrt(days / 30.0)

        move_dollar = self.current_price * move_pct if self.current_price is not None else None
        return round(move_pct, 4), round(move_dollar, 2) if move_dollar is not None else None

    # ── Contract selection ──────────────────────────────────────────────────

    def recommend_strike_expiry(
        self,
        bias: str,
        move_pct: float | None,
        horizon_days: int = 30,
    ) -> dict:
        """Return the theoretical target used when no listed contract exists."""
        if self.current_price is None or move_pct is None or bias == "NEUTRAL":
            strike = self.current_price
        elif bias == "CALL":
            strike = self.current_price * (1 + 0.5 * move_pct)
        else:
            strike = self.current_price * (1 - 0.5 * move_pct)
        return {
            "strike": round(strike, 2) if strike is not None else None,
            "expiry_days": max(1, int(horizon_days)),
        }

    def _chain_contracts(self) -> list[dict]:
        chain_symbol = str(self.option_chain.get("symbol") or "").upper().strip()
        if chain_symbol and chain_symbol != self.ticker:
            return []
        rows = self.option_chain.get("contracts")
        if not isinstance(rows, list):
            return []

        contracts = []
        for row in rows:
            if not isinstance(row, dict):
                continue
            option_type = str(row.get("option_type") or "").upper()
            strike = _finite_float(row.get("strike"))
            dte = _contract_days_to_expiry(row)
            if option_type not in {"CALL", "PUT"} or strike is None or strike <= 0:
                continue
            if dte is None or dte <= 0:
                continue
            normalized = dict(row)
            normalized["option_type"] = option_type
            normalized["strike"] = strike
            normalized["days_to_expiry"] = dte
            contracts.append(normalized)
        return contracts

    def calc_liquidity_risk(self, contract: dict | None = None) -> float:
        """0-100 execution risk from spread, open interest, and volume."""
        if not isinstance(contract, dict):
            return 50.0

        spread = _finite_float(contract.get("spread_pct"))
        if spread is not None and spread < 0:
            spread = None
        if spread is None:
            bid = _finite_float(contract.get("bid"))
            ask = _finite_float(contract.get("ask"))
            if bid is not None and ask is not None and ask >= bid and ask > 0:
                mid = (bid + ask) / 2.0
                spread = (ask - bid) / mid if mid > 0 else None
        spread_risk = 90.0 if spread is None else _clip((spread - 0.05) / 0.45 * 100.0)

        open_interest = _finite_int(contract.get("open_interest"))
        if open_interest is None or open_interest == 0:
            oi_risk = 90.0
        elif open_interest >= 1000:
            oi_risk = 0.0
        elif open_interest >= 500:
            oi_risk = 15.0
        elif open_interest >= 100:
            oi_risk = 40.0
        elif open_interest >= 25:
            oi_risk = 65.0
        else:
            oi_risk = 80.0

        volume = _finite_int(contract.get("volume"))
        if volume is None or volume == 0:
            volume_risk = 90.0
        elif volume >= 500:
            volume_risk = 0.0
        elif volume >= 100:
            volume_risk = 20.0
        elif volume >= 25:
            volume_risk = 45.0
        else:
            volume_risk = 70.0

        return round(spread_risk * 0.50 + oi_risk * 0.30 + volume_risk * 0.20, 1)

    def select_contract(
        self,
        bias: str,
        target_strike: float | None,
        horizon_days: int = 30,
    ) -> dict | None:
        """Select the nearest-expiry/strike contract with liquidity tie-breaks."""
        contracts = self._chain_contracts()
        if bias in {"CALL", "PUT"}:
            contracts = [row for row in contracts if row["option_type"] == bias]
        if not contracts:
            return None

        horizon = max(1, int(horizon_days))
        chosen_expiry = min(
            {row["days_to_expiry"] for row in contracts},
            key=lambda dte: (abs(dte - horizon), dte < horizon, dte),
        )
        expiry_candidates = [
            row for row in contracts
            if row["days_to_expiry"] == chosen_expiry
        ]
        executable_candidates = [
            row for row in expiry_candidates
            if contract_entry_price(row, "LONG")[0] is not None
        ]
        if executable_candidates:
            expiry_candidates = executable_candidates

        target = _finite_float(target_strike)
        if target is None:
            target = self.current_price
        if target is None:
            target = float(np.median([row["strike"] for row in expiry_candidates]))

        return min(
            expiry_candidates,
            key=lambda row: (
                abs(row["strike"] - target),
                _finite_float(row.get("implied_volatility")) is None,
                self.calc_liquidity_risk(row),
                -(_finite_int(row.get("open_interest")) or 0),
                -(_finite_int(row.get("volume")) or 0),
            ),
        )

    # ── Risk and edge ───────────────────────────────────────────────────────

    def calc_risk_score(
        self,
        iv_level: str,
        horizon_days: int = 30,
        contract: dict | None = None,
    ) -> float:
        """0-100; higher is riskier for an option buyer."""
        if horizon_days <= 14:
            theta_risk = 80
        elif horizon_days <= 45:
            theta_risk = 50
        else:
            theta_risk = 25

        iv_risk = {"HIGH": 80, "NORMAL": 50, "LOW": 20}.get(iv_level, 50)
        liquidity_risk = self.calc_liquidity_risk(contract)

        underlying_score = _finite_float(self.risk_result.get("risk_score"))
        underlying_max = _finite_float(self.risk_result.get("risk_score_max")) or 100.0
        if underlying_score is None or underlying_max <= 0:
            underlying_risk = 50.0
        else:
            underlying_risk = 100.0 - _clip(underlying_score / underlying_max * 100.0)

        return round(
            theta_risk * 0.30
            + iv_risk * 0.30
            + liquidity_risk * 0.20
            + underlying_risk * 0.20,
            1,
        )

    def calc_edge_score(self, bias_confidence: float, iv_level: str, iv_trend: str) -> float:
        """Directional confidence adjusted for option-premium favorability."""
        if iv_level == "LOW" or iv_trend == "CONTRACTING":
            factor = 1.2
        elif iv_level == "HIGH" or iv_trend == "EXPANDING":
            factor = 0.7
        else:
            factor = 1.0
        return round(_clip(bias_confidence * factor), 1)

    def calc_data_quality_score(self, contract: dict | None = None) -> float:
        """0-100 completeness score including live-chain evidence."""
        points = 0.0
        total = 125.0

        if self.price_hist is not None and not self.price_hist.empty and _price_series(self.price_hist) is not None:
            points += 30
        if _finite_float(self.regime_result.get("market_trend_score")) is not None:
            points += 25
        if _finite_float(self.regime_result.get("volatility_percentile")) is not None:
            points += 15
        if (
            _finite_float(self.regime_result.get("vol_20d")) is not None
            and _finite_float(self.regime_result.get("vol_60d")) is not None
        ):
            points += 10
        if _finite_float(self.risk_result.get("risk_score")) is not None:
            points += 20

        contracts = self._chain_contracts()
        if contracts:
            points += 5
        if isinstance(contract, dict):
            if contract.get("expiration_date") and _finite_float(contract.get("strike")) is not None:
                points += 5
            if _finite_float(contract.get("implied_volatility")) is not None:
                points += 5
            if _finite_float(contract.get("bid")) is not None and _finite_float(contract.get("ask")) is not None:
                points += 5
            if _finite_int(contract.get("open_interest")) is not None and _finite_int(contract.get("volume")) is not None:
                points += 5

        return round(_clip(points / total * 100.0), 1)

    # ── Main entry point ─────────────────────────────────────────────────────

    def get_options_signal(self, horizon_days: int = 30) -> dict:
        horizon = max(1, int(horizon_days))
        bias, confidence = self.calc_directional_bias()
        proxy_level, proxy_trend = self.calc_iv_regime()

        proxy_move_pct, _ = self.calc_expected_move(horizon)
        theoretical = self.recommend_strike_expiry(bias, proxy_move_pct, horizon)
        contract = self.select_contract(bias, theoretical["strike"], horizon)

        implied_volatility = (
            _finite_float(contract.get("implied_volatility"))
            if isinstance(contract, dict)
            else None
        )
        if implied_volatility is not None and implied_volatility > 0:
            # One refinement pass: IV-derived expected move may point to a
            # different listed strike than the realized-volatility proxy did.
            true_move_pct, _ = self.calc_expected_move(horizon, implied_volatility)
            refined_target = self.recommend_strike_expiry(bias, true_move_pct, horizon)
            refined = self.select_contract(bias, refined_target["strike"], horizon)
            refined_iv = _finite_float(refined.get("implied_volatility")) if refined else None
            if refined is not None and refined_iv is not None and refined_iv > 0:
                contract = refined
                implied_volatility = refined_iv

        has_true_iv = implied_volatility is not None and implied_volatility > 0
        if has_true_iv:
            iv_level, iv_trend = self.calc_iv_regime(implied_volatility)
            move_pct, move_dollar = self.calc_expected_move(horizon, implied_volatility)
        else:
            iv_level, iv_trend = proxy_level, proxy_trend
            move_pct, move_dollar = self.calc_expected_move(horizon)

        if contract is not None:
            strike_info = {
                "strike": _finite_float(contract.get("strike")),
                "expiry_days": _contract_days_to_expiry(contract) or horizon,
                "expiration_date": contract.get("expiration_date"),
            }
        else:
            strike_info = {
                **self.recommend_strike_expiry(bias, move_pct, horizon),
                "expiration_date": None,
            }

        provider = str(self.option_chain.get("provider") or "").upper().strip() or None
        chain_status = str(self.option_chain.get("status") or "UNAVAILABLE").upper()
        if has_true_iv:
            chain_source = f"{provider or 'OPTION'}_OPTION_CHAIN"
            if chain_status == "STALE":
                chain_source += "_STALE"
            iv_source = chain_source
            expected_move_source = "IMPLIED_VOLATILITY"
        else:
            iv_source = "REALIZED_VOL_PROXY"
            expected_move_source = "REALIZED_VOLATILITY"

        risk_score = self.calc_risk_score(iv_level, strike_info["expiry_days"], contract)
        liquidity_risk = self.calc_liquidity_risk(contract)
        edge_score = self.calc_edge_score(confidence, iv_level, iv_trend)
        data_quality_score = self.calc_data_quality_score(contract)
        event_risk = self.calc_event_risk(horizon, bias)
        if event_risk["coverage"] == "AVAILABLE":
            risk_score = round(_clip(risk_score * 0.80 + event_risk["risk_score"] * 0.20), 1)

        selected_contract_analytics = None
        if contract is not None and self.current_price is not None:
            selected_contract_analytics = analyze_long_contract(
                contract,
                spot=self.current_price,
                risk_free_rate=self.risk_free_rate,
                dividend_yield=self.dividend_yield,
            )

        strategy_candidates = []
        if self.current_price is not None:
            strategy_candidates = build_ranked_strategy_candidates(
                self._chain_contracts(),
                spot=self.current_price,
                horizon_days=horizon,
                expected_move_dollar=move_dollar,
                bias=bias,
                confidence=confidence,
                iv_level=iv_level,
                risk_free_rate=self.risk_free_rate,
                dividend_yield=self.dividend_yield,
                liquidity_risk=self.calc_liquidity_risk,
                calibration_profile=self.calibration_profile,
            )
        top_strategy = strategy_candidates[0] if strategy_candidates else None
        if top_strategy:
            strategy_label = str(top_strategy.get("ranking_label") or "balanced")
            strategy_signal = (
                f"{strategy_label.upper().replace('-', '_')}_"
                f"{top_strategy['strategy_type']}"
            )
        else:
            strategy_signal = "NO_STRATEGY"

        if bias == "NEUTRAL":
            signal = "NO_TRADE"
        else:
            verdict, label = _signal(edge_score).split("|", 1)
            if label in {"high-conviction", "favorable"}:
                signal = f"{label.upper().replace('-', '_')}_{bias}"
            else:
                signal = verdict

        if event_risk["entry_suppressed"] and signal != "NO_TRADE":
            signal = "EVENT_RISK_SUPPRESSED"
            strategy_signal = "EVENT_RISK_SUPPRESSED"

        normalized_contract = _contract_output(contract)
        primary_analytics = top_strategy or selected_contract_analytics or {}
        strategy_ranking_method = (
            top_strategy.get("ranking_method")
            if top_strategy
            else self.pricing_assumptions()["ranking_method"]
        )
        total_score = top_strategy.get("ranking_score") if top_strategy else edge_score
        if event_risk["entry_suppressed"]:
            total_score = min(total_score, 39.0)
        return {
            "ticker": self.ticker,
            "bias": bias,
            "bias_confidence": confidence,
            "iv_level": iv_level,
            "iv_trend": iv_trend,
            "implied_volatility": round(implied_volatility, 6) if has_true_iv else None,
            "iv_vs_realized_ratio": self.calc_iv_vs_realized_ratio(implied_volatility),
            "vol_proxy_level": proxy_level,
            "vol_proxy_trend": proxy_trend,
            "volatility_source": iv_source,
            "iv_source": iv_source,
            "expected_move_source": expected_move_source,
            "expected_move_pct": move_pct,
            "expected_move_dollar": move_dollar,
            "target_horizon_days": horizon,
            "recommended_strike": strike_info["strike"],
            "recommended_expiry_days": strike_info["expiry_days"],
            "recommended_expiration_date": strike_info["expiration_date"],
            "recommended_contract_symbol": (
                normalized_contract.get("contract_symbol") if normalized_contract else None
            ),
            "contract_role": "CANDIDATE" if bias in {"CALL", "PUT"} else "REFERENCE",
            "selected_contract": normalized_contract,
            "selected_contract_analytics": selected_contract_analytics,
            "pricing_assumptions": self.pricing_assumptions(),
            "strategy_candidates": strategy_candidates,
            "strategy_count": len(strategy_candidates),
            "top_strategy": top_strategy,
            "recommended_strategy": top_strategy.get("strategy_type") if top_strategy else None,
            "strategy_signal": strategy_signal,
            "strategy_ranking_method": strategy_ranking_method,
            "calibration_status": (
                self.calibration_profile.get("calibration_status")
                if isinstance(self.calibration_profile, dict)
                else "UNAVAILABLE"
            ),
            "event_risk": event_risk,
            "event_coverage": event_risk["coverage"],
            "event_entry_suppressed": event_risk["entry_suppressed"],
            "event_suppression_reasons": event_risk["suppression_reasons"],
            "greeks": primary_analytics.get("greeks"),
            "breakevens": primary_analytics.get("breakevens") or [],
            "max_loss": primary_analytics.get("max_loss"),
            "max_profit": primary_analytics.get("max_profit"),
            "max_profit_unbounded": bool(primary_analytics.get("max_profit_unbounded")),
            "expected_value_risk_neutral": primary_analytics.get("expected_value_risk_neutral"),
            "probability_profit_risk_neutral": primary_analytics.get("probability_profit_risk_neutral"),
            "chain_provider": provider,
            "chain_status": chain_status,
            "chain_fetched_at": self.option_chain.get("fetched_at"),
            "contract_count": len(self._chain_contracts()),
            "liquidity_risk": liquidity_risk,
            "risk_score": risk_score,
            "edge_score": edge_score,
            "data_quality_score": data_quality_score,
            "signal": signal,
            "total_score": total_score,
            "total_max": 100.0,
        }


def get_options_signal(
    ticker: str,
    price_hist: pd.DataFrame | None = None,
    regime_result: dict | None = None,
    risk_result: dict | None = None,
    current_price: float | None = None,
    horizon_days: int = 30,
    option_chain: dict | None = None,
    risk_free_rate: float | None = None,
    dividend_yield: float | None = None,
    event_calendar: dict | None = None,
    calibration_profile: dict | None = None,
) -> dict:
    """Module-level convenience wrapper used by the analysis pipeline."""
    return OptionsSignalEngine(
        ticker=ticker,
        price_hist=price_hist,
        regime_result=regime_result,
        risk_result=risk_result,
        current_price=current_price,
        option_chain=option_chain,
        risk_free_rate=risk_free_rate,
        dividend_yield=dividend_yield,
        event_calendar=event_calendar,
        calibration_profile=calibration_profile,
    ).get_options_signal(horizon_days)
