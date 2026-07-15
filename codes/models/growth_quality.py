"""
Growth Quality Model — P2 module.

Measures quality of long-term business growth using a strict 10-year framework.
All metrics require exactly 10 years of history; shorter series yield unavailable metrics,
which are reweighted proportionally rather than penalised.

Metrics & base weights:
  Revenue CAGR (10Y)        25%  — top-line compound growth
  EPS CAGR (10Y)            25%  — earnings-per-share compound growth
  FCF CAGR (10Y)            20%  — free-cash-flow compound growth
  Margin Stability (10Y)    15%  — std-dev of operating margins (lower = better)
  Incremental ROIC (10Y)    15%  — ΔNOPAT / ΔIC between year 0 and year 10

Missing metrics are reweighted proportionally so no score penalty arises purely
from data absence.

Signal thresholds:
  >= 70  → Bullish
  40-69  → Neutral
  < 40   → Bearish

Output schema:
  {
    "ticker":               str,
    "rev_cagr_10y":         float | None,
    "eps_cagr_10y":         float | None,
    "fcf_cagr_10y":         float | None,
    "margin_stability":     float | None,   # std-dev in pp
    "incremental_roic":     float | None,   # %
    "growth_quality_score": float,          # 0-100
    "signal":               str,            # Bullish | Neutral | Bearish
    "total_score":          float,          # scorer.py compat (= growth_quality_score)
    "total_max":            float,          # 100.0
  }

Integration:
  from codes.models.growth_quality import GrowthQualityAnalyzer
  result = GrowthQualityAnalyzer(ticker, sec_facts).get_growth_quality_score()
  Composite weight: 7%  (per PROJECT_MAP.md)
"""

from __future__ import annotations

import math

from codes.core import financial_math as fm
from codes.core import model_utils as mu

YEARS_REQUIRED = 10  # strict 10-year look-back


# ── Helpers ───────────────────────────────────────────────────────────────────

_safe = mu.safe_float


def _values(records: list, n: int = 11) -> list[float]:
    """Return up to n most-recent non-None values, newest first."""
    return mu.record_values(records, limit=n)


_clamp = mu.clamp


def _cagr(start: float, end: float, years: int) -> float | None:
    """Compound annual growth rate. Returns None on invalid inputs."""
    if start <= 0 or not math.isfinite(start) or not math.isfinite(end) or years <= 0:
        return None
    result = fm.cagr(start, end, years)
    return result * 100.0 if result is not None else None


# ── Signal mapping ────────────────────────────────────────────────────────────

def _signal(score: float) -> str:
    if score >= 70:
        return "Bullish"
    if score >= 40:
        return "Neutral"
    return "Bearish"


# ── Normalisation helpers ─────────────────────────────────────────────────────

def _norm_cagr(cagr_pct: float | None, excellent: float = 15.0, floor: float = -5.0) -> float:
    """
    Map a CAGR (%) to 0-100.
    excellent (default 15%) → 100; floor (default -5%) → 0; 0% → ~25.
    Uses a simple linear interpolation across [floor, excellent].
    """
    if cagr_pct is None:
        return 0.0
    span = excellent - floor
    if span <= 0:
        return 100.0 if cagr_pct >= excellent else 0.0
    return _clamp((cagr_pct - floor) / span * 100.0, 0.0, 100.0)


def _norm_margin_stability(std_pp: float | None) -> float:
    """
    Low std of operating margin = stable = high score.
    std ≤ 2pp → 100; std ≥ 20pp → 0.
    Neutral (50) when unavailable.
    """
    if std_pp is None:
        return 50.0
    if std_pp <= 2.0:
        return 100.0
    if std_pp >= 20.0:
        return 0.0
    return _clamp((20.0 - std_pp) / 18.0 * 100.0, 0.0, 100.0)


