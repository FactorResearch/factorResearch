from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime
from enum import Enum
from typing import Any

from codes.engine.scorer import ENHANCED_VERDICTS


class AnalysisType(str, Enum):
    STANDARD = "STANDARD"
    CUSTOM_USER = "CUSTOM_USER"
    BACKTEST = "BACKTEST"
    EXPERIMENTAL = "EXPERIMENTAL"


PUBLIC_ANALYSIS_TYPES = {AnalysisType.STANDARD}


def company_slug(company_name: str) -> str:
    """Stable, URL-safe company-name slug with common legal suffixes removed."""
    value = re.sub(r"\b(incorporated|inc|corporation|corp|company|co|ltd|plc)\b\.?", "", company_name, flags=re.I)
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")


def _num(value: Any) -> float | None:
    try:
        if value is None:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _first_num(*values: Any) -> float | None:
    for value in values:
        number = _num(value)
        if number is not None:
            return number
    return None


def _enhanced_verdict(enhanced: dict[str, Any], score: float | None) -> str:
    """Use the scorer's exact warning verdict; derive only for legacy payloads."""
    if enhanced.get("verdict"):
        return str(enhanced["verdict"])
    value = score or 0
    for threshold, verdict, _label, _description in ENHANCED_VERDICTS:
        if value >= threshold:
            return verdict
    return ENHANCED_VERDICTS[-1][1]


