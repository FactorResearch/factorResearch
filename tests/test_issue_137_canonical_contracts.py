"""Cross-runtime contract and compatibility evidence for ISSUE_137."""

from __future__ import annotations

import importlib.util
import json
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path
from types import ModuleType
from uuid import UUID

import pandas as pd
import pyarrow as pa
import pytest

from codes.core.arrow_contracts import (
    price_observation_schema,
    price_observations_from_table,
    price_observations_to_table,
    read_price_observations_ipc,
    write_price_observations_ipc,
)
from codes.core.canonical_adapters import (
    legacy_price_frame_to_observations,
    observations_to_legacy_price_frame,
)
from codes.domain.canonical import (
    SCHEMA_VERSION,
    AvailabilityStatus,
    Currency,
    ObservedDecimal,
    ObservedRatio,
    Price,
    PriceAdjustment,
    PriceObservation,
    Provenance,
    to_json_value,
)

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests" / "fixtures" / "issue_137_price_observations.json"
SCHEMA = ROOT / "schemas" / "canonical" / "v1" / "canonical.schema.json"


def _parse_utc(value: str) -> datetime:
    """Parse a fixture UTC instant without accepting ambiguous timezone input."""
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _fixture_records() -> tuple[PriceObservation, ...]:
    """Build validated Python records from the language-neutral golden fixture."""
    payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
    records: list[PriceObservation] = []
    for raw in payload["records"]:
        raw_provenance = raw["provenance"]
        provenance = Provenance(
            provider=raw_provenance["provider"],
            source_record_id=raw_provenance["source_record_id"],
            source_uri=raw_provenance["source_uri"],
            observed_at=_parse_utc(raw_provenance["observed_at"]),
            available_at=_parse_utc(raw_provenance["available_at"]),
            ingested_at=_parse_utc(raw_provenance["ingested_at"]),
            normalization_version=raw_provenance["normalization_version"],
            filing_version=raw_provenance["filing_version"],
        )
        raw_price = raw["price"]
        records.append(
            PriceObservation(
                listing_id=UUID(raw["listing_id"]),
                observation_date=date.fromisoformat(raw["observation_date"]),
                price=Price(
                    Decimal(raw_price["amount"]),
                    Currency(raw_price["currency"]),
                    PriceAdjustment(raw_price["adjustment"]),
                ),
                available_at=_parse_utc(raw["available_at"]),
                provenance=provenance,
            )
        )
    return tuple(records)


