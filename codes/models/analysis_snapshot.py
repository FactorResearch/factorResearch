from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from enum import Enum
from typing import Any


class AnalysisType(str, Enum):
    STANDARD = "STANDARD"
    CUSTOM_USER = "CUSTOM_USER"
    BACKTEST = "BACKTEST"
    EXPERIMENTAL = "EXPERIMENTAL"


PUBLIC_ANALYSIS_TYPES = {AnalysisType.STANDARD}


def _num(value: Any) -> float | None:
    try:
        if value is None:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _rating(score: float | None) -> str:
    score = score or 0
    if score >= 75:
        return "STRONG BUY"
    if score >= 60:
        return "BUY"
    if score >= 45:
        return "WATCH"
    if score >= 30:
        return "HOLD"
    return "AVOID"


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
    created_at: datetime | None = None
    id: int | None = None

    @property
    def url_date(self) -> str:
        return self.analysis_date.strftime("%Y%m%d")

    @property
    def public_path(self) -> str:
        return f"/analyze/{self.ticker}/{self.url_date}"

    @property
    def title(self) -> str:
        day = self.analysis_date.strftime("%B %-d %Y")
        return f"{self.company_name} Stock Analysis {day} | FactorResearch"

    @property
    def description(self) -> str:
        score = self.valuation_score
        score_text = f"valuation score {score:.0f}" if score is not None else "valuation metrics"
        return (
            f"{self.company_name} ({self.ticker}) FactorResearch analysis for "
            f"{self.analysis_date.isoformat()} with {score_text}, factor ranking, "
            f"investment metrics, and rating {self.final_rating}."
        )

    @classmethod
    def from_analysis_result(
        cls,
        result: dict[str, Any],
        *,
        analysis_date: date | None = None,
        algorithm_version: str = "standard-v1",
    ) -> "AnalysisSnapshot":
        ticker = str(result.get("symbol") or "").upper()
        enhanced = result.get("enhanced") or {}
        graham = result.get("graham") or {}
        quality = result.get("quality") or {}
        growth = result.get("growth_quality") or {}
        momentum = result.get("momentum") or {}
        risk = result.get("risk") or {}
        regime = result.get("regime") or {}

        valuation_score = _num(
            enhanced.get("composite_score")
            or (result.get("composite") or {}).get("composite_score")
            or graham.get("total_score")
        )

        return cls(
            ticker=ticker,
            company_name=str(result.get("name") or ticker),
            analysis_date=analysis_date or date.today(),
            algorithm_version=algorithm_version,
            valuation_score=valuation_score,
            quality_score=_num(quality.get("total_score")),
            growth_score=_num(growth.get("growth_quality_score")),
            momentum_score=_num(momentum.get("total_score")),
            risk_score=_num(risk.get("risk_score")),
            final_rating=_rating(valuation_score),
            intrinsic_value=_num(
                graham.get("graham_number")
                or (result.get("buffett") or {}).get("intrinsic_value")
            ),
            market_price=_num(result.get("price")),
            market_fear_score=_num(
                regime.get("market_fear_score")
                or regime.get("fear_score")
                or regime.get("market_trend_score")
            ),
        )

