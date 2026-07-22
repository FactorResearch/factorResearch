"""Apache Arrow boundaries for canonical v1 columnar records.

This module maps immutable domain records to maintained PyArrow physical
schemas and Arrow IPC streams. It owns schema metadata, exact decimal scale,
field ordering, and fail-closed compatibility validation.

It must not define financial meaning, read provider payloads, run engines,
persist Parquet files, or create a custom serialization format. Canonical
meaning remains in ``codes.domain.canonical`` and the language-neutral schema.
"""

from __future__ import annotations

from collections.abc import Sequence
from decimal import Decimal
from uuid import UUID

import pyarrow as pa  # type: ignore[import-untyped]
import pyarrow.ipc as ipc  # type: ignore[import-untyped]

from codes.domain.canonical import (
    SCHEMA_VERSION,
    Currency,
    Price,
    PriceAdjustment,
    PriceObservation,
    Provenance,
)

_DECIMAL_PRECISION = 38
_DECIMAL_SCALE = 12
_SCHEMA_METADATA = {
    b"cenvarn.schema": b"price_observation",
    b"cenvarn.schema_version": SCHEMA_VERSION.encode("ascii"),
    b"cenvarn.decimal_policy": b"decimal128(38,12); fail on scale loss",
    b"cenvarn.time_policy": b"UTC",
}


def price_observation_schema() -> pa.Schema:
    """Return the canonical Arrow schema for ordered price observations.

    The schema uses 16-byte UUIDs, date32 business dates, exact
    ``decimal128(38, 12)`` prices, and timezone-aware microsecond UTC instants.
    Required semantic-version metadata is part of compatibility validation.

    Returns:
        A new immutable PyArrow schema with stable field order and metadata.

    Side Effects:
        None.
    """
    return pa.schema(
        [
            pa.field("listing_id", pa.binary(16), nullable=False),
            pa.field("observation_date", pa.date32(), nullable=False),
            pa.field(
                "price_amount",
                pa.decimal128(_DECIMAL_PRECISION, _DECIMAL_SCALE),
                nullable=False,
            ),
            pa.field("currency", pa.string(), nullable=False),
            pa.field("adjustment", pa.string(), nullable=False),
            pa.field("available_at", pa.timestamp("us", tz="UTC"), nullable=False),
            pa.field("provider", pa.string(), nullable=False),
            pa.field("source_record_id", pa.string(), nullable=False),
            pa.field("source_uri", pa.string(), nullable=True),
            pa.field("observed_at", pa.timestamp("us", tz="UTC"), nullable=False),
            pa.field("ingested_at", pa.timestamp("us", tz="UTC"), nullable=False),
            pa.field("normalization_version", pa.string(), nullable=False),
            pa.field("filing_version", pa.string(), nullable=True),
        ],
        metadata=_SCHEMA_METADATA,
    )


def _validate_decimal(value: Decimal) -> None:
    """Reject values that cannot enter decimal128 without loss.

    Args:
        value: Exact value intended for ``decimal128(38, 12)``.

    Returns:
        Nothing. Successful return guarantees finite scale and precision fit.

    Raises:
        ValueError: If the value is non-finite, has more than 12 fractional
            digits, or exceeds 38 total digits after scale alignment.

    Side Effects:
        None.
    """
    if not value.is_finite():
        raise ValueError("Arrow decimal values must be finite")
    sign, digits, exponent = value.as_tuple()
    del sign
    if not isinstance(exponent, int):
        raise ValueError("Arrow decimal values must be finite")
    fractional_digits = max(-exponent, 0)
    integer_digits = max(len(digits) + exponent, 0)
    if fractional_digits > _DECIMAL_SCALE:
        raise ValueError("Arrow decimal conversion would lose fractional precision")
    if integer_digits + _DECIMAL_SCALE > _DECIMAL_PRECISION:
        raise ValueError("Arrow decimal value exceeds decimal128 precision")


def _validate_observation_order(records: Sequence[PriceObservation]) -> None:
    """Require deterministic identity/date ordering without duplicates.

    Args:
        records: Canonical observations in intended Arrow row order.

    Returns:
        Nothing. Successful return guarantees strict listing/date ordering.

    Raises:
        ValueError: If records are out of order or repeat a listing/date key.

    Side Effects:
        None.
    """
    keys = [(record.listing_id.bytes, record.observation_date) for record in records]
    if keys != sorted(keys):
        raise ValueError("price observations must be ordered by listing_id and date")
    if len(keys) != len(set(keys)):
        raise ValueError("price observations may not repeat a listing/date key")


