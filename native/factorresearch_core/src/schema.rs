//! Serde representations of Cenvarn canonical schema v1.
//!
//! Exact decimals use `rust_decimal` and serialize as strings. Business dates
//! and UTC instants use `time`; permanent identities use UUIDs. These structs
//! own transport meaning only and must not acquire provider or product logic.

use rust_decimal::Decimal;
use serde::{Deserialize, Serialize};
use std::collections::BTreeMap;
use time::{Date, OffsetDateTime};
use uuid::Uuid;

/// Serialize and parse canonical business dates as ISO `YYYY-MM-DD` text.
mod iso_date {
    use serde::{Deserialize, Deserializer, Serializer, de::Error as _};
    use time::{Date, format_description};

    /// Serialize a business date without time or timezone fields.
    pub fn serialize<S>(value: &Date, serializer: S) -> Result<S::Ok, S::Error>
    where
        S: Serializer,
    {
        serializer.serialize_str(&value.to_string())
    }

    /// Deserialize a strict canonical business date.
    pub fn deserialize<'de, D>(deserializer: D) -> Result<Date, D::Error>
    where
        D: Deserializer<'de>,
    {
        let value = String::deserialize(deserializer)?;
        let format = format_description::parse_borrowed::<3>("[year]-[month]-[day]")
            .map_err(D::Error::custom)?;
        Date::parse(&value, &format).map_err(D::Error::custom)
    }
}

/// Semantic version shared with JSON Schema, Python, TypeScript, Arrow, and OpenAPI.
pub const CANONICAL_SCHEMA_VERSION: &str = "1.0.0";

/// Explicit availability and data-quality state for a canonical value.
#[derive(Clone, Debug, Deserialize, Eq, PartialEq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum AvailabilityStatus {
    Available,
    Missing,
    NotApplicable,
    Stale,
    Invalid,
    ProviderFailed,
    InsufficientHistory,
    PolicySuppressed,
}

/// Corporate-action treatment already applied to a price.
#[derive(Clone, Debug, Deserialize, Eq, PartialEq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum PriceAdjustment {
    Raw,
    SplitAdjusted,
    TotalReturnAdjusted,
}

/// Exact monetary value with explicit denomination.
#[derive(Clone, Debug, Deserialize, Eq, PartialEq, Serialize)]
pub struct Money {
    #[serde(with = "rust_decimal::serde::str")]
    pub amount: Decimal,
    pub currency: String,
}

/// Exact price with explicit denomination and adjustment basis.
#[derive(Clone, Debug, Deserialize, Eq, PartialEq, Serialize)]
pub struct Price {
    #[serde(with = "rust_decimal::serde::str")]
    pub amount: Decimal,
    pub currency: String,
    pub adjustment: PriceAdjustment,
}

/// Exact quantity and its explicit unit.
#[derive(Clone, Debug, Deserialize, Eq, PartialEq, Serialize)]
pub struct Quantity {
    #[serde(with = "rust_decimal::serde::str")]
    pub amount: Decimal,
    pub unit: String,
}

/// Source and point-in-time lineage for one observation.
#[derive(Clone, Debug, Deserialize, Eq, PartialEq, Serialize)]
pub struct Provenance {
    pub provider: String,
    pub source_record_id: String,
    pub source_uri: Option<String>,
    #[serde(with = "time::serde::rfc3339")]
    pub observed_at: OffsetDateTime,
    #[serde(with = "time::serde::rfc3339")]
    pub available_at: OffsetDateTime,
    #[serde(with = "time::serde::rfc3339")]
    pub ingested_at: OffsetDateTime,
    pub normalization_version: String,
    pub filing_version: Option<String>,
}

/// Tagged exact value that never substitutes zero for unavailable data.
#[derive(Clone, Debug, Deserialize, Eq, PartialEq, Serialize)]
pub struct ObservedDecimal {
    pub status: AvailabilityStatus,
    #[serde(with = "rust_decimal::serde::str_option")]
    pub value: Option<Decimal>,
    pub reason: Option<String>,
    pub provenance: Option<Provenance>,
}

/// Tagged analytical value that never substitutes zero for unavailable data.
#[derive(Clone, Debug, Deserialize, PartialEq, Serialize)]
pub struct ObservedRatio {
    pub status: AvailabilityStatus,
    pub value: Option<f64>,
    pub reason: Option<String>,
    pub provenance: Option<Provenance>,
}

/// One exact point-in-time listing price.
#[derive(Clone, Debug, Deserialize, Eq, PartialEq, Serialize)]
pub struct PriceObservation {
    pub listing_id: Uuid,
    #[serde(with = "iso_date")]
    pub observation_date: Date,
    pub price: Price,
    #[serde(with = "time::serde::rfc3339")]
    pub available_at: OffsetDateTime,
    pub provenance: Provenance,
}

/// Bounded fiscal reporting period using business dates.
#[derive(Clone, Debug, Deserialize, Eq, PartialEq, Serialize)]
pub struct FiscalPeriod {
    pub fiscal_year: i32,
    pub period: String,
    #[serde(with = "iso_date")]
    pub start_date: Date,
    #[serde(with = "iso_date")]
    pub end_date: Date,
}

/// Immutable filing or amendment identity.
#[derive(Clone, Debug, Deserialize, Eq, PartialEq, Serialize)]
pub struct FilingVersion {
    pub filing_id: Uuid,
    pub accession: String,
    #[serde(with = "time::serde::rfc3339")]
    pub filed_at: OffsetDateTime,
    #[serde(with = "time::serde::rfc3339")]
    pub accepted_at: OffsetDateTime,
    pub amendment: u32,
}

