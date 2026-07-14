"""
Accounting Quality Engine — V2.3 initial forensic-accounting module.

Focus:
  Detect statement-quality stress signals without duplicating existing
  profitability / cash-flow / growth engines.

Current signals (reweighted when data is missing):
  Receivables growth vs revenue growth
  DSO trend
  Inventory growth vs revenue growth
  Accrual ratio (reused from FCF Quality when available)
  Asset composition (goodwill + intangibles as % of assets)
  Earnings stability (net margin volatility)
  Acquisition-fuelled growth gap (reused from Growth Quality when available)
  Piotroski accrual confirmation (reused from Piotroski F4 when available)
"""

from __future__ import annotations

import statistics
from typing import Any

from codes.core import model_utils as mu


def _safe(val: Any) -> float | None:
    return mu.safe_float(val)


def _first(records: list[dict[str, Any]]) -> float | None:
    return mu.first_record_value(records)


def _values(records: list[dict[str, Any]], n: int | None = None) -> list[float]:
    vals = mu.record_values(records)
    return vals[:n] if n is not None else vals


def _clamp(v: float, lo: float, hi: float) -> float:
    return mu.clamp(v, lo, hi)


def _pct_change(current: float | None, prior: float | None) -> float | None:
    if current is None or prior is None or prior == 0:
        return None
    return mu.percent_change(prior, current)


def _grade(score: float) -> str:
    if score >= 90:
        return "A"
    if score >= 80:
        return "B"
    if score >= 65:
        return "C"
    if score >= 50:
        return "D"
    return "F"


def _risk_level(score: float) -> str:
    if score >= 80:
        return "Low"
    if score >= 60:
        return "Moderate"
    if score >= 40:
        return "Elevated"
    return "High"


def _manipulation_risk(score: float, warning_count: int) -> str:
    if score < 35 or warning_count >= 4:
        return "High"
    if score < 60 or warning_count >= 2:
        return "Moderate"
    return "Low"


def _norm_gap_pp(gap_pp: float | None, *, good_at_or_below: float, bad_at_or_above: float) -> float:
    if gap_pp is None:
        return 50.0
    if gap_pp <= good_at_or_below:
        return 100.0
    if gap_pp >= bad_at_or_above:
        return 0.0
    span = bad_at_or_above - good_at_or_below
    return _clamp((bad_at_or_above - gap_pp) / span * 100, 0, 100)


def _norm_receivables_gap(gap_pp: float | None) -> float:
    return _norm_gap_pp(gap_pp, good_at_or_below=0.0, bad_at_or_above=25.0)


def _norm_dso_change(days: float | None) -> float:
    return _norm_gap_pp(days, good_at_or_below=0.0, bad_at_or_above=20.0)


def _norm_inventory_gap(gap_pp: float | None) -> float:
    return _norm_gap_pp(gap_pp, good_at_or_below=5.0, bad_at_or_above=30.0)


def _norm_accrual_ratio(accrual: float | None) -> float:
    if accrual is None:
        return 50.0
    if accrual <= -0.05:
        return 100.0
    if accrual >= 0.10:
        return 0.0
    return _clamp((0.10 - accrual) / 0.15 * 100, 0, 100)


def _norm_asset_composition(ratio: float | None) -> float:
    if ratio is None:
        return 50.0
    if ratio <= 0.20:
        return 100.0
    if ratio >= 0.60:
        return 0.0
    return _clamp((0.60 - ratio) / 0.40 * 100, 0, 100)


def _norm_earnings_volatility(std_pp: float | None) -> float:
    if std_pp is None:
        return 50.0
    if std_pp <= 2.0:
        return 100.0
    if std_pp >= 15.0:
        return 0.0
    return _clamp((15.0 - std_pp) / 13.0 * 100, 0, 100)


def _norm_piotroski_accrual(flag: bool | None) -> float:
    if flag is None:
        return 50.0
    return 100.0 if flag else 0.0


