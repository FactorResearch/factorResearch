import json
from pathlib import Path

from codes.core.model_registry import production_manifest


if __name__ == "__main__":
    target = Path("artifacts/production-proof/04-model-integrity/model-manifest.json")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(production_manifest(), indent=2) + "\n")
