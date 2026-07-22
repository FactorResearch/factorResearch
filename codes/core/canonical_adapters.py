"""Compatibility adapters between canonical v1 prices and legacy pandas engines.

The adapters isolate existing Date/Close DataFrame contracts while new callers
use permanent listing identity, exact decimals, UTC availability, and source
provenance. Decimal-to-float conversion occurs only when invoking a legacy
analytical engine and is therefore explicit and testable.

This module must not calculate financial metrics, fetch provider data, infer
availability timestamps, or persist canonical records.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, date, datetime, time
from decimal import Decimal, InvalidOperation
from uuid import UUID

import pandas as pd  # type: ignore[import-untyped]

from codes.domain.canonical import (
    Currency,
    Price,
    PriceAdjustment,
    PriceObservation,
    Provenance,
)


def _parse_legacy_price_rows(frame: pd.DataFrame) -> list[tuple[date, Decimal]]:
    """Parse, sort, and validate legacy Date/Close rows.

    Args:
        frame: Legacy frame containing Date and Close columns.

    Returns:
        Unique business dates and exact closes in increasing date order.

    Raises:
        ValueError: If required columns, dates, closes, or uniqueness are invalid.

    Side Effects:
        Reads and copies the two required columns without mutating the frame.
    """
    missing_columns = {"Date", "Close"} - set(frame.columns)
    if missing_columns:
        raise ValueError(f"legacy price frame missing columns: {sorted(missing_columns)}")
    parsed: list[tuple[date, Decimal]] = []
    for row_number, row in frame.loc[:, ["Date", "Close"]].iterrows():
        try:
            parsed_date = pd.Timestamp(row["Date"])
        except (TypeError, ValueError) as exc:
            raise ValueError(f"legacy price row {row_number} has an invalid date") from exc
        if pd.isna(parsed_date):
            raise ValueError(f"legacy price row {row_number} has an invalid date")
        try:
            close = Decimal(str(row["Close"]))
        except (InvalidOperation, ValueError) as exc:
            raise ValueError(f"legacy price row {row_number} has an invalid close") from exc
        if not close.is_finite() or close <= 0:
            raise ValueError(f"legacy price row {row_number} close must be finite and positive")
        parsed.append((parsed_date.date(), close))
    parsed.sort(key=lambda item: item[0])
    dates = [item[0] for item in parsed]
    if len(dates) != len(set(dates)):
        raise ValueError("legacy price frame contains duplicate dates")
    return parsed


def _price_observation(
    observation_date: date,
    close: Decimal,
    *,
    listing_id: UUID,
    currency: Currency,
    adjustment: PriceAdjustment,
    provider: str,
    normalization_version: str,
    available_at: datetime,
) -> PriceObservation:
    """Build one canonical record from a validated legacy row.

    Args:
        observation_date: Validated business date represented by the close.
        close: Positive finite exact close.
        listing_id: Permanent listing identity.
        currency: Currency of the close.
        adjustment: Corporate-action basis of the close.
        provider: Non-empty legacy source-system label.
        normalization_version: Non-empty mapping version.
        available_at: True UTC availability instant for the source frame.

    Returns:
        One immutable price observation with deterministic legacy provenance.

    Raises:
        ValueError: If availability predates the observation or a domain
            invariant unexpectedly fails.

    Side Effects:
        None.
    """
    observed_at = datetime.combine(observation_date, time.min, tzinfo=UTC)
    if available_at < observed_at:
        raise ValueError("available_at may not precede a price observation date")
    provenance = Provenance(
        provider=provider,
        source_record_id=f"legacy:{listing_id}:{observation_date.isoformat()}",
        observed_at=observed_at,
        available_at=available_at,
        ingested_at=available_at,
        normalization_version=normalization_version,
    )
    return PriceObservation(
        listing_id=listing_id,
        observation_date=observation_date,
        price=Price(close, currency, adjustment),
        available_at=available_at,
        provenance=provenance,
    )


def legacy_price_frame_to_observations(
    frame: pd.DataFrame,
    *,
    listing_id: UUID,
    currency: Currency,
    adjustment: PriceAdjustment,
    provider: str,
    normalization_version: str,
    available_at: datetime,
) -> tuple[PriceObservation, ...]:
    """Validate and convert a legacy Date/Close frame to canonical records.

    The caller supplies permanent identity, adjustment, provenance labels, and
    the true UTC availability instant. The adapter does not infer those facts.
    Dates are normalized to business dates, rows are sorted, duplicates are
    rejected, and close values pass through decimal text to avoid introducing
    additional binary-float error.

    Args:
        frame: Legacy frame containing exactly the required ``Date`` and
            ``Close`` columns plus any ignored presentation columns.
        listing_id: Permanent listing identity, never a ticker alias.
        currency: Currency of every close in the frame.
        adjustment: Corporate-action treatment of every close.
        provider: Non-empty provider or legacy source-system label.
        normalization_version: Non-empty version of this source mapping.
        available_at: True timezone-aware UTC instant at which the complete
            supplied frame was available to Cenvarn.

    Returns:
        Immutable observations ordered by listing identity and business date.

    Raises:
        ValueError: If columns, dates, closes, duplicates, labels, or UTC
            availability are invalid.

    Side Effects:
        Reads and copies the supplied frame; performs no mutation or I/O.
    """
    if not provider.strip() or not normalization_version.strip():
        raise ValueError("provider and normalization_version must not be empty")
    if available_at.tzinfo is None or available_at.utcoffset() != UTC.utcoffset(available_at):
        raise ValueError("available_at must be timezone-aware UTC")
    return tuple(
        _price_observation(
            observation_date,
            close,
            listing_id=listing_id,
            currency=currency,
            adjustment=adjustment,
            provider=provider,
            normalization_version=normalization_version,
            available_at=available_at,
        )
        for observation_date, close in _parse_legacy_price_rows(frame)
    )


def observations_to_legacy_price_frame(
    records: Sequence[PriceObservation],
) -> pd.DataFrame:
    """Convert canonical price records for an existing Date/Close engine.

    This is the documented decimal-to-binary64 boundary. It is appropriate for
    returns, covariance, optimization, and simulation engines, but not for
    authoritative monetary storage or ledger arithmetic.

    Args:
        records: Canonical observations for exactly one listing and one
            currency/adjustment basis, in strictly increasing date order.

    Returns:
        A new DataFrame with ISO ``Date`` strings and binary64 ``Close`` values
        in the same order as the canonical input.

    Raises:
        ValueError: If records mix listings, currencies, adjustment bases,
            repeat dates, or are not strictly date ordered.

    Side Effects:
        Allocates a new DataFrame; performs no mutation or I/O.
    """
    if not records:
        return pd.DataFrame(
            {"Date": pd.Series(dtype="object"), "Close": pd.Series(dtype="float64")}
        )

    identity = (
        records[0].listing_id,
        records[0].price.currency,
        records[0].price.adjustment,
    )
    dates = [record.observation_date for record in records]
    if dates != sorted(dates) or len(dates) != len(set(dates)):
        raise ValueError("canonical price records must have unique increasing dates")
    if any(
        (record.listing_id, record.price.currency, record.price.adjustment) != identity
        for record in records
    ):
        raise ValueError("legacy price conversion requires one listing and price basis")
    return pd.DataFrame(
        {
            "Date": [record.observation_date.isoformat() for record in records],
            "Close": [float(record.price.amount) for record in records],
        }
    )
