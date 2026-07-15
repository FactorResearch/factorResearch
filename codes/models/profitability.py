"""
Profitability Model — P1 module.

Computes structural business quality using ROIC, margins, and capital
efficiency. Outputs a normalized profitability_score (0-100) and a
classification signal.

Metrics & weights:
  ROIC                       35%  — after-tax return on invested capital
  Gross profitability        20%  — gross profit / total assets (Novy-Marx)
  Operating margin stability 15%  — consistency of operating margin over time
  Capital efficiency         15%  — asset turnover (revenue / total assets)
  Incremental ROIC           15%  — marginal return on new invested capital

Supplementary (not in score):
  ROE adjusted               — ROE de-levered by D/E ratio
  ROA                        — net income / total assets

Signal mapping:
  >= 80  → STRONG_HIGH_QUALITY
  65–79  → HIGH_QUALITY
  45–64  → NEUTRAL
  30–44  → LOW_QUALITY
  < 30   → VALUE_TRAP_RISK

Integration:
  scores["profitability"] = ProfitabilityAnalyzer(ticker, financials)
                                .get_profitability_score()["profitability_score"]
  Composite weight: 12%
"""

from __future__ import annotations

import statistics

from codes.core import model_utils as mu


# ── Helpers ───────────────────────────────────────────────────────────────────

_safe = mu.safe_float
_first = mu.first_record_value


def _values(records: list, n: int = 10) -> list[float]:
    """Return up to n most-recent non-None values, newest first."""
    return mu.record_values(records, limit=n)


_by_year = mu.records_by_year


# ── Signal mapping ────────────────────────────────────────────────────────────

def _signal(score: float) -> str:
    if score >= 80:
        return "STRONG_HIGH_QUALITY"
    if score >= 65:
        return "HIGH_QUALITY"
    if score >= 45:
        return "NEUTRAL"
    if score >= 30:
        return "LOW_QUALITY"
    return "VALUE_TRAP_RISK"


# ── Normalization helpers ─────────────────────────────────────────────────────

def _clamp(v: float, lo: float, hi: float) -> float:
    return mu.clamp(v, lo, hi)


def _norm_roic(roic_pct: float | None) -> float:
    """Map ROIC (%) to 0-100 score. Exceptional ≥25%, zero at ≤0%."""
    if roic_pct is None:
        return 0.0
    if roic_pct >= 25:
        return 100.0
    if roic_pct <= 0:
        return 0.0
    return _clamp(roic_pct / 25 * 100, 0, 100)


def _norm_gross_prof(gp_ratio: float | None) -> float:
    """
    Novy-Marx gross profitability = gross profit / total assets.
    Empirically: ≥0.40 → excellent, ≤0 → poor.
    """
    if gp_ratio is None:
        return 0.0
    if gp_ratio >= 0.40:
        return 100.0
    if gp_ratio <= 0:
        return 0.0
    return _clamp(gp_ratio / 0.40 * 100, 0, 100)


def _norm_op_margin_stability(std_pct: float | None) -> float:
    """
    Low std of operating margin = stable = high score.
    std ≤ 2pp → 100, std ≥ 20pp → 0.
    """
    if std_pct is None:
        return 50.0  # neutral when insufficient data
    if std_pct <= 2:
        return 100.0
    if std_pct >= 20:
        return 0.0
    return _clamp((20 - std_pct) / 18 * 100, 0, 100)


def _norm_asset_turnover(turnover: float | None) -> float:
    """
    Asset turnover = revenue / total_assets.
    ≥1.0 → 100, ≤0.10 → 0.
    """
    if turnover is None:
        return 0.0
    if turnover >= 1.0:
        return 100.0
    if turnover <= 0.10:
        return 0.0
    return _clamp((turnover - 0.10) / 0.90 * 100, 0, 100)


def _norm_incremental_roic(iroic_pct: float | None) -> float:
    """
    Incremental ROIC: Δ(NOPAT) / Δ(IC).
    ≥ 25% → 100, ≤ 0 → 0.  Capped at ±500% to exclude noise.
    """
    if iroic_pct is None:
        return 50.0  # neutral when only one period available
    capped = _clamp(iroic_pct, -100, 500)
    if capped >= 25:
        return 100.0
    if capped <= 0:
        return 0.0
    return _clamp(capped / 25 * 100, 0, 100)


# ── Class ─────────────────────────────────────────────────────────────────────