def price_observations_to_table(records: Sequence[PriceObservation]) -> pa.Table:
    """Convert ordered canonical price records to one exact Arrow table.

    Args:
        records: Canonical observations ordered by listing identity and date.

    Returns:
        A PyArrow table with canonical v1 schema metadata and one row per input.

    Raises:
        ValueError: If ordering is invalid or a decimal would lose precision.
        pyarrow.ArrowException: If PyArrow rejects a physical value.

    Side Effects:
        Allocates Arrow arrays in local process memory; performs no I/O.
    """
    _validate_observation_order(records)
    for record in records:
        _validate_decimal(record.price.amount)

    columns: dict[str, list[object]] = {
        "listing_id": [record.listing_id.bytes for record in records],
        "observation_date": [record.observation_date for record in records],
        "price_amount": [record.price.amount for record in records],
        "currency": [record.price.currency.code for record in records],
        "adjustment": [record.price.adjustment.value for record in records],
        "available_at": [record.available_at for record in records],
        "provider": [record.provenance.provider for record in records],
        "source_record_id": [record.provenance.source_record_id for record in records],
        "source_uri": [record.provenance.source_uri for record in records],
        "observed_at": [record.provenance.observed_at for record in records],
        "ingested_at": [record.provenance.ingested_at for record in records],
        "normalization_version": [record.provenance.normalization_version for record in records],
        "filing_version": [record.provenance.filing_version for record in records],
    }
    return pa.Table.from_pydict(columns, schema=price_observation_schema())


def _require_table_schema(table: pa.Table) -> None:
    """Fail before decoding a table with incompatible physical meaning.

    Args:
        table: Arrow table received from an in-process or IPC boundary.

    Returns:
        Nothing. Successful return guarantees exact schema and metadata match.

    Raises:
        ValueError: If fields, nullability, ordering, or metadata differ.

    Side Effects:
        None.
    """
    expected = price_observation_schema()
    if not table.schema.equals(expected, check_metadata=True):
        raise ValueError("Arrow table does not match canonical price schema v1")


def price_observations_from_table(table: pa.Table) -> tuple[PriceObservation, ...]:
    """Decode a canonical Arrow table into validated domain records.

    Args:
        table: Table whose schema must exactly match canonical price v1.

    Returns:
        Immutable observations in original deterministic row order.

    Raises:
        ValueError: If schema metadata or decoded domain invariants fail.

    Side Effects:
        Materializes Python values from Arrow buffers; performs no I/O.
    """
    _require_table_schema(table)
    records: list[PriceObservation] = []
    for row in table.to_pylist():
        provenance = Provenance(
            provider=str(row["provider"]),
            source_record_id=str(row["source_record_id"]),
            source_uri=str(row["source_uri"]) if row["source_uri"] is not None else None,
            observed_at=row["observed_at"],
            available_at=row["available_at"],
            ingested_at=row["ingested_at"],
            normalization_version=str(row["normalization_version"]),
            filing_version=(
                str(row["filing_version"]) if row["filing_version"] is not None else None
            ),
        )
        records.append(
            PriceObservation(
                listing_id=UUID(bytes=row["listing_id"]),
                observation_date=row["observation_date"],
                price=Price(
                    amount=row["price_amount"],
                    currency=Currency(str(row["currency"])),
                    adjustment=PriceAdjustment(str(row["adjustment"])),
                ),
                available_at=row["available_at"],
                provenance=provenance,
            )
        )
    _validate_observation_order(records)
    return tuple(records)


def write_price_observations_ipc(records: Sequence[PriceObservation]) -> bytes:
    """Serialize canonical price observations as an Arrow IPC stream.

    Args:
        records: Ordered canonical observations to cross a process boundary.

    Returns:
        Arrow IPC stream bytes containing schema metadata and record batches.

    Raises:
        ValueError: If canonical ordering or decimal precision is invalid.
        pyarrow.ArrowException: If Arrow serialization fails.

    Side Effects:
        Allocates an in-memory Arrow buffer; performs no file or network I/O.
    """
    table = price_observations_to_table(records)
    sink = pa.BufferOutputStream()
    with ipc.new_stream(sink, table.schema) as writer:
        writer.write_table(table)
    return bytes(sink.getvalue().to_pybytes())


def read_price_observations_ipc(payload: bytes) -> tuple[PriceObservation, ...]:
    """Read and validate one canonical Arrow IPC price stream.

    Args:
        payload: Complete Arrow IPC stream bytes from a trusted transport after
            normal authorization and payload-size enforcement.

    Returns:
        Immutable validated canonical observations.

    Raises:
        ValueError: If the decoded schema or domain records are incompatible.
        pyarrow.ArrowException: If the stream is malformed or truncated.

    Side Effects:
        Reads only the supplied in-memory bytes and allocates decoded buffers.
    """
    with ipc.open_stream(pa.py_buffer(payload)) as reader:
        table = reader.read_all()
    return price_observations_from_table(table)
