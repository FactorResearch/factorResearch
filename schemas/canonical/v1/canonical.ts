/** Canonical schema semantic version consumed by generated and hand-written clients. */
export const CANONICAL_SCHEMA_VERSION = "1.0.0" as const;

/** Permanent UUID identity for an issuer or legal entity; never a ticker alias. */
export type EntityId = string;
/** Permanent UUID identity for one fungible security. */
export type SecurityId = string;
/** Permanent UUID identity for one venue-specific listing. */
export type ListingId = string;
/** Permanent UUID identity for an external identifier assignment. */
export type IdentifierId = string;
/** Uppercase three-letter currency code. */
export type Currency = string;
/** Base-10 exact numeric text without exponent notation. */
export type DecimalString = string;

/** Explicit availability and data-quality states shared by every runtime. */
export type AvailabilityStatus =
    | "available"
    | "missing"
    | "not_applicable"
    | "stale"
    | "invalid"
    | "provider_failed"
    | "insufficient_history"
    | "policy_suppressed";

/** Corporate-action treatment already applied to a price. */
export type PriceAdjustment =
    | "raw"
    | "split_adjusted"
    | "total_return_adjusted";

/** Exact monetary value with explicit denomination. */
export interface Money {
    amount: DecimalString;
    currency: Currency;
}

/** Exact price with explicit denomination and adjustment basis. */
export interface Price extends Money {
    adjustment: PriceAdjustment;
}

/** Exact quantity whose signed amount is interpreted in the named unit. */
export interface Quantity {
    amount: DecimalString;
    unit: string;
}

/** Source and point-in-time lineage for one canonical observation. */
export interface Provenance {
    provider: string;
    source_record_id: string;
    source_uri: string | null;
    observed_at: string;
    available_at: string;
    ingested_at: string;
    normalization_version: string;
    filing_version: string | null;
}

/** Tagged exact value that never substitutes zero for unavailable data. */
export interface ObservedDecimal {
    status: AvailabilityStatus;
    value: DecimalString | null;
    reason: string | null;
    provenance: Provenance | null;
}

/** Tagged analytical value that never substitutes zero for unavailable data. */
export interface ObservedRatio {
    status: AvailabilityStatus;
    value: number | null;
    reason: string | null;
    provenance: Provenance | null;
}

/** Bounded fiscal reporting period using business dates. */
export interface FiscalPeriod {
    fiscal_year: number;
    period: "FY" | "Q1" | "Q2" | "Q3" | "Q4" | "H1" | "H2" | "TTM";
    start_date: string;
    end_date: string;
}

/** Immutable filing or amendment identity. */
export interface FilingVersion {
    filing_id: string;
    accession: string;
    filed_at: string;
    accepted_at: string;
    amendment: number;
}

/** Point-in-time accounting fact with exact value, unit, and filing lineage. */
export interface FinancialFact {
    entity_id: EntityId;
    concept: string;
    period: FiscalPeriod;
    value: ObservedDecimal;
    unit: string;
    currency: Currency | null;
    filing: FilingVersion | null;
}

/** Immutable security-level corporate action. */
export interface CorporateAction {
    security_id: SecurityId;
    action_id: string;
    action_type: "split" | "cash_dividend" | "stock_dividend" | "spinoff" | "merger";
    effective_date: string;
    value: ObservedDecimal;
    provenance: Provenance;
}

/** One exact point-in-time listing price. */
export interface PriceObservation {
    listing_id: ListingId;
    observation_date: string;
    price: Price;
    available_at: string;
    provenance: Provenance;
}

/** One exact point-in-time foreign-exchange rate. */
export interface FxObservation {
    base_currency: Currency;
    quote_currency: Currency;
    observation_date: string;
    rate: ObservedDecimal;
    available_at: string;
    provenance: Provenance;
}

/** Immutable portfolio-ledger event; authorization remains server-side. */
export interface PortfolioTransaction {
    transaction_id: string;
    portfolio_id: string;
    listing_id: ListingId;
    transaction_type: "buy" | "sell" | "deposit" | "withdrawal" | "dividend" | "fee" | "tax";
    quantity: Quantity;
    unit_price: Price | null;
    executed_at: string;
    recorded_at: string;
}

/** One versioned point-in-time factor value. */
export interface FactorObservation {
    security_id: SecurityId;
    factor: string;
    as_of_date: string;
    available_at: string;
    value: ObservedRatio;
    model_version: string;
}

/** Dense row-major point-in-time factor matrix. */
export interface FactorMatrix {
    as_of_date: string;
    available_at: string;
    security_ids: SecurityId[];
    factor_names: string[];
    values: ObservedRatio[][];
    model_version: string;
}

/** Versions required to reproduce one analysis. */
export interface AnalysisManifest {
    schema_version: typeof CANONICAL_SCHEMA_VERSION;
    normalization_version: string;
    provider_mapping_version: string;
    model_version: string;
    engine_version: string;
    executed_at: string;
}

/** Immutable control object for a point-in-time backtest. */
export interface BacktestSpecification {
    specification_id: string;
    strategy_version: string;
    start_date: string;
    end_date: string;
    base_currency: Currency;
    created_at: string;
}

/** Minimal versioned backtest outcome shared between runtimes. */
export interface BacktestResult {
    specification_id: string;
    engine_version: string;
    completed_at: string;
    total_return: number;
    manifest: AnalysisManifest;
}

/** Immutable control object for one simulation run. */
export interface SimulationSpecification {
    specification_id: string;
    model_version: string;
    paths: number;
    horizon_periods: number;
    created_at: string;
}

/** Versioned simulation percentiles shared between runtimes. */
export interface SimulationResult {
    specification_id: string;
    engine_version: string;
    completed_at: string;
    percentiles: Record<string, number>;
    manifest: AnalysisManifest;
}