class ProfitabilityAnalyzer:
    """
    Compute structural profitability score from SEC financials.

    Args:
        ticker:     Stock ticker (stored in output, not used for fetching).
        financials: sec_facts dict as returned by sec_data.fetch_company_facts().
    """

    # Component weights (must sum to 1.0)
    _WEIGHTS = {
        "roic":                      0.35,
        "gross_profitability":        0.20,
        "operating_margin_stability": 0.15,
        "capital_efficiency":         0.15,
        "incremental_roic":           0.15,
    }

    def __init__(self, ticker: str, financials: dict) -> None:
        self.ticker = ticker.upper().strip()
        self._f = financials  # sec_facts dict

    # ── Raw metric extractors ─────────────────────────────────────────────────

    def calc_roic(self) -> float | None:
        """
        ROIC = NOPAT / Invested Capital
        NOPAT  = Operating Income × (1 − effective_tax_rate)
        IC     = Equity + Long-term Debt + Short-term debt − Cash
               = Equity + Net Debt  (floor at equity to avoid negative IC)
        """
        op_inc  = _first(self._f.get("op_income", []))
        net_inc = _first(self._f.get("net_inc",   []))
        revenue = _first(self._f.get("revenue",   []))
        equity  = _first(self._f.get("equity",    []))
        lt_debt = _first(self._f.get("lt_debt",   []))
        cash    = _first(self._f.get("cash",       []))

        if op_inc is None or equity is None:
            return None

        # Effective tax rate via net income / pre-tax income proxy.
        # Fallback: use net_inc / (net_inc + op_inc) as a rough estimate,
        # or assume 21% corporate rate when data is sparse.
        if net_inc is not None and op_inc > 0:
            tax_rate = _clamp(1 - net_inc / op_inc, 0, 0.50)
        else:
            tax_rate = 0.21

        nopat = op_inc * (1 - tax_rate)

        net_debt = (lt_debt or 0) - (cash or 0)
        ic = equity + max(net_debt, 0)
        if ic <= 0:
            return None

        return nopat / ic * 100

    def calc_roe_adjusted(self) -> float | None:
        """
        ROE de-levered by D/E: removes the amplification from leverage.
        ROE_adj = ROE / (1 + D/E)   where D/E = total_liabilities / equity.
        """
        net_inc  = _first(self._f.get("net_inc",   []))
        equity   = _first(self._f.get("equity",    []))
        tot_lib  = _first(self._f.get("tot_lib",   []))

        if net_inc is None or equity is None or equity <= 0:
            return None

        roe = net_inc / equity * 100
        de_ratio = (tot_lib / equity) if (tot_lib is not None and equity > 0) else 1.0
        return roe / (1 + max(de_ratio, 0))

    def calc_roa(self) -> float | None:
        """ROA = Net Income / Total Assets."""
        net_inc    = _first(self._f.get("net_inc",       []))
        tot_assets = _first(self._f.get("total_assets",  []))
        if net_inc is None or not tot_assets:
            return None
        return net_inc / tot_assets * 100

    def calc_gross_profitability(self) -> float | None:
        """
        Novy-Marx (2013): Gross Profit / Total Assets.
        A higher ratio signals superior pricing power and efficiency.
        """
        gp         = _first(self._f.get("gross_profit",  []))
        tot_assets = _first(self._f.get("total_assets",  []))
        if gp is None or not tot_assets:
            return None
        return gp / tot_assets  # ratio, not pct

    def calc_operating_margin_stability(self) -> float | None:
        """
        Standard deviation of operating margin over up to 7 years.
        Lower std = more stable = higher quality.
        Returns std in percentage points, or None if <3 periods available.
        """
        op_inc_list = _values(self._f.get("op_income", []), n=7)
        rev_list    = _values(self._f.get("revenue",   []), n=7)

        pairs = min(len(op_inc_list), len(rev_list))
        if pairs < 3:
            return None

        margins = [
            op_inc_list[i] / rev_list[i] * 100
            for i in range(pairs)
            if rev_list[i] and rev_list[i] > 0
        ]
        if len(margins) < 3:
            return None

        return statistics.stdev(margins)

    def calc_capital_efficiency(self) -> float | None:
        """Asset Turnover = Revenue / Total Assets."""
        revenue    = _first(self._f.get("revenue",      []))
        tot_assets = _first(self._f.get("total_assets", []))
        if revenue is None or not tot_assets:
            return None
        return revenue / tot_assets

    def calc_incremental_roic(self) -> float | None:
        """
        Incremental ROIC = ΔNOPAT / ΔIC over the most recent two periods.
        Uses same NOPAT / IC methodology as calc_roic().
        Returns None when only one period of data is available.
        """
        op_inc_vals = _values(self._f.get("op_income", []), n=2)
        net_inc_vals= _values(self._f.get("net_inc",   []), n=2)
        equity_vals = _values(self._f.get("equity",    []), n=2)
        lt_debt_vals= _values(self._f.get("lt_debt",   []), n=2)
        cash_vals   = _values(self._f.get("cash",       []), n=2)

        if len(op_inc_vals) < 2 or len(equity_vals) < 2:
            return None

        def _nopat(idx: int) -> float | None:
            oi = op_inc_vals[idx] if idx < len(op_inc_vals) else None
            ni = net_inc_vals[idx] if idx < len(net_inc_vals) else None
            if oi is None:
                return None
            if ni is not None and oi > 0:
                tax_rate = _clamp(1 - ni / oi, 0, 0.50)
            else:
                tax_rate = 0.21
            return oi * (1 - tax_rate)

        def _ic(idx: int) -> float | None:
            eq = equity_vals[idx] if idx < len(equity_vals) else None
            ld = lt_debt_vals[idx] if idx < len(lt_debt_vals) else None
            ca = cash_vals[idx]    if idx < len(cash_vals)    else None
            if eq is None:
                return None
            net_debt = (ld or 0) - (ca or 0)
            ic = eq + max(net_debt, 0)
            return ic if ic > 0 else None

        nopat_now  = _nopat(0)
        nopat_prev = _nopat(1)
        ic_now     = _ic(0)
        ic_prev    = _ic(1)

        if None in (nopat_now, nopat_prev, ic_now, ic_prev):
            return None

        delta_nopat = nopat_now  - nopat_prev   # type: ignore[operator]
        delta_ic    = ic_now     - ic_prev       # type: ignore[operator]

        if abs(delta_ic) < 1:       # near-zero capital change — avoid div/0
            return None

        return delta_nopat / delta_ic * 100

    # ── Composite score ───────────────────────────────────────────────────────

    def get_profitability_score(self) -> dict:
        """
        Compute and return a strict JSON-compatible dict:

        {
            "ticker": str,
            "roic": float,
            "roe_adjusted": float,
            "roa": float,
            "gross_profitability": float,
            "operating_margin_stability": float,
            "capital_efficiency": float,
            "incremental_roic": float,
            "profitability_score": float,
            "signal": str
        }

        All metric values are floats or None (serialised as null).
        profitability_score is always a float in 0-100.
        """
        roic        = self.calc_roic()
        roe_adj     = self.calc_roe_adjusted()
        roa         = self.calc_roa()
        gross_prof  = self.calc_gross_profitability()
        op_stab     = self.calc_operating_margin_stability()
        cap_eff     = self.calc_capital_efficiency()
        incr_roic   = self.calc_incremental_roic()

        # Normalised sub-scores
        n_roic      = _norm_roic(roic)
        n_gp        = _norm_gross_prof(gross_prof)
        n_stab      = _norm_op_margin_stability(op_stab)
        n_ce        = _norm_asset_turnover(cap_eff)
        n_iroic     = _norm_incremental_roic(incr_roic)

        w = self._WEIGHTS
        raw = (
            n_roic   * w["roic"]                       +
            n_gp     * w["gross_profitability"]         +
            n_stab   * w["operating_margin_stability"]  +
            n_ce     * w["capital_efficiency"]          +
            n_iroic  * w["incremental_roic"]
        )

        profitability_score = round(_clamp(raw, 0, 100), 2)

        def _r(v: float | None, decimals: int = 4) -> float | None:
            return round(v, decimals) if v is not None else None

        return {
            "ticker":                    self.ticker,
            "roic":                      _r(roic, 4),
            "roe_adjusted":              _r(roe_adj, 4),
            "roa":                       _r(roa, 4),
            "gross_profitability":       _r(gross_prof, 6),
            "operating_margin_stability":_r(op_stab, 4),
            "capital_efficiency":        _r(cap_eff, 6),
            "incremental_roic":          _r(incr_roic, 4),
            "profitability_score":       profitability_score,
            "signal":                    _signal(profitability_score),
            # ── scorer.py compatibility ───────────────────────────────────────
            "total_score": profitability_score,
            "total_max":   100.0,
        }