def _norm_incremental_roic(iroic_pct: float | None) -> float:
    """
    Incremental ROIC: ≥ 25% → 100; ≤ 0% → 0.
    Neutral (50) when unavailable (insufficient data).
    Values capped at ±100% to suppress noise.
    """
    if iroic_pct is None:
        return 50.0
    capped = _clamp(iroic_pct, -100.0, 100.0)
    if capped >= 25.0:
        return 100.0
    if capped <= 0.0:
        return 0.0
    return _clamp(capped / 25.0 * 100.0, 0.0, 100.0)

def _norm_reinvestment_efficiency(v: float | None) -> float:
    """
    Reinvestment efficiency = incremental ROIC (%) × reinvestment rate (fraction).
    High ROIC combined with high reinvestment = compounding machine.
    >= 15 -> 100; <= 0 -> 0. Neutral (50) when unavailable.
    """
    if v is None:
        return 50.0
    if v >= 15.0:
        return 100.0
    if v <= 0.0:
        return 0.0
    return _clamp(v / 15.0 * 100.0, 0.0, 100.0)

# ── Class ─────────────────────────────────────────────────────────────────────

class GrowthQualityAnalyzer:
    """
    Compute long-term growth quality score from SEC financials.

    Args:
        ticker:     Stock ticker (stored in output).
        financials: sec_facts dict as returned by sec_data.fetch_company_facts().

    Assumptions
    ──────────────
    • "10 years" = index 0 (most recent) vs index 10 in the values list returned by
      _values(records, n=11). Index 0 = year T, index 10 = year T-10.
    • FCF = op_cf − abs(capex). Both series must have ≥ 11 values for FCF CAGR.
    • Operating margin = op_income / revenue. Both must have ≥ 11 values for
      Margin Stability (std-dev across the full 10-year window).
    • Incremental ROIC uses the same NOPAT / IC methodology as profitability.py:
        NOPAT  = op_income × (1 − effective_tax_rate)
        IC     = equity + max(lt_debt − cash, 0)
      Metric excluded when ΔIC ≤ 0 (no new capital deployed).
    • Revenue CAGR uses the raw revenue series (not per-share).
    • EPS CAGR uses the eps series (per-share values already).
    """

    _WEIGHTS = {
        "rev_cagr":                  0.225,
        "eps_cagr":                  0.225,
        "fcf_cagr":                  0.18,
        "margin_stability":          0.135,
        "incremental_roic":          0.135,
        "reinvestment_efficiency":   0.10,
    }

    def __init__(self, ticker: str, financials: dict) -> None:
        self.ticker = ticker.upper().strip()
        self._f = financials

    # ── Metric calculators ────────────────────────────────────────────────────

    def calc_rev_cagr_10y(self) -> float | None:
        """Revenue CAGR over exactly 10 years."""
        vals = _values(self._f.get("revenue", []), n=11)
        if len(vals) < 11:
            return None
        return _cagr(vals[10], vals[0], YEARS_REQUIRED)

    def calc_eps_cagr_10y(self) -> float | None:
        """EPS CAGR over exactly 10 years. Requires positive start and end."""
        vals = _values(self._f.get("eps", []), n=11)
        if len(vals) < 11:
            return None
        start, end = vals[10], vals[0]
        if start <= 0 or end <= 0:
            return None
        return _cagr(start, end, YEARS_REQUIRED)

    def calc_fcf_cagr_10y(self) -> float | None:
        """FCF CAGR over exactly 10 years. Requires positive starting FCF."""
        op_cf_vals = _values(self._f.get("op_cf",  []), n=11)
        capex_vals = _values(self._f.get("capex",  []), n=11)
        if len(op_cf_vals) < 11 or len(capex_vals) < 11:
            return None
        fcf_series = [op_cf_vals[i] - abs(capex_vals[i]) for i in range(11)]
        start, end = fcf_series[10], fcf_series[0]
        if start <= 0:
            return None
        return _cagr(start, end, YEARS_REQUIRED)

    def calc_margin_stability(self) -> float | None:
        """
        Std-dev (pp) of operating margin over 10 years.
        Lower = more stable = higher score.
        Returns None when full 10-year history is unavailable.
        """
        op_inc_vals  = _values(self._f.get("op_income", []), n=11)
        revenue_vals = _values(self._f.get("revenue",   []), n=11)
        n = min(len(op_inc_vals), len(revenue_vals))
        if n < 11:
            return None
        margins = []
        for i in range(11):
            rev = revenue_vals[i]
            if rev and rev > 0:
                margins.append(op_inc_vals[i] / rev * 100.0)
        if len(margins) < 11:
            return None
        mean = sum(margins) / len(margins)
        variance = sum((m - mean) ** 2 for m in margins) / len(margins)
        return math.sqrt(variance)

    def calc_incremental_roic(self) -> float | None:
        """
        Incremental ROIC = ΔNOPAT / ΔIC between year 0 and year 10.
        Returns None when ΔIC ≤ 0.
        """
        op_inc_vals  = _values(self._f.get("op_income", []), n=11)
        net_inc_vals = _values(self._f.get("net_inc",   []), n=11)
        equity_vals  = _values(self._f.get("equity",    []), n=11)
        lt_debt_vals = _values(self._f.get("lt_debt",   []), n=11)
        cash_vals    = _values(self._f.get("cash",      []), n=11)

        if len(op_inc_vals) < 11 or len(equity_vals) < 11:
            return None

        def _nopat(idx: int) -> float | None:
            oi = op_inc_vals[idx] if idx < len(op_inc_vals) else None
            ni = net_inc_vals[idx] if idx < len(net_inc_vals) else None
            if oi is None:
                return None
            if ni is not None and oi > 0:
                tax_rate = _clamp(1.0 - ni / oi, 0.0, 0.50)
            else:
                tax_rate = 0.21
            return oi * (1.0 - tax_rate)

        def _ic(idx: int) -> float | None:
            eq = equity_vals[idx] if idx < len(equity_vals) else None
            ld = lt_debt_vals[idx] if idx < len(lt_debt_vals) else None
            ca = cash_vals[idx]    if idx < len(cash_vals)    else None
            if eq is None:
                return None
            net_debt = (ld or 0.0) - (ca or 0.0)
            ic = eq + max(net_debt, 0.0)
            return ic if ic > 0 else None

        nopat_now  = _nopat(0)
        nopat_old  = _nopat(10)
        ic_now     = _ic(0)
        ic_old     = _ic(10)

        if None in (nopat_now, nopat_old, ic_now, ic_old):
            return None

        delta_nopat = nopat_now - nopat_old   # type: ignore[operator]
        delta_ic    = ic_now    - ic_old       # type: ignore[operator]

        if delta_ic <= 0:
            return None

        raw = delta_nopat / delta_ic * 100.0
        return _clamp(raw, -100.0, 100.0)

    def calc_reinvestment_rate_10y(self) -> float | None:
        """
        Average reinvestment rate = |CapEx| / Operating Income across available
        years (up to 10). Requires at least 3 years of usable data.
        """
        op_inc_vals = _values(self._f.get("op_income", []), n=11)
        capex_vals  = _values(self._f.get("capex",     []), n=11)
        n = min(len(op_inc_vals), len(capex_vals))
        if n < 3:
            return None
        rates = [
            abs(capex_vals[i]) / op_inc_vals[i]
            for i in range(n) if op_inc_vals[i] and op_inc_vals[i] > 0
        ]
        if len(rates) < 3:
            return None
        return sum(rates) / len(rates)

    def calc_reinvestment_efficiency(self) -> float | None:
        """
        Reinvestment efficiency = Incremental ROIC (%) × Reinvestment Rate.
        Rewards businesses that both earn high returns on NEW capital and
        actually reinvest at scale (vs. high-ROIC but low-reinvestment
        harvesters, or high-reinvestment but low-ROIC capital destroyers).
        """
        iroic    = self.calc_incremental_roic()
        reinvest = self.calc_reinvestment_rate_10y()
        if iroic is None or reinvest is None:
            return None
        return iroic * reinvest

    def calc_organic_revenue_cagr_10y(self) -> float | None:
        """
        CAGR of revenue net of M&A cash outflow (organic revenue proxy):
        organic_revenue = revenue - |acquisitions|.
        Requires the full 10-year revenue window; missing acquisition data
        for a given year is treated as 0 (no M&A that year).
        """
        rev_vals = _values(self._f.get("revenue",      []), n=11)
        acq_vals = _values(self._f.get("acquisitions", []), n=11)
        if len(rev_vals) < 11:
            return None
        acq = [acq_vals[i] if i < len(acq_vals) else 0.0 for i in range(11)]
        organic = [rev_vals[i] - abs(acq[i]) for i in range(11)]
        start, end = organic[10], organic[0]
        if start <= 0 or end <= 0:
            return None
        return _cagr(start, end, YEARS_REQUIRED)

    def calc_acquisition_driven_growth_flag(self) -> bool | None:
        """
        True when reported revenue CAGR materially outpaces organic revenue
        CAGR (>= 5pp gap), signalling growth is largely acquisition-fuelled
        rather than organic. None when either CAGR is unavailable.
        """
        rev_cagr     = self.calc_rev_cagr_10y()
        organic_cagr = self.calc_organic_revenue_cagr_10y()
        if rev_cagr is None or organic_cagr is None:
            return None
        return (rev_cagr - organic_cagr) >= 5.0
    # ── Composite score ───────────────────────────────────────────────────────

    def get_growth_quality_score(self) -> dict:
        rev_cagr   = self.calc_rev_cagr_10y()
        eps_cagr   = self.calc_eps_cagr_10y()
        fcf_cagr   = self.calc_fcf_cagr_10y()
        margin_std = self.calc_margin_stability()
        iroic      = self.calc_incremental_roic()
        reinvest_eff = self.calc_reinvestment_efficiency()

        acquisition_driven_flag = self.calc_acquisition_driven_growth_flag()
        organic_rev_cagr        = self.calc_organic_revenue_cagr_10y()

        components = {
            "rev_cagr":                (rev_cagr,     _norm_cagr(rev_cagr)),
            "eps_cagr":                (eps_cagr,     _norm_cagr(eps_cagr)),
            "fcf_cagr":                (fcf_cagr,     _norm_cagr(fcf_cagr)),
            "margin_stability":        (margin_std,   _norm_margin_stability(margin_std)),
            "incremental_roic":        (iroic,        _norm_incremental_roic(iroic)),
            "reinvestment_efficiency": (reinvest_eff, _norm_reinvestment_efficiency(reinvest_eff)),
        }

        available_weight = sum(
            self._WEIGHTS[k]
            for k, (raw, _) in components.items()
            if raw is not None
        )

        if available_weight <= 0:
            score = 50.0
        else:
            raw_sum = sum(
                norm_val * self._WEIGHTS[k]
                for k, (raw, norm_val) in components.items()
                if raw is not None
            )
            score = _clamp(raw_sum / available_weight, 0.0, 100.0)

        growth_quality_score = round(score, 2)

        def _r(v: float | None, decimals: int = 4) -> float | None:
            return round(v, decimals) if v is not None else None

        return {
            "ticker":                   self.ticker,
            "rev_cagr_10y":             _r(rev_cagr,   4),
            "eps_cagr_10y":             _r(eps_cagr,   4),
            "fcf_cagr_10y":             _r(fcf_cagr,   4),
            "margin_stability":         _r(margin_std, 4),
            "incremental_roic":         _r(iroic,       4),
            "reinvestment_efficiency":  _r(reinvest_eff, 4),
            "organic_revenue_cagr_10y": _r(organic_rev_cagr, 4),
            "acquisition_driven_growth": acquisition_driven_flag,
            "growth_quality_score":     growth_quality_score,
            "signal":                   _signal(growth_quality_score),
            # scorer.py compatibility
            "total_score": growth_quality_score,
            "total_max":   100.0,
        }
