"""Product lifecycle metadata for every production analysis model."""

from dataclasses import dataclass
from typing import Literal


Disclosure = Literal["glance", "understand", "investigate"]
Cost = Literal["low", "medium", "high"]


@dataclass(frozen=True)
class ModelRegistration:
    key: str
    version: str
    section: str
    disclosure: Disclosure
    cost: Cost
    cacheable: bool = True
    backfills_existing: bool = True


_MODELS = (
    ("graham", "valuation", "understand", "low"),
    ("quality", "quality", "understand", "low"),
    ("momentum", "market", "investigate", "medium"),
    ("piotroski", "accounting", "understand", "low"),
    ("altman", "accounting", "understand", "low"),
    ("risk", "risk", "understand", "medium"),
    ("greenblatt", "valuation", "investigate", "low"),
    ("buffett", "quality", "understand", "low"),
    ("earnings_revision", "market", "investigate", "medium"),
    ("profitability", "quality", "understand", "low"),
    ("fcf_quality", "accounting", "understand", "low"),
    ("capital_allocation", "quality", "investigate", "low"),
    ("growth_quality", "quality", "investigate", "low"),
    ("insider_activity", "ownership", "investigate", "high"),
    ("factor_momentum", "market", "investigate", "medium"),
    ("alternative_data", "market", "investigate", "high"),
    ("market_fear", "market", "glance", "medium"),
    ("regime", "market", "understand", "medium"),
    ("spy_benchmark", "risk", "investigate", "medium"),
    ("bias", "risk", "understand", "low"),
)

MODELS = {
    key: ModelRegistration(key, "1", section, disclosure, cost)
    for key, section, disclosure, cost in _MODELS
}


def get_model(key: str) -> ModelRegistration:
    return MODELS[key]