class AccountingQualityAnalyzer:
    _WEIGHTS = {
        "receivables_gap": 0.18,
        "dso_change": 0.12,
        "inventory_gap": 0.15,
        "accrual_ratio": 0.22,
        "asset_composition": 0.13,
        "earnings_volatility": 0.10,
        "acquisition_gap": 0.05,
        "piotroski_accrual": 0.05,
    }

    def __init__(
        self,
        ticker: str,
        financials: dict,
        *,
        piotroski_result: dict | None = None,
        fcf_quality_result: dict | None = None,
        growth_quality_result: dict | None = None,
    ) -> None:
        self.ticker = ticker.upper().strip()
        self._f = financials
        self._piotroski = piotroski_result or {}
        self._fcf_quality = fcf_quality_result or {}
        self._growth_quality = growth_quality_result or {}

    def calc_receivables_growth_gap(self) -> float | None:
        receivables = _values(self._f.get("receivables", []), 2)
        revenue = _values(self._f.get("revenue", []), 2)
        if len(receivables) < 2 or len(revenue) < 2:
            return None
        rec_growth = _pct_change(receivables[0], receivables[1])
        rev_growth = _pct_change(revenue[0], revenue[1])
        if rec_growth is None or rev_growth is None:
            return None
        return rec_growth - rev_growth

    def calc_dso_change(self) -> float | None:
        receivables = _values(self._f.get("receivables", []), 2)
        revenue = _values(self._f.get("revenue", []), 2)
        if len(receivables) < 2 or len(revenue) < 2:
            return None
        if revenue[0] <= 0 or revenue[1] <= 0:
            return None
        dso_current = receivables[0] / revenue[0] * 365
        dso_prior = receivables[1] / revenue[1] * 365
        return dso_current - dso_prior

    def calc_inventory_growth_gap(self) -> float | None:
        inventory = _values(self._f.get("inventory", []), 2)
        revenue = _values(self._f.get("revenue", []), 2)
        if len(inventory) < 2 or len(revenue) < 2:
            return None
        inv_growth = _pct_change(inventory[0], inventory[1])
        rev_growth = _pct_change(revenue[0], revenue[1])
        if inv_growth is None or rev_growth is None:
            return None
        return inv_growth - rev_growth

    def calc_accrual_ratio(self) -> float | None:
        reused = _safe(self._fcf_quality.get("accrual_ratio"))
        if reused is not None:
            return reused
        net_inc = _first(self._f.get("net_inc", []))
        op_cf = _first(self._f.get("op_cf", []))
        assets = _values(self._f.get("total_assets", []), 2)
        if net_inc is None or op_cf is None or len(assets) < 2:
            return None
        avg_assets = (assets[0] + assets[1]) / 2
        if avg_assets <= 0:
            return None
        return (net_inc - op_cf) / avg_assets

    def calc_asset_composition_ratio(self) -> float | None:
        goodwill = _first(self._f.get("goodwill", [])) or 0.0
        intangibles = _first(self._f.get("intangible_assets", [])) or 0.0
        total_assets = _first(self._f.get("total_assets", []))
        if total_assets is None or total_assets <= 0:
            return None
        return (goodwill + intangibles) / total_assets

    def calc_earnings_volatility(self) -> float | None:
        net_inc = _values(self._f.get("net_inc", []), 5)
        revenue = _values(self._f.get("revenue", []), 5)
        n = min(len(net_inc), len(revenue))
        if n < 3:
            return None
        margins: list[float] = []
        for i in range(n):
            if revenue[i] <= 0:
                continue
            margins.append(net_inc[i] / revenue[i] * 100)
        if len(margins) < 3:
            return None
        return statistics.pstdev(margins)

    def calc_acquisition_gap(self) -> float | None:
        rev_cagr = _safe(self._growth_quality.get("rev_cagr_10y"))
        organic_cagr = _safe(self._growth_quality.get("organic_revenue_cagr_10y"))
        if rev_cagr is None or organic_cagr is None:
            return None
        return rev_cagr - organic_cagr

    def calc_piotroski_accrual_flag(self) -> bool | None:
        for sig in self._piotroski.get("signals", []):
            if sig.get("id") == "F4":
                return bool(sig.get("signal"))
        return None

    def _warning_flags(self, metrics: dict[str, float | bool | None]) -> list[str]:
        flags: list[str] = []
        if (metrics["receivables_gap"] is not None) and metrics["receivables_gap"] >= 15:
            flags.append("receivables_outpacing_revenue")
        if (metrics["dso_change"] is not None) and metrics["dso_change"] >= 10:
            flags.append("dso_deterioration")
        if (metrics["inventory_gap"] is not None) and metrics["inventory_gap"] >= 20:
            flags.append("inventory_build")
        if (metrics["accrual_ratio"] is not None) and metrics["accrual_ratio"] >= 0.08:
            flags.append("aggressive_accruals")
        if (metrics["asset_composition"] is not None) and metrics["asset_composition"] >= 0.45:
            flags.append("intangibles_heavy_balance_sheet")
        if (metrics["earnings_volatility"] is not None) and metrics["earnings_volatility"] >= 8:
            flags.append("unstable_earnings")
        if (metrics["acquisition_gap"] is not None) and metrics["acquisition_gap"] >= 5:
            flags.append("acquisition_fueled_growth")
        if metrics["piotroski_accrual"] is False:
            flags.append("weak_piotroski_accrual_signal")
        return flags

    def _explanation(self, warning_flags: list[str]) -> str:
        if not warning_flags:
            return "Accounting signals are broadly clean with no major forensic warning flags."
        lookup = {
            "receivables_outpacing_revenue": "Receivables are growing materially faster than sales.",
            "dso_deterioration": "Days sales outstanding has worsened, which can indicate softer collection quality.",
            "inventory_build": "Inventory is building faster than revenue.",
            "aggressive_accruals": "Accounting earnings are running ahead of cash realization.",
            "intangibles_heavy_balance_sheet": "A large share of assets sits in goodwill or intangibles.",
            "unstable_earnings": "Net margins are volatile across recent years.",
            "acquisition_fueled_growth": "Reported growth appears meaningfully acquisition-driven.",
            "weak_piotroski_accrual_signal": "Piotroski's low-accrual test does not confirm earnings quality.",
        }
        top = [lookup[f] for f in warning_flags[:3] if f in lookup]
        return " ".join(top)

    def get_accounting_quality_score(self) -> dict:
        receivables_gap = self.calc_receivables_growth_gap()
        dso_change = self.calc_dso_change()
        inventory_gap = self.calc_inventory_growth_gap()
        accrual_ratio = self.calc_accrual_ratio()
        asset_composition = self.calc_asset_composition_ratio()
        earnings_volatility = self.calc_earnings_volatility()
        acquisition_gap = self.calc_acquisition_gap()
        piotroski_accrual = self.calc_piotroski_accrual_flag()

        components = {
            "receivables_gap": (receivables_gap, _norm_receivables_gap(receivables_gap)),
            "dso_change": (dso_change, _norm_dso_change(dso_change)),
            "inventory_gap": (inventory_gap, _norm_inventory_gap(inventory_gap)),
            "accrual_ratio": (accrual_ratio, _norm_accrual_ratio(accrual_ratio)),
            "asset_composition": (asset_composition, _norm_asset_composition(asset_composition)),
            "earnings_volatility": (earnings_volatility, _norm_earnings_volatility(earnings_volatility)),
            "acquisition_gap": (acquisition_gap, _norm_gap_pp(acquisition_gap, good_at_or_below=2.0, bad_at_or_above=10.0)),
            "piotroski_accrual": (piotroski_accrual, _norm_piotroski_accrual(piotroski_accrual)),
        }

        available_weight = sum(
            self._WEIGHTS[name]
            for name, (raw, _) in components.items()
            if raw is not None
        )
        if available_weight <= 0:
            score = 50.0
        else:
            weighted_sum = sum(
                norm * self._WEIGHTS[name]
                for name, (raw, norm) in components.items()
                if raw is not None
            )
            score = _clamp(weighted_sum / available_weight, 0.0, 100.0)

        accounting_quality_score = round(score, 2)
        metrics = {
            "receivables_gap": receivables_gap,
            "dso_change": dso_change,
            "inventory_gap": inventory_gap,
            "accrual_ratio": accrual_ratio,
            "asset_composition": asset_composition,
            "earnings_volatility": earnings_volatility,
            "acquisition_gap": acquisition_gap,
            "piotroski_accrual": piotroski_accrual,
        }
        warning_flags = self._warning_flags(metrics)
        warning_count = len(warning_flags)

        def _r(v: float | None, decimals: int = 4) -> float | None:
            return round(v, decimals) if v is not None else None

        return {
            "ticker": self.ticker,
            "receivables_growth_gap": _r(receivables_gap, 4),
            "dso_change_days": _r(dso_change, 4),
            "inventory_growth_gap": _r(inventory_gap, 4),
            "accrual_ratio": _r(accrual_ratio, 6),
            "asset_composition_ratio": _r(asset_composition, 6),
            "earnings_volatility": _r(earnings_volatility, 4),
            "acquisition_growth_gap": _r(acquisition_gap, 4),
            "piotroski_accrual_confirmed": piotroski_accrual,
            "warning_flags": warning_flags,
            "warning_count": warning_count,
            "accounting_quality_score": accounting_quality_score,
            "accounting_grade": _grade(accounting_quality_score),
            "accounting_risk_level": _risk_level(accounting_quality_score),
            "manipulation_risk": _manipulation_risk(accounting_quality_score, warning_count),
            "explanation": self._explanation(warning_flags),
            "signal": _risk_level(accounting_quality_score).upper(),
            "total_score": accounting_quality_score,
            "total_max": 100.0,
        }