@dataclass(frozen=True)
class AnalysisSnapshot:
    ticker: str
    company_name: str
    analysis_date: date
    algorithm_version: str
    valuation_score: float | None
    quality_score: float | None
    growth_score: float | None
    momentum_score: float | None
    risk_score: float | None
    final_rating: str
    intrinsic_value: float | None
    market_price: float | None
    market_fear_score: float | None
    sector: str = ""
    created_at: datetime | None = None
    id: int | None = None
    official_metrics: dict[str, Any] | None = None
    analysis_manifest: dict[str, Any] | None = None

    @property
    def url_date(self) -> str:
        return self.analysis_date.strftime("%Y%m%d")

    @property
    def public_path(self) -> str:
        return f"/{self.ticker}/analyze/{self.url_date}"

    @property
    def company_path(self) -> str:
        return f"/{self.ticker}"

    @property
    def permanent_path(self) -> str:
        """Return the stable SEO URL for this official historical snapshot.

        The ``/analyze/{ticker}/{YYYYMMDD}`` shape is the externally published
        contract. ``public_path`` remains the legacy in-app link shape so
        existing navigation can migrate without invalidating old links.
        """
        return f"/analyze/{self.ticker}/{self.url_date}"

    @property
    def title(self) -> str:
        day = self.analysis_date.strftime("%B %-d %Y")
        return f"{self.company_name} Stock Analysis {day} | Cenvarn"

    @property
    def description(self) -> str:
        score_parts = []
        if self.valuation_score is not None:
            score_parts.append(f"valuation score {self.valuation_score:.0f}/100")
        if self.quality_score is not None:
            score_parts.append(f"quality score {self.quality_score:.0f}/100")
        if self.growth_score is not None:
            score_parts.append(f"growth score {self.growth_score:.0f}/100")
        metric_text = ", ".join(score_parts[:3]) if score_parts else "valuation and factor metrics"
        return (
            f"{self.company_name} ({self.ticker}) stock analysis for "
            f"{self.analysis_date.isoformat()} with {metric_text}, intrinsic value, "
            f"market price, risk metrics, and Cenvarnrating {self.final_rating}."
        )

    @property
    def keywords(self) -> str:
        terms = [
            self.company_name,
            self.ticker,
            f"{self.ticker} stock analysis",
            f"{self.company_name} valuation",
            "factor score",
            "intrinsic value",
            "investment metrics",
        ]
        if self.sector:
            terms.append(f"{self.sector} stocks")
        return ", ".join(terms)

    @classmethod
    def from_analysis_result(
        cls,
        result: dict[str, Any],
        *,
        analysis_date: date | None = None,
        algorithm_version: str = "standard-v1",
    ) -> AnalysisSnapshot:
        ticker = str(result.get("symbol") or "").upper()
        enhanced = result.get("enhanced") or {}
        graham = result.get("graham") or {}
        quality = result.get("quality") or {}
        growth = result.get("growth_quality") or {}
        momentum = result.get("momentum") or {}
        risk = result.get("risk") or {}
        regime = result.get("regime") or {}
        market_fear = result.get("market_fear") or {}
        altman = result.get("altman") or {}
        piotroski = result.get("piotroski") or {}
        beneish = result.get("beneish") or {}
        ohlson = result.get("ohlson") or {}
        profitability = result.get("profitability") or {}

        valuation_score = _first_num(
            enhanced.get("composite_score"),
            (result.get("composite") or {}).get("composite_score"),
            graham.get("total_score"),
        )

        return cls(
            ticker=ticker,
            company_name=str(result.get("name") or ticker),
            analysis_date=analysis_date or date.today(),
            algorithm_version=algorithm_version,
            valuation_score=valuation_score,
            quality_score=_first_num(enhanced.get("quality_pct"), quality.get("total_score")),
            growth_score=_first_num(enhanced.get("growth_quality_pct"), growth.get("growth_quality_score")),
            momentum_score=_first_num(enhanced.get("momentum_pct"), momentum.get("total_score")),
            risk_score=_first_num(enhanced.get("risk_pct"), risk.get("risk_score")),
            final_rating=_enhanced_verdict(enhanced, valuation_score),
            intrinsic_value=_num(
                graham.get("graham_number")
                or (result.get("buffett") or {}).get("intrinsic_value")
            ),
            market_price=_num(result.get("price")),
            market_fear_score=_num(
                market_fear.get("market_fear_score")
                or regime.get("market_fear_score")
                or regime.get("fear_score")
                or regime.get("market_trend_score")
            ),
            sector=str(result.get("sector") or ""),
            official_metrics={
                "composite_score": valuation_score,
                "verdict": _enhanced_verdict(enhanced, valuation_score),
                "verdict_label": enhanced.get("verdict_label"),
                "verdict_desc": enhanced.get("verdict_desc"),
                "margin_of_safety": _first_num(result.get("margin_of_safety"), graham.get("margin_of_safety")),
                "graham_score": _first_num(enhanced.get("graham_pct"), graham.get("total_score")),
                "piotroski_f_score": _first_num(piotroski.get("f_score"), piotroski.get("score")),
                "altman_z_score": _first_num(altman.get("z_score"), altman.get("score")),
                "beneish_m_score": _first_num(beneish.get("m_score"), beneish.get("score")),
                "ohlson_o_score": _first_num(ohlson.get("o_score"), ohlson.get("score")),
                "profitability_score": _first_num(enhanced.get("profitability_pct"), profitability.get("score"), profitability.get("total_score")),
                "value_trap_warning": bool(enhanced.get("value_trap_warning")),
                "compounder_flag": bool(enhanced.get("compounder_flag")),
                "altman_cap_applied": bool(enhanced.get("altman_cap_applied")),
            },
            analysis_manifest=dict(result.get("analysis_manifest") or {}),
        )


@dataclass(frozen=True)
class CustomAnalysisSnapshot:
    id: str
    user_id: str
    ticker: str
    company_name: str
    formula_name: str
    formula_version: str
    composite_score: float | None
    factors: dict[str, float]
    backtest_summary: dict[str, Any]
    default_comparison: dict[str, Any]
    benchmark_comparison: dict[str, Any]
    notes: str
    analysis_date: date
    created_at: datetime | None = None

    @property
    def private_path(self) -> str:
        return f"/analyze/{company_slug(self.company_name)}/custom/{self.id}"
