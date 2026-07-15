from codes.core.model_registry import MODELS
from codes.app_modules import analysis


PRODUCTION_ANALYSIS_MODELS = {
    "graham", "quality", "momentum", "piotroski", "altman", "risk",
    "greenblatt", "buffett", "earnings_revision", "profitability",
    "fcf_quality", "capital_allocation", "growth_quality", "insider_activity",
    "factor_momentum", "alternative_data", "market_fear", "regime",
    "spy_benchmark", "bias",
}


def test_every_production_model_has_product_lifecycle_metadata():
    assert set(MODELS) == PRODUCTION_ANALYSIS_MODELS
    assert all(model.section for model in MODELS.values())
    assert all(model.disclosure in {"glance", "understand", "investigate"} for model in MODELS.values())


def test_every_production_model_supports_existing_stock_backfill():
    assert all(model.cacheable and model.backfills_existing for model in MODELS.values())


def test_analysis_payload_versions_come_from_registry():
    assert analysis._MODEL_VERSIONS == {key: model.version for key, model in MODELS.items()}
