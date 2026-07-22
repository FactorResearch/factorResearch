"""Canonical v1 financial and quantitative domain contracts.

This module owns immutable Python representations of the language-neutral
schemas in ``schemas/canonical/v1``. It validates financial meaning at the
domain boundary and serializes exact values without depending on pandas,
PyArrow, a web framework, persistence, or provider-specific payloads.

It must not perform financial calculations, network or database access,
authorization, retries, logging, or columnar serialization. Those concerns
belong to engines, adapters, repositories, and ``codes.core.arrow_contracts``.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, fields, is_dataclass
from datetime import UTC, date, datetime
from decimal import Decimal
from enum import Enum
from typing import TypeAlias
from uuid import UUID

SCHEMA_VERSION = "1.0.0"

JsonScalar: TypeAlias = None | bool | int | float | str
JsonValue: TypeAlias = JsonScalar | list["JsonValue"] | dict[str, "JsonValue"]
_JSON_UNHANDLED = object()


class AvailabilityStatus(str, Enum):
    """Explain whether a value exists and why it may not be usable."""

    AVAILABLE = "available"
    MISSING = "missing"
    NOT_APPLICABLE = "not_applicable"
    STALE = "stale"
    INVALID = "invalid"
    PROVIDER_FAILED = "provider_failed"
    INSUFFICIENT_HISTORY = "insufficient_history"
    POLICY_SUPPRESSED = "policy_suppressed"


class PriceAdjustment(str, Enum):
    """Identify the corporate-action treatment already applied to a price."""

    RAW = "raw"
    SPLIT_ADJUSTED = "split_adjusted"
    TOTAL_RETURN_ADJUSTED = "total_return_adjusted"


class CorporateActionType(str, Enum):
    """Identify the supported event represented by a corporate-action record."""

    SPLIT = "split"
    CASH_DIVIDEND = "cash_dividend"
    STOCK_DIVIDEND = "stock_dividend"
    SPINOFF = "spinoff"
    MERGER = "merger"


class PortfolioTransactionType(str, Enum):
    """Identify the economic event represented by a portfolio ledger record."""

    BUY = "buy"
    SELL = "sell"
    DEPOSIT = "deposit"
    WITHDRAWAL = "withdrawal"
    DIVIDEND = "dividend"
    FEE = "fee"
    TAX = "tax"


def _require_utc(value: datetime, field_name: str) -> None:
    """Reject naive and non-UTC instants at the canonical trust boundary.

    Args:
        value: Instant whose timezone semantics must be unambiguous.
        field_name: Stable field label included in validation errors.

    Returns:
        Nothing. Successful return guarantees a timezone-aware UTC instant.

    Raises:
        ValueError: If ``value`` is naive or has a non-zero UTC offset.

    Side Effects:
        None.
    """
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field_name} must be timezone-aware UTC")
    if value.utcoffset() != UTC.utcoffset(value):
        raise ValueError(f"{field_name} must use UTC")


def _require_text(value: str, field_name: str) -> None:
    """Reject empty canonical identifiers and version labels.

    Args:
        value: Text value to validate without modifying it.
        field_name: Stable field label included in validation errors.

    Returns:
        Nothing. Successful return guarantees non-whitespace text.

    Raises:
        ValueError: If ``value`` contains no non-whitespace characters.

    Side Effects:
        None.
    """
    if not value.strip():
        raise ValueError(f"{field_name} must not be empty")


@dataclass(frozen=True, slots=True)
class Currency:
    """Represent an uppercase three-letter currency code.

    The value object owns syntax validation only. It does not maintain the ISO
    currency registry or perform currency conversion.

    Attributes:
        code: Uppercase three-letter code such as ``USD`` or ``CAD``.
    """

    code: str

    def __post_init__(self) -> None:
        """Validate the currency code without normalizing caller input.

        Raises:
            ValueError: If the code is not exactly three uppercase letters.

        Side Effects:
            None; the frozen value remains unchanged.
        """
        if re.fullmatch(r"[A-Z]{3}", self.code) is None:
            raise ValueError("currency code must contain three uppercase letters")


@dataclass(frozen=True, slots=True)
class Money:
    """Represent an exact monetary amount in one explicit currency.

    Attributes:
        amount: Base-10 exact amount. No implicit rounding is performed.
        currency: Currency in which the amount is denominated.
    """

    amount: Decimal
    currency: Currency


@dataclass(frozen=True, slots=True)
class Price:
    """Represent an exact positive price and its adjustment basis.

    Attributes:
        amount: Strictly positive base-10 exact price.
        currency: Currency in which the price is quoted.
        adjustment: Corporate-action treatment already applied.
    """

    amount: Decimal
    currency: Currency
    adjustment: PriceAdjustment

    def __post_init__(self) -> None:
        """Reject non-positive or non-finite exact prices.

        Raises:
            ValueError: If the price is zero, negative, NaN, or infinite.

        Side Effects:
            None; the frozen value remains unchanged.
        """
        if not self.amount.is_finite() or self.amount <= 0:
            raise ValueError("price amount must be finite and positive")


@dataclass(frozen=True, slots=True)
class Quantity:
    """Represent an exact amount in an explicit unit.

    Attributes:
        amount: Base-10 exact quantity; negative values remain meaningful for
            signed ledger movements.
        unit: Non-empty unit label such as ``shares`` or ``contracts``.
    """

    amount: Decimal
    unit: str

    def __post_init__(self) -> None:
        """Validate a finite quantity and non-empty unit.

        Raises:
            ValueError: If the amount is non-finite or the unit is empty.

        Side Effects:
            None; the frozen value remains unchanged.
        """
        if not self.amount.is_finite():
            raise ValueError("quantity amount must be finite")
        _require_text(self.unit, "quantity unit")


@dataclass(frozen=True, slots=True)
class Ratio:
    """Represent one finite binary64 analytical ratio.

    This type is for returns, correlations, covariance-derived metrics,
    optimization, and simulations. It must not represent authoritative money.

    Attributes:
        value: Finite IEEE-754 binary64 value without implicit percentage
            scaling; ``0.15`` means fifteen percent when the owning contract
            defines a return.
    """

    value: float

    def __post_init__(self) -> None:
        """Reject NaN and infinite analytical values.

        Raises:
            ValueError: If ``value`` is not finite.

        Side Effects:
            None; the frozen value remains unchanged.
        """
        if not math.isfinite(self.value):
            raise ValueError("ratio must be finite")


@dataclass(frozen=True, slots=True)
class BasisPoints:
    """Represent an integral count of basis points.

    Attributes:
        value: Signed basis-point count; one unit is 0.01 percentage point.
    """

    value: int


@dataclass(frozen=True, slots=True)
class Provenance:
    """Trace a canonical value to its source and point-in-time availability.

    The record owns normalized lineage metadata and UTC ordering. It performs
    no provider lookup and contains no credentials.

    Attributes:
        provider: Stable provider or source-system name.
        source_record_id: Provider-stable record identifier.
        observed_at: UTC instant represented by the source observation.
        available_at: First UTC instant the observation was usable by Cenvarn.
        ingested_at: UTC instant Cenvarn stored or normalized the observation.
        normalization_version: Version of provider-to-canonical mapping.
        source_uri: Optional public or internal stable source URI.
        filing_version: Optional filing or amendment identity.
    """

    provider: str
    source_record_id: str
    observed_at: datetime
    available_at: datetime
    ingested_at: datetime
    normalization_version: str
    source_uri: str | None = None
    filing_version: str | None = None

    def __post_init__(self) -> None:
        """Validate lineage labels, UTC instants, and temporal ordering.

        Raises:
            ValueError: If a required label is empty, a timestamp is not UTC,
                or availability/ingestion precedes the source observation.

        Side Effects:
            None; the frozen value remains unchanged.
        """
        for field_name in ("provider", "source_record_id", "normalization_version"):
            _require_text(str(getattr(self, field_name)), field_name)
        _require_utc(self.observed_at, "observed_at")
        _require_utc(self.available_at, "available_at")
        _require_utc(self.ingested_at, "ingested_at")
        if self.available_at < self.observed_at:
            raise ValueError("available_at may not precede observed_at")
        if self.ingested_at < self.available_at:
            raise ValueError("ingested_at may not precede available_at")


@dataclass(frozen=True, slots=True)
class ObservedDecimal:
    """Represent an exact value or one explicit unavailable state.

    Available values require both an exact decimal and provenance. Every other
    state forbids a numeric value and requires a human-readable reason. This
    prevents missing, invalid, stale, or suppressed inputs from becoming zero.

    Attributes:
        status: Availability classification.
        value: Exact value only when status is ``available``.
        reason: Explanation required for non-available states.
        provenance: Source lineage required for available values and optional
            for failures that occurred before a source record existed.
    """

    status: AvailabilityStatus
    value: Decimal | None
    reason: str | None
    provenance: Provenance | None

    def __post_init__(self) -> None:
        """Enforce the tagged missingness invariant.

        Raises:
            ValueError: If value, reason, or provenance conflicts with status,
                or an available value is non-finite.

        Side Effects:
            None; the frozen value remains unchanged.
        """
        if self.status is AvailabilityStatus.AVAILABLE:
            if self.value is None or self.provenance is None:
                raise ValueError("available values require value and provenance")
            if not self.value.is_finite():
                raise ValueError("available decimal must be finite")
            if self.reason is not None:
                raise ValueError("available values may not include a missingness reason")
            return
        if self.value is not None:
            raise ValueError("non-available values may not carry a numeric value")
        if self.reason is None or not self.reason.strip():
            raise ValueError("non-available values require a reason")


@dataclass(frozen=True, slots=True)
class ObservedRatio:
    """Represent a finite analytical value or explicit unavailable state."""

    status: AvailabilityStatus
    value: float | None
    reason: str | None
    provenance: Provenance | None

    def __post_init__(self) -> None:
        """Enforce tagged analytical missingness without sentinel numbers."""
        if self.status is AvailabilityStatus.AVAILABLE:
            if self.value is None or self.provenance is None:
                raise ValueError("available values require value and provenance")
            if not math.isfinite(self.value):
                raise ValueError("available ratio must be finite")
            if self.reason is not None:
                raise ValueError("available values may not include a missingness reason")
            return
        if self.value is not None:
            raise ValueError("non-available values may not carry a numeric value")
        if self.reason is None or not self.reason.strip():
            raise ValueError("non-available values require a reason")


@dataclass(frozen=True, slots=True)
class FiscalPeriod:
    """Represent a bounded fiscal reporting period.

    Attributes:
        fiscal_year: Issuer-designated fiscal year.
        period: One of FY, Q1–Q4, H1, H2, or TTM.
        start_date: Inclusive business-date start.
        end_date: Inclusive business-date end.
    """

    fiscal_year: int
    period: str
    start_date: date
    end_date: date

    def __post_init__(self) -> None:
        """Validate the fiscal label and chronological range.

        Raises:
            ValueError: If the year or period is unsupported, or the end date
                precedes the start date.

        Side Effects:
            None; the frozen value remains unchanged.
        """
        if not 1800 <= self.fiscal_year <= 9999:
            raise ValueError("fiscal_year must be between 1800 and 9999")
        if self.period not in {"FY", "Q1", "Q2", "Q3", "Q4", "H1", "H2", "TTM"}:
            raise ValueError("unsupported fiscal period")
        if self.end_date < self.start_date:
            raise ValueError("fiscal period end may not precede start")


@dataclass(frozen=True, slots=True)
class FilingVersion:
    """Identify one filing version or amendment without overwriting history.

    Attributes:
        filing_id: Permanent internal filing identity.
        accession: Regulator or provider filing accession.
        filed_at: UTC filing-submission instant.
        accepted_at: UTC instant the filing became available.
        amendment: Zero for the original filing and increasing for amendments.
    """

    filing_id: UUID
    accession: str
    filed_at: datetime
    accepted_at: datetime
    amendment: int

    def __post_init__(self) -> None:
        """Validate filing identity, UTC time, and amendment ordering.

        Raises:
            ValueError: If the accession is empty, timestamps are not UTC,
                acceptance precedes filing, or amendment is negative.

        Side Effects:
            None; the frozen value remains unchanged.
        """
        _require_text(self.accession, "accession")
        _require_utc(self.filed_at, "filed_at")
        _require_utc(self.accepted_at, "accepted_at")
        if self.accepted_at < self.filed_at:
            raise ValueError("accepted_at may not precede filed_at")
        if self.amendment < 0:
            raise ValueError("amendment must be non-negative")


@dataclass(frozen=True, slots=True)
class FinancialFact:
    """Represent one point-in-time financial fact with typed missingness.

    Attributes:
        entity_id: Permanent issuer identity.
        concept: Canonical or source-qualified accounting concept.
        period: Fiscal period to which the fact applies.
        value: Exact value or explicit unavailable state.
        unit: Non-empty accounting unit.
        currency: Currency when the unit is monetary.
        filing: Filing version when the source is a filing.
    """

    entity_id: UUID
    concept: str
    period: FiscalPeriod
    value: ObservedDecimal
    unit: str
    currency: Currency | None = None
    filing: FilingVersion | None = None

    def __post_init__(self) -> None:
        """Validate non-empty concept and unit labels.

        Raises:
            ValueError: If concept or unit is empty.

        Side Effects:
            None; the frozen value remains unchanged.
        """
        _require_text(self.concept, "concept")
        _require_text(self.unit, "unit")


@dataclass(frozen=True, slots=True)
class CorporateAction:
    """Represent one immutable security-level corporate action.

    Attributes:
        security_id: Permanent security identity.
        action_id: Permanent action identity.
        action_type: Supported economic event type.
        effective_date: Business date on which the action takes effect.
        value: Exact action ratio or amount with explicit missingness.
        provenance: Source lineage for the action record.
    """

    security_id: UUID
    action_id: UUID
    action_type: CorporateActionType
    effective_date: date
    value: ObservedDecimal
    provenance: Provenance


@dataclass(frozen=True, slots=True)
class PriceObservation:
    """Represent one dated canonical listing price.

    Attributes:
        listing_id: Permanent listing identity; never a ticker alias.
        observation_date: Trading or valuation business date.
        price: Exact positive price and adjustment basis.
        available_at: First UTC instant the price was usable.
        provenance: Source lineage for the observation.
    """

    listing_id: UUID
    observation_date: date
    price: Price
    available_at: datetime
    provenance: Provenance

    def __post_init__(self) -> None:
        """Validate UTC availability and agreement with provenance.

        Raises:
            ValueError: If availability is not UTC or disagrees with lineage.

        Side Effects:
            None; the frozen value remains unchanged.
        """
        _require_utc(self.available_at, "available_at")
        if self.available_at != self.provenance.available_at:
            raise ValueError("price availability must match provenance")


@dataclass(frozen=True, slots=True)
class FxObservation:
    """Represent one point-in-time foreign-exchange rate.

    Attributes:
        base_currency: Currency whose one unit is being priced.
        quote_currency: Currency in which the base is priced.
        observation_date: Business date of the rate.
        rate: Exact rate or explicit unavailable state.
        available_at: First UTC instant the rate was usable.
        provenance: Source lineage for the observation.
    """

    base_currency: Currency
    quote_currency: Currency
    observation_date: date
    rate: ObservedDecimal
    available_at: datetime
    provenance: Provenance

    def __post_init__(self) -> None:
        """Validate currency distinction and UTC availability.

        Raises:
            ValueError: If currencies are equal, availability is not UTC, or
                availability disagrees with provenance.

        Side Effects:
            None; the frozen value remains unchanged.
        """
        if self.base_currency == self.quote_currency:
            raise ValueError("FX base and quote currencies must differ")
        _require_utc(self.available_at, "available_at")
        if self.available_at != self.provenance.available_at:
            raise ValueError("FX availability must match provenance")


@dataclass(frozen=True, slots=True)
class PortfolioTransaction:
    """Represent one immutable portfolio-ledger event.

    This record defines transport meaning only; authorization and ledger state
    transitions remain application and persistence responsibilities.

    Attributes:
        transaction_id: Permanent transaction identity.
        portfolio_id: Permanent portfolio identity within its tenant boundary.
        listing_id: Permanent listing identity affected by the event.
        transaction_type: Economic event type.
        quantity: Exact signed quantity and unit.
        unit_price: Exact execution price when applicable.
        executed_at: UTC economic execution time.
        recorded_at: UTC system-recording time.
    """

    transaction_id: UUID
    portfolio_id: UUID
    listing_id: UUID
    transaction_type: PortfolioTransactionType
    quantity: Quantity
    unit_price: Price | None
    executed_at: datetime
    recorded_at: datetime

    def __post_init__(self) -> None:
        """Validate UTC execution order.

        Raises:
            ValueError: If timestamps are not UTC or recording precedes the
                represented execution.

        Side Effects:
            None; the frozen value remains unchanged.
        """
        _require_utc(self.executed_at, "executed_at")
        _require_utc(self.recorded_at, "recorded_at")
        if self.recorded_at < self.executed_at:
            raise ValueError("recorded_at may not precede executed_at")


@dataclass(frozen=True, slots=True)
class FactorObservation:
    """Represent one versioned point-in-time factor value.

    Attributes:
        security_id: Permanent security identity.
        factor: Stable factor name.
        as_of_date: Business date represented by the factor.
        available_at: First UTC instant the factor was usable.
        value: Finite analytical value or explicit unavailable state.
        model_version: Version of the factor methodology.
    """

    security_id: UUID
    factor: str
    as_of_date: date
    available_at: datetime
    value: ObservedRatio
    model_version: str

    def __post_init__(self) -> None:
        """Validate factor labels, UTC time, and status/value agreement.

        Raises:
            ValueError: If labels are empty, time is not UTC, an available
                value is absent or non-finite, or an unavailable value exists.

        Side Effects:
            None; the frozen value remains unchanged.
        """
        _require_text(self.factor, "factor")
        _require_text(self.model_version, "model_version")
        _require_utc(self.available_at, "available_at")
        if self.value.provenance is not None and (
            self.available_at != self.value.provenance.available_at
        ):
            raise ValueError("factor availability must match provenance")


@dataclass(frozen=True, slots=True)
class FactorMatrix:
    """Represent a dense point-in-time security-by-factor matrix.

    Attributes:
        as_of_date: Business date represented by every matrix row.
        available_at: First UTC instant the complete matrix was usable.
        security_ids: Deterministically ordered permanent security identities.
        factor_names: Deterministically ordered factor columns.
        values: Row-major tagged analytical values with explicit missingness.
        model_version: Version shared by all factor columns.
    """

    as_of_date: date
    available_at: datetime
    security_ids: tuple[UUID, ...]
    factor_names: tuple[str, ...]
    values: tuple[tuple[ObservedRatio, ...], ...]
    model_version: str

    def __post_init__(self) -> None:
        """Validate UTC time, labels, dimensions, identity uniqueness, and values.

        Raises:
            ValueError: If dimensions differ, identities or names repeat,
                labels are empty, or a numeric cell is non-finite.

        Side Effects:
            None; the frozen value remains unchanged.
        """
        _require_utc(self.available_at, "available_at")
        _require_text(self.model_version, "model_version")
        if len(set(self.security_ids)) != len(self.security_ids):
            raise ValueError("factor matrix security identities must be unique")
        if len(set(self.factor_names)) != len(self.factor_names):
            raise ValueError("factor matrix names must be unique")
        if any(not name.strip() for name in self.factor_names):
            raise ValueError("factor matrix names must not be empty")
        if len(self.values) != len(self.security_ids):
            raise ValueError("factor matrix row count must match security_ids")
        for row in self.values:
            if len(row) != len(self.factor_names):
                raise ValueError("factor matrix column count must match factor_names")


@dataclass(frozen=True, slots=True)
class AnalysisManifest:
    """Record every semantic version needed to reproduce an analysis.

    Attributes:
        normalization_version: Provider-normalization version.
        provider_mapping_version: Provider-field mapping version.
        model_version: Financial or quantitative methodology version.
        engine_version: Runtime implementation version.
        executed_at: UTC execution instant.
        schema_version: Canonical schema version, fixed to v1 for this module.
    """

    normalization_version: str
    provider_mapping_version: str
    model_version: str
    engine_version: str
    executed_at: datetime
    schema_version: str = SCHEMA_VERSION

    def __post_init__(self) -> None:
        """Validate version labels, canonical version, and UTC execution time.

        Raises:
            ValueError: If a version is empty, schema version differs from v1,
                or execution time is not UTC.

        Side Effects:
            None; the frozen value remains unchanged.
        """
        for field_name in (
            "normalization_version",
            "provider_mapping_version",
            "model_version",
            "engine_version",
        ):
            _require_text(str(getattr(self, field_name)), field_name)
        if self.schema_version != SCHEMA_VERSION:
            raise ValueError(f"schema_version must be {SCHEMA_VERSION}")
        _require_utc(self.executed_at, "executed_at")


@dataclass(frozen=True, slots=True)
class BacktestSpecification:
    """Represent a versioned point-in-time backtest request.

    Attributes:
        specification_id: Permanent request identity.
        strategy_version: Strategy and parameter-set version.
        start_date: Inclusive first business date.
        end_date: Inclusive final business date.
        base_currency: Reporting currency.
        created_at: UTC instant the immutable specification was created.
    """

    specification_id: UUID
    strategy_version: str
    start_date: date
    end_date: date
    base_currency: Currency
    created_at: datetime

    def __post_init__(self) -> None:
        """Validate strategy label, date range, and UTC creation time.

        Raises:
            ValueError: If the label is empty, end precedes start, or creation
                time is not UTC.

        Side Effects:
            None; the frozen value remains unchanged.
        """
        _require_text(self.strategy_version, "strategy_version")
        if self.end_date < self.start_date:
            raise ValueError("backtest end_date may not precede start_date")
        _require_utc(self.created_at, "created_at")


@dataclass(frozen=True, slots=True)
class BacktestResult:
    """Represent the minimal versioned outcome of a backtest.

    Attributes:
        specification_id: Identity of the request that produced the result.
        engine_version: Engine implementation version.
        completed_at: UTC completion instant.
        total_return: Finite decimal return where 0.15 means fifteen percent.
        manifest: Reproducibility and lineage versions.
    """

    specification_id: UUID
    engine_version: str
    completed_at: datetime
    total_return: Ratio
    manifest: AnalysisManifest

    def __post_init__(self) -> None:
        """Validate engine label and UTC completion time.

        Raises:
            ValueError: If engine version is empty or completion is not UTC.

        Side Effects:
            None; the frozen value remains unchanged.
        """
        _require_text(self.engine_version, "engine_version")
        _require_utc(self.completed_at, "completed_at")


@dataclass(frozen=True, slots=True)
class SimulationSpecification:
    """Represent a versioned simulation request.

    Attributes:
        specification_id: Permanent request identity.
        model_version: Simulation methodology and parameter-set version.
        paths: Positive number of simulated paths.
        horizon_periods: Positive number of model periods per path.
        created_at: UTC instant the immutable specification was created.
    """

    specification_id: UUID
    model_version: str
    paths: int
    horizon_periods: int
    created_at: datetime

    def __post_init__(self) -> None:
        """Validate model label, positive sizes, and UTC creation time.

        Raises:
            ValueError: If labels are empty, sizes are not positive, or time is
                not UTC.

        Side Effects:
            None; the frozen value remains unchanged.
        """
        _require_text(self.model_version, "model_version")
        if self.paths <= 0 or self.horizon_periods <= 0:
            raise ValueError("simulation paths and horizon_periods must be positive")
        _require_utc(self.created_at, "created_at")


@dataclass(frozen=True, slots=True)
class SimulationResult:
    """Represent versioned simulation percentile outputs.

    Attributes:
        specification_id: Identity of the request that produced the result.
        engine_version: Engine implementation version.
        completed_at: UTC completion instant.
        percentiles: Deterministically named finite percentile values.
        manifest: Reproducibility and lineage versions.
    """

    specification_id: UUID
    engine_version: str
    completed_at: datetime
    percentiles: dict[str, float]
    manifest: AnalysisManifest

    def __post_init__(self) -> None:
        """Validate labels, UTC completion, and finite percentile values.

        Raises:
            ValueError: If labels are empty, completion is not UTC, or a
                percentile value is non-finite.

        Side Effects:
            None; the frozen value remains unchanged.
        """
        _require_text(self.engine_version, "engine_version")
        _require_utc(self.completed_at, "completed_at")
        if any(not name.strip() for name in self.percentiles):
            raise ValueError("simulation percentile names must not be empty")
        if any(not math.isfinite(value) for value in self.percentiles.values()):
            raise ValueError("simulation percentile values must be finite")


def _primitive_json_value(value: object) -> JsonValue | object:
    """Convert primitive canonical wrappers or return the internal sentinel.

    Args:
        value: Candidate primitive, enum, currency, ratio, or basis-point value.

    Returns:
        A JSON scalar when supported, otherwise ``_JSON_UNHANDLED``.

    Raises:
        ValueError: If a float is NaN or infinite.

    Side Effects:
        None.
    """
    if value is None or isinstance(value, (bool, int)):
        return value
    if isinstance(value, Enum):
        return _primitive_json_value(value.value)
    if isinstance(value, Currency):
        return value.code
    if isinstance(value, (Ratio, BasisPoints)):
        return _primitive_json_value(value.value)
    if isinstance(value, str):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError("JSON analytical values must be finite")
        return value
    return _JSON_UNHANDLED


def _standard_json_value(value: object) -> JsonValue | object:
    """Convert exact and temporal standard-library values or return a sentinel.

    Args:
        value: Candidate decimal, UUID, date, or datetime.

    Returns:
        Exact JSON text when supported, otherwise ``_JSON_UNHANDLED``.

    Raises:
        ValueError: If a decimal is non-finite or a datetime is not UTC.

    Side Effects:
        None.
    """
    if isinstance(value, Decimal):
        if not value.is_finite():
            raise ValueError("JSON decimal values must be finite")
        return format(value, "f")
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, datetime):
        _require_utc(value, "datetime")
        return value.isoformat().replace("+00:00", "Z")
    if isinstance(value, date):
        return value.isoformat()
    return _JSON_UNHANDLED


def to_json_value(value: object) -> JsonValue:
    """Convert a canonical record to an exact JSON-compatible value.

    Decimals become non-exponent text, UUIDs become canonical strings, dates
    use ISO format, and datetimes use an explicit ``Z`` UTC suffix. The
    function is deterministic for tuples and dataclass field order. It does not
    emit JSON text or accept arbitrary object serialization hooks.

    Args:
        value: Canonical dataclass, enum, scalar, UUID, decimal, date, datetime,
            list, tuple, or string-keyed dictionary.

    Returns:
        A recursively JSON-compatible value that preserves exact decimals and
        temporal meaning.

    Raises:
        TypeError: If ``value`` is outside the supported canonical value set.
        ValueError: If a datetime is not timezone-aware UTC or a float is not
            finite.

    Side Effects:
        None.
    """
    primitive = _primitive_json_value(value)
    if primitive is not _JSON_UNHANDLED:
        return primitive  # type: ignore[return-value]
    standard = _standard_json_value(value)
    if standard is not _JSON_UNHANDLED:
        return standard  # type: ignore[return-value]
    if is_dataclass(value) and not isinstance(value, type):
        return {
            field_def.name: to_json_value(getattr(value, field_def.name))
            for field_def in fields(value)
        }
    if isinstance(value, (list, tuple)):
        return [to_json_value(item) for item in value]
    if isinstance(value, dict):
        if not all(isinstance(key, str) for key in value):
            raise TypeError("canonical JSON dictionaries require string keys")
        return {str(key): to_json_value(item) for key, item in value.items()}
    raise TypeError(f"unsupported canonical JSON value: {type(value).__name__}")