/// Point-in-time accounting fact with exact value, unit, and filing lineage.
#[derive(Clone, Debug, Deserialize, Eq, PartialEq, Serialize)]
pub struct FinancialFact {
    pub entity_id: Uuid,
    pub concept: String,
    pub period: FiscalPeriod,
    pub value: ObservedDecimal,
    pub unit: String,
    pub currency: Option<String>,
    pub filing: Option<FilingVersion>,
}

/// Immutable security-level corporate action.
#[derive(Clone, Debug, Deserialize, Eq, PartialEq, Serialize)]
pub struct CorporateAction {
    pub security_id: Uuid,
    pub action_id: Uuid,
    pub action_type: String,
    #[serde(with = "iso_date")]
    pub effective_date: Date,
    pub value: ObservedDecimal,
    pub provenance: Provenance,
}

/// One exact point-in-time foreign-exchange rate.
#[derive(Clone, Debug, Deserialize, Eq, PartialEq, Serialize)]
pub struct FxObservation {
    pub base_currency: String,
    pub quote_currency: String,
    #[serde(with = "iso_date")]
    pub observation_date: Date,
    pub rate: ObservedDecimal,
    #[serde(with = "time::serde::rfc3339")]
    pub available_at: OffsetDateTime,
    pub provenance: Provenance,
}

/// Immutable portfolio-ledger event; authorization remains server-side.
#[derive(Clone, Debug, Deserialize, Eq, PartialEq, Serialize)]
pub struct PortfolioTransaction {
    pub transaction_id: Uuid,
    pub portfolio_id: Uuid,
    pub listing_id: Uuid,
    pub transaction_type: String,
    pub quantity: Quantity,
    pub unit_price: Option<Price>,
    #[serde(with = "time::serde::rfc3339")]
    pub executed_at: OffsetDateTime,
    #[serde(with = "time::serde::rfc3339")]
    pub recorded_at: OffsetDateTime,
}

/// One versioned point-in-time factor value.
#[derive(Clone, Debug, Deserialize, PartialEq, Serialize)]
pub struct FactorObservation {
    pub security_id: Uuid,
    pub factor: String,
    #[serde(with = "iso_date")]
    pub as_of_date: Date,
    #[serde(with = "time::serde::rfc3339")]
    pub available_at: OffsetDateTime,
    pub value: ObservedRatio,
    pub model_version: String,
}

/// Dense row-major point-in-time factor matrix.
#[derive(Clone, Debug, Deserialize, PartialEq, Serialize)]
pub struct FactorMatrix {
    #[serde(with = "iso_date")]
    pub as_of_date: Date,
    #[serde(with = "time::serde::rfc3339")]
    pub available_at: OffsetDateTime,
    pub security_ids: Vec<Uuid>,
    pub factor_names: Vec<String>,
    pub values: Vec<Vec<ObservedRatio>>,
    pub model_version: String,
}

/// Versions required to reproduce one analysis.
#[derive(Clone, Debug, Deserialize, Eq, PartialEq, Serialize)]
pub struct AnalysisManifest {
    pub schema_version: String,
    pub normalization_version: String,
    pub provider_mapping_version: String,
    pub model_version: String,
    pub engine_version: String,
    #[serde(with = "time::serde::rfc3339")]
    pub executed_at: OffsetDateTime,
}

/// Immutable control object for a point-in-time backtest.
#[derive(Clone, Debug, Deserialize, Eq, PartialEq, Serialize)]
pub struct BacktestSpecification {
    pub specification_id: Uuid,
    pub strategy_version: String,
    #[serde(with = "iso_date")]
    pub start_date: Date,
    #[serde(with = "iso_date")]
    pub end_date: Date,
    pub base_currency: String,
    #[serde(with = "time::serde::rfc3339")]
    pub created_at: OffsetDateTime,
}

/// Minimal versioned backtest outcome shared between runtimes.
#[derive(Clone, Debug, Deserialize, PartialEq, Serialize)]
pub struct BacktestResult {
    pub specification_id: Uuid,
    pub engine_version: String,
    #[serde(with = "time::serde::rfc3339")]
    pub completed_at: OffsetDateTime,
    pub total_return: f64,
    pub manifest: AnalysisManifest,
}

/// Immutable control object for one simulation run.
#[derive(Clone, Debug, Deserialize, Eq, PartialEq, Serialize)]
pub struct SimulationSpecification {
    pub specification_id: Uuid,
    pub model_version: String,
    pub paths: u64,
    pub horizon_periods: u64,
    #[serde(with = "time::serde::rfc3339")]
    pub created_at: OffsetDateTime,
}

/// Versioned simulation percentiles shared between runtimes.
#[derive(Clone, Debug, Deserialize, PartialEq, Serialize)]
pub struct SimulationResult {
    pub specification_id: Uuid,
    pub engine_version: String,
    #[serde(with = "time::serde::rfc3339")]
    pub completed_at: OffsetDateTime,
    pub percentiles: BTreeMap<String, f64>,
    pub manifest: AnalysisManifest,
}

#[cfg(test)]
mod tests {
    use super::PriceObservation;
    use serde_json::Value;

    /// Prove the Rust Serde representation preserves the shared golden record.
    #[test]
    fn price_observation_matches_language_neutral_fixture() {
        let fixture: Value = serde_json::from_str(include_str!(
            "../../../tests/fixtures/issue_137_price_observations.json"
        ))
        .expect("golden fixture must be valid JSON");
        let raw = fixture["records"][0].clone();
        let record: PriceObservation =
            serde_json::from_value(raw.clone()).expect("fixture must match Rust contract");
        assert_eq!(
            serde_json::to_value(record).expect("Rust contract must serialize"),
            raw
        );
    }
}