def _load_architecture_module() -> ModuleType:
    """Load the hyphenated architecture script for negative boundary tests."""
    path = ROOT / "scripts" / "check-architecture.py"
    spec = importlib.util.spec_from_file_location("check_architecture", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_language_neutral_schema_covers_required_canonical_vocabulary() -> None:
    """The semantic source names every contract required by the issue."""
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    required = {
        "EntityId",
        "SecurityId",
        "ListingId",
        "IdentifierId",
        "Currency",
        "Money",
        "ObservedRatio",
        "Price",
        "Quantity",
        "Ratio",
        "BasisPoints",
        "FiscalPeriod",
        "FilingVersion",
        "FinancialFact",
        "CorporateAction",
        "PriceObservation",
        "FxObservation",
        "PortfolioTransaction",
        "FactorObservation",
        "FactorMatrix",
        "BacktestSpecification",
        "BacktestResult",
        "SimulationSpecification",
        "SimulationResult",
        "AnalysisManifest",
    }
    assert schema["x-schema-version"] == SCHEMA_VERSION
    assert required <= set(schema["$defs"])


def test_typed_missingness_preserves_valid_zero_and_rejects_ambiguous_values() -> None:
    """A valid zero remains available while every missing state has a reason."""
    instant = datetime(2026, 7, 20, tzinfo=UTC)
    provenance = Provenance(
        provider="fixture",
        source_record_id="zero",
        observed_at=instant,
        available_at=instant,
        ingested_at=instant,
        normalization_version="v1",
    )
    zero = ObservedDecimal(AvailabilityStatus.AVAILABLE, Decimal("0"), None, provenance)
    assert to_json_value(zero)["value"] == "0"

    with pytest.raises(ValueError, match="require a reason"):
        ObservedDecimal(AvailabilityStatus.MISSING, None, None, provenance)
    with pytest.raises(ValueError, match="may not carry"):
        ObservedDecimal(AvailabilityStatus.STALE, Decimal("0"), "stale", provenance)

    analytical_zero = ObservedRatio(AvailabilityStatus.AVAILABLE, 0.0, None, provenance)
    assert to_json_value(analytical_zero)["value"] == 0.0
    with pytest.raises(ValueError, match="require a reason"):
        ObservedRatio(AvailabilityStatus.INSUFFICIENT_HISTORY, None, None, provenance)


def test_python_json_round_trip_preserves_exact_fixture_meaning() -> None:
    """Python serialization retains identity, decimal text, UTC, and provenance."""
    payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
    records = _fixture_records()

    assert payload["schema_version"] == SCHEMA_VERSION
    assert [to_json_value(record) for record in records] == payload["records"]
    assert records[0].price.amount == Decimal("123.450000000001")
    assert records[0].listing_id == UUID("11111111-1111-4111-8111-111111111111")


def test_arrow_and_ipc_round_trip_preserve_canonical_records() -> None:
    """Arrow fields and IPC retain the full golden-record contract."""
    records = _fixture_records()
    table = price_observations_to_table(records)

    assert table.schema.equals(price_observation_schema(), check_metadata=True)
    assert table.schema.metadata[b"cenvarn.schema_version"] == SCHEMA_VERSION.encode("ascii")
    assert table.schema.field("price_amount").type == pa.decimal128(38, 12)
    assert price_observations_from_table(table) == records
    assert read_price_observations_ipc(write_price_observations_ipc(records)) == records


def test_arrow_boundary_rejects_precision_loss_and_schema_drift() -> None:
    """Columnar conversion fails closed instead of rounding or guessing versions."""
    record = _fixture_records()[0]
    too_precise = PriceObservation(
        listing_id=record.listing_id,
        observation_date=record.observation_date,
        price=Price(
            Decimal("1.0000000000001"),
            record.price.currency,
            record.price.adjustment,
        ),
        available_at=record.available_at,
        provenance=record.provenance,
    )
    with pytest.raises(ValueError, match="lose fractional precision"):
        price_observations_to_table((too_precise,))

    table = price_observations_to_table((record,)).replace_schema_metadata({})
    with pytest.raises(ValueError, match="canonical price schema"):
        price_observations_from_table(table)


def test_legacy_dataframe_adapter_is_explicit_and_deterministic() -> None:
    """Existing engines receive stable Date/Close frames through one adapter."""
    listing_id = UUID("11111111-1111-4111-8111-111111111111")
    available_at = datetime(2026, 7, 21, tzinfo=UTC)
    frame = pd.DataFrame({"Date": ["2026-07-20", "2026-07-17"], "Close": ["125.0", "123.45"]})

    records = legacy_price_frame_to_observations(
        frame,
        listing_id=listing_id,
        currency=Currency("USD"),
        adjustment=PriceAdjustment.TOTAL_RETURN_ADJUSTED,
        provider="legacy-fixture",
        normalization_version="legacy-v1",
        available_at=available_at,
    )

    assert [record.observation_date.isoformat() for record in records] == [
        "2026-07-17",
        "2026-07-20",
    ]
    legacy = observations_to_legacy_price_frame(records)
    assert legacy.to_dict("records") == [
        {"Date": "2026-07-17", "Close": 123.45},
        {"Date": "2026-07-20", "Close": 125.0},
    ]

    duplicate = pd.DataFrame({"Date": ["2026-07-20", "2026-07-20"], "Close": [1, 2]})
    with pytest.raises(ValueError, match="duplicate dates"):
        legacy_price_frame_to_observations(
            duplicate,
            listing_id=listing_id,
            currency=Currency("USD"),
            adjustment=PriceAdjustment.RAW,
            provider="legacy-fixture",
            normalization_version="legacy-v1",
            available_at=available_at,
        )


def test_runtime_and_storage_mappings_share_version_and_contract_names() -> None:
    """Rust, TypeScript, PostgreSQL, and OpenAPI remain tied to schema v1."""
    rust = (ROOT / "native" / "factorresearch_core" / "src" / "schema.rs").read_text()
    typescript = (ROOT / "schemas" / "canonical" / "v1" / "canonical.ts").read_text()
    postgres = json.loads(
        (ROOT / "schemas" / "canonical" / "v1" / "postgresql.mapping.json").read_text()
    )
    openapi = json.loads(
        (ROOT / "schemas" / "canonical" / "v1" / "openapi.components.json").read_text()
    )
    contract_names = {
        "AnalysisManifest",
        "BacktestResult",
        "BacktestSpecification",
        "FactorMatrix",
        "FactorObservation",
        "FinancialFact",
        "FxObservation",
        "PriceObservation",
        "Provenance",
        "SimulationResult",
        "SimulationSpecification",
    }

    assert f'CANONICAL_SCHEMA_VERSION: &str = "{SCHEMA_VERSION}"' in rust
    assert f'CANONICAL_SCHEMA_VERSION = "{SCHEMA_VERSION}"' in typescript
    assert postgres["schema_version"] == SCHEMA_VERSION
    assert openapi["x-canonical-schema-version"] == SCHEMA_VERSION
    assert contract_names <= set(openapi["components"]["schemas"])
    assert contract_names - {"AnalysisManifest"} <= set(postgres["records"])
    for name in contract_names:
        assert f"struct {name}" in rust
        assert f"interface {name}" in typescript


def test_architecture_gate_grandfathers_old_boundaries_but_rejects_new_ones() -> None:
    """New engine entry points require named types while legacy functions remain."""
    module = _load_architecture_module()
    check = module.boundary_annotation_errors

    assert check(
        "codes/models/new_engine.py",
        "def score(payload: dict[str, object]) -> float:\n    return 0.0\n",
    ) == ["codes/models/new_engine.py:score: parameter payload requires a named canonical type"]
    assert check(
        "codes/models/new_engine.py",
        "def score(payload: list[dict[str, object]]) -> float:\n    return 0.0\n",
    ) == ["codes/models/new_engine.py:score: parameter payload requires a named canonical type"]
    assert (
        check(
            "codes/models/new_engine.py",
            "class PriceSeries: pass\ndef score(payload: PriceSeries) -> float:\n    return 0.0\n",
        )
        == []
    )
    assert (
        check(
            "codes/models/risk_metrics.py",
            "def score(price_hist: pd.DataFrame) -> dict:\n    return {}\n",
        )
        == []
    )
