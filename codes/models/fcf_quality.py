"""
Free Cash Flow Quality Model — P1 module.

Measures earnings quality and cash generation durability using up to 10
years of operating cash flow and capex history.

Metrics & weights:
  FCF Margin              25%  — FCF / Revenue (cash profitability)
  FCF Conversion          25%  — FCF / Net Income (how much profit becomes cash)
  FCF Stability           20%  — coefficient of variation of FCF margin (lower = better)
  FCF Growth Consistency  15%  — fraction of years with positive YoY FCF growth
  Accrual Ratio           15%  — (Net Income − OCF) / avg Total Assets (lower = better)

All metrics use up to 10 years of annual data.

Signal mapping:
  >= 80  → STRONG_CASH_GENERATOR
  65–79  → HIGH_CASH_QUALITY
  45–64  → NEUTRAL
  30–44  → WEAK_CASH_QUALITY
  < 30   → EARNINGS_QUALITY_RISK

Output schema (strict — no extra keys):
  {
    "ticker":                 str,
    "fcf":                    float | None,
    "operating_cash_flow":    float | None,
    "capex":                  float | None,
    "fcf_margin":             float | None,
    "fcf_conversion":         float | None,
    "fcf_stability":          float | None,
    "fcf_growth_consistency": float | None,
    "accrual_ratio":          float | None,
    "fcf_cagr_5y":            float | None,
    "fcf_quality_score":      float,
    "signal":                 str,
    "total_score":            float,    # scorer.py compat
    "total_max":              float,    # scorer.py compat (100.0)
  }

Integration:
  from codes.models.fcf_quality import FCFQualityAnalyzer
  result = FCFQualityAnalyzer(ticker, sec_facts).get_fcf_quality_score()
  Composite weight: 10%
"""

from __future__ import annotations

import math
import statistics
from typing import Any


# ── Helpers ───────────────────────────────────────────────────────────────────

def _safe(val: Any) -> float | None:
    try:
        v = float(val)
        return v if math.isfinite(v) else None
    except (TypeError, ValueError):
        return None


def _first(records: list) -> float | None:
    for r in records:
        v = _safe(r.get("value"))
        if v is not None:
            return v
    return None


def _values(records: list, n: int = 10) -> list[float]:
    """Return up to n most-recent non-None values, newest first."""
    out: list[float] = []
    for r in records:
        v = _safe(r.get("value"))
        if v is not None:
            out.append(v)
            if len(out) >= n:
                break
    return out


def _clamp(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))


# ── Signal mapping ────────────────────────────────────────────────────────────

def _signal(score: float) -> str:
    if score >= 80:
        return "STRONG_CASH_GENERATOR"
    if score >= 65:
        return "HIGH_CASH_QUALITY"
    if score >= 45:
        return "NEUTRAL"
    if score >= 30:
        return "WEAK_CASH_QUALITY"
    return "EARNINGS_QUALITY_RISK"


# ── Normalisation helpers ─────────────────────────────────────────────────────

def _norm_fcf_margin(margin_pct: float | None) -> float:
    """
    FCF margin (%). Exceptional ≥ 20%, zero at ≤ 0%.
    Negative FCF margin → 0 (cash-consuming business).
    """
    if margin_pct is None:
        return 0.0
    if margin_pct >= 20.0:
        return 100.0
    if margin_pct <= 0.0:
        return 0.0
    return _clamp(margin_pct / 20.0 * 100, 0, 100)


def _norm_fcf_conversion(conversion: float | None) -> float:
    """
    FCF conversion = FCF / Net Income (%).
    ≥ 100% → 100 (business generates more cash than accounting profit).
    ≤ 0%   → 0.
    """
    if conversion is None:
        return 50.0  # neutral when net income missing/zero
    if conversion >= 100.0:
        return 100.0
    if conversion <= 0.0:
        return 0.0
    return _clamp(conversion, 0, 100)


def _norm_fcf_stability(cv: float | None) -> float:
    """
    Coefficient of variation of FCF margin (lower = more stable = higher score).
    CV ≤ 0.20 → 100 (very stable).
    CV ≥ 1.00 → 0   (highly volatile).
    Neutral (50) when fewer than 3 periods available.
    """
    if cv is None:
        return 50.0
    if cv <= 0.20:
        return 100.0
    if cv >= 1.00:
        return 0.0
    return _clamp((1.00 - cv) / 0.80 * 100, 0, 100)


