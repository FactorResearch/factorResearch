import json
from pathlib import Path

from codes.core.model_registry import MODELS, production_manifest


def test_checked_in_model_manifest_matches_registry():
    stored = json.loads(Path("artifacts/production-proof/04-model-integrity/model-manifest.json").read_text())
    assert stored == production_manifest()


def test_every_model_has_versioned_backfill_and_product_placement():
    assert len(MODELS) == 20
    assert all(model.version and model.section and model.backfills_existing for model in MODELS.values())
    assert {model.section for model in MODELS.values()} >= {"valuation", "quality", "accounting", "risk", "market"}