def _norm_fcf_growth_consistency(frac: float | None) -> float:
    """
    Fraction of years with positive YoY FCF growth (0-1).
    1.0 → 100, 0.0 → 0.
    Neutral (50) when fewer than 3 periods.
    """
    if frac is None:
        return 50.0
    return _clamp(frac * 100, 0, 100)


def _norm_accrual_ratio(ar: float | None) -> float:
    """
    Accrual ratio = (Net Income − OCF) / avg Total Assets.
    Lower (more negative) = higher earnings quality = higher score.
    ar ≤ -0.05 → 100 (cash earnings well exceed accounting earnings).
    ar ≥  0.10 → 0   (accounting earnings exceed cash earnings — low quality).
    Neutral (50) when data unavailable.
    """
    if ar is None:
        return 50.0
    if ar <= -0.05:
        return 100.0
    if ar >= 0.10:
        return 0.0
    # Linear interpolation from 0.10 → 0 to -0.05 → 100
    return _clamp((0.10 - ar) / 0.15 * 100, 0, 100)


# ── Class ─────────────────────────────────────────────────────────────────────

class FCFQualityAnalyzer:
    """
    Compute FCF quality score from SEC financials.

    Args:
        ticker:     Stock ticker (stored in output, not used for fetching).
        financials: sec_facts dict as returned by sec_data.fetch_company_facts().
    """

    # Component weights (must sum to 1.0)
    _WEIGHTS = {
        "fcf_margin":             0.25,
        "fcf_conversion":         0.25,
        "fcf_stability":          0.20,
        "fcf_growth_consistency": 0.15,
        "accrual_ratio":          0.15,
    }

    def __init__(self, ticker: str, financials: dict) -> None:
        self.ticker = ticker.upper().strip()
        self._f = financials

        # Pre-compute FCF series (newest first, up to 10 years)
        self._fcf_series: list[float] = self._build_fcf_series()

    # ── FCF series builder ────────────────────────────────────────────────────

    def _build_fcf_series(self) -> list[float]:
        """
        FCF = Operating Cash Flow − abs(CapEx), newest first, up to 10 years.
        Years where either value is missing are excluded.
        """
        op_cf_vals = _values(self._f.get("op_cf",   []), n=10)
        capex_vals = _values(self._f.get("capex",   []), n=10)

        n = min(len(op_cf_vals), len(capex_vals))
        return [op_cf_vals[i] - abs(capex_vals[i]) for i in range(n)]

    # ── Raw metric calculators ────────────────────────────────────────────────

    def calc_fcf(self) -> float | None:
        """Most recent annual FCF."""
        return self._fcf_series[0] if self._fcf_series else None

    def calc_fcf_margin(self) -> float | None:
        """
        FCF Margin = FCF / Revenue (%), most recent year.
        """
        fcf     = self.calc_fcf()
        revenue = _first(self._f.get("revenue", []))
        if fcf is None or revenue is None or revenue <= 0:
            return None
        return fcf / revenue * 100

    def calc_fcf_conversion(self) -> float | None:
        """
        FCF Conversion = FCF / Net Income (%).
        Represents how much accounting profit translates to real cash.
        Returns None when net income is zero or missing.
        """
        fcf     = self.calc_fcf()
        net_inc = _first(self._f.get("net_inc", []))
        if fcf is None or net_inc is None or abs(net_inc) < 1:
            return None
        return fcf / net_inc * 100

    def calc_fcf_stability(self) -> float | None:
        """
        Coefficient of variation of FCF Margin across up to 10 years.
        CV = std(FCF margins) / |mean(FCF margins)|.
        Returns None when fewer than 3 periods available.
        """
        op_cf_vals  = _values(self._f.get("op_cf",   []), n=10)
        capex_vals  = _values(self._f.get("capex",   []), n=10)
        revenue_vals = _values(self._f.get("revenue", []), n=10)

        n = min(len(op_cf_vals), len(capex_vals), len(revenue_vals))
        if n < 3:
            return None

        margins = []
        for i in range(n):
            rev = revenue_vals[i]
            if rev and rev > 0:
                fcf = op_cf_vals[i] - abs(capex_vals[i])
                margins.append(fcf / rev * 100)

        if len(margins) < 3:
            return None

        mean_abs = abs(sum(margins) / len(margins))
        if mean_abs < 1e-6:
            return None  # near-zero mean → CV undefined

        std = statistics.stdev(margins)
        return std / mean_abs  # CV (dimensionless)

    def calc_fcf_growth_consistency(self) -> float | None:
        """
        Fraction of years (0-1) with positive YoY FCF growth.
        Requires at least 3 years of FCF data.
        """
        series = self._fcf_series  # newest first
        if len(series) < 3:
            return None

        # Compare consecutive years: series[i] vs series[i+1] (older)
        up_years = 0
        total = 0
        for i in range(len(series) - 1):
            total += 1
            if series[i] > series[i + 1]:
                up_years += 1

        return up_years / total if total > 0 else None

    def calc_accrual_ratio(self) -> float | None:
        """
        Sloan Accrual Ratio = (Net Income − OCF) / avg Total Assets.
        Uses the two most recent years to compute average total assets.
        Lower (more negative) = higher earnings quality.
        """
        net_inc    = _first(self._f.get("net_inc",       []))
        ocf        = _first(self._f.get("op_cf",         []))
        ta_vals    = _values(self._f.get("total_assets",  []), n=2)

        if net_inc is None or ocf is None:
            return None
        if len(ta_vals) < 1:
            return None

        avg_assets = sum(ta_vals) / len(ta_vals)
        if avg_assets <= 0:
            return None

        return (net_inc - ocf) / avg_assets

    def calc_fcf_cagr_5y(self) -> float | None:
        """
        5-year FCF CAGR (annualised growth rate).
        Requires at least 5 years of FCF data.
        Only computed when both start and end FCF are positive.
        """
        series = self._fcf_series  # newest first
        if len(series) < 5:
            return None

        end_fcf   = series[0]    # most recent
        start_fcf = series[4]    # 5 years ago (index 4)

        if start_fcf <= 0 or end_fcf <= 0:
            return None

        return (math.pow(end_fcf / start_fcf, 1 / 5) - 1) * 100

    # ── Composite score ───────────────────────────────────────────────────────

    def get_fcf_quality_score(self) -> dict:
        """
        Compute and return a strict JSON-compatible dict with exactly these keys:

          ticker, fcf, operating_cash_flow, capex, fcf_margin, fcf_conversion,
          fcf_stability, fcf_growth_consistency, accrual_ratio, fcf_cagr_5y,
          fcf_quality_score, signal, total_score, total_max
        """
        fcf         = self.calc_fcf()
        ocf         = _first(self._f.get("op_cf",  []))
        capex_raw   = _first(self._f.get("capex",  []))
        fcf_margin  = self.calc_fcf_margin()
        fcf_conv    = self.calc_fcf_conversion()
        fcf_stab    = self.calc_fcf_stability()
        fcf_growth  = self.calc_fcf_growth_consistency()
        accrual     = self.calc_accrual_ratio()
        fcf_cagr    = self.calc_fcf_cagr_5y()

        # Normalised sub-scores
        n_margin  = _norm_fcf_margin(fcf_margin)
        n_conv    = _norm_fcf_conversion(fcf_conv)
        n_stab    = _norm_fcf_stability(fcf_stab)
        n_growth  = _norm_fcf_growth_consistency(fcf_growth)
        n_accrual = _norm_accrual_ratio(accrual)

        w = self._WEIGHTS
        raw = (
            n_margin  * w["fcf_margin"]             +
            n_conv    * w["fcf_conversion"]          +
            n_stab    * w["fcf_stability"]           +
            n_growth  * w["fcf_growth_consistency"]  +
            n_accrual * w["accrual_ratio"]
        )

        fcf_quality_score = round(_clamp(raw, 0, 100), 2)

        def _r(v: float | None, decimals: int = 4) -> float | None:
            return round(v, decimals) if v is not None else None

        return {
            "ticker":                 self.ticker,
            "fcf":                    _r(fcf, 2),
            "operating_cash_flow":    _r(ocf, 2),
            "capex":                  _r(abs(capex_raw) if capex_raw is not None else None, 2),
            "fcf_margin":             _r(fcf_margin, 4),
            "fcf_conversion":         _r(fcf_conv, 4),
            "fcf_stability":          _r(fcf_stab, 6),
            "fcf_growth_consistency": _r(fcf_growth, 4),
            "accrual_ratio":          _r(accrual, 6),
            "fcf_cagr_5y":            _r(fcf_cagr, 4),
            "fcf_quality_score":      fcf_quality_score,
            "signal":                 _signal(fcf_quality_score),
            # ── scorer.py compatibility ───────────────────────────────────────
            "total_score": fcf_quality_score,
            "total_max":   100.0,
        }
