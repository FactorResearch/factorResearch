"""UK canonical-to-scoring bridge with brand-safe validation gates."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from . import (
    CanonicalFinancials,
    CanonicalSharesOutstanding,
    DataQualityIssue,
    DataQualityReport,
    StatementProvenance,
)
from .uk import UKProviderAdapter, normalize_uk_symbol


PUBLIC_CONFIDENCE = {
    "regulatory_verified",
    "issuer_verified",
    "licensed_source_verified",
    "cross_checked",
}
INTERNAL_CONFIDENCE = "provider_normalized_internal_only"

FIELD_ALIASES = {
    "revenue": ("revenue", "sales"),
    "earnings": ("earnings", "net_income", "net_inc"),
    "net_inc": ("net_inc", "net_income", "earnings"),
    "eps": ("eps", "basic_eps", "diluted_eps", "earnings_per_share"),
    "op_income": ("op_income", "operating_income"),
    "ebit": ("ebit",),
    "cur_ast": ("cur_ast", "current_assets"),
    "cur_lib": ("cur_lib", "current_liabilities"),
    "cash": ("cash", "cash_and_equivalents"),
    "lt_debt": ("lt_debt", "long_term_debt"),
    "tot_lib": ("tot_lib", "total_liabilities", "liabilities"),
    "total_assets": ("total_assets", "assets"),
    "equity": ("equity", "shareholders_equity", "total_equity"),
    "bvps": ("bvps", "book_value_per_share"),
    "ppe": ("ppe", "ppe_net", "property_plant_equipment"),
    "retained_earnings": ("retained_earnings",),
    "op_cf": ("op_cf", "operating_cash_flow", "cashflow"),
    "cashflow": ("cashflow", "operating_cash_flow", "op_cf"),
    "capex": ("capex", "capital_expenditure", "capital_expenditures"),
}

REQUIRED_FIELDS = ("revenue", "net_inc", "total_assets", "tot_lib", "equity")
SUPPORTED_ACCOUNTING_STANDARDS = {
    "IFRS",
    "UK-ADOPTED IFRS",
    "UK GAAP",
    "FRS 101",
    "FRS 102",
}
SUPPORTED_SECURITY_TYPES = {"ordinary_share", "adr", "investment_trust"}
PUBLIC_SCORING_SECURITY_TYPES = {"ordinary_share"}
SUPPORTED_EXCHANGES = {"LSE", "AIM", "AQUIS"}
MIN_ANNUAL_PERIODS = 3
VERIFIED_SOURCE_MARKERS = (
    "COMPANIES HOUSE",
    "FCA",
    "NSM",
    "ISSUER",
    "LICENSED",
)


@dataclass(frozen=True)
class UKNormalizationResult:
    symbol: str
    can_score: bool
    sec_facts: dict[str, Any]
    quality_report: DataQualityReport


def build_uk_scoring_facts(
    provider: UKProviderAdapter,
    symbol: str,
    *,
    allow_internal: bool = False,
) -> UKNormalizationResult:
    """Return SEC-shaped facts only when UK data passes source gates."""
    normalized_symbol = normalize_uk_symbol(symbol)
    financials = provider.get_financials(normalized_symbol)
    shares = provider.get_shares_outstanding(normalized_symbol)
    issues = _validate_financials(financials, shares, allow_internal=allow_internal)
    confidence = _overall_confidence(financials)
    can_score = not any(issue.severity == "error" for issue in issues)
    report = DataQualityReport(
        market="GB",
        can_score=can_score,
        confidence=confidence,
        issues=tuple(issues),
    )

    if not can_score:
        return UKNormalizationResult(normalized_symbol, False, {}, report)

    sec_facts = _to_sec_facts(financials, shares, report)
    return UKNormalizationResult(normalized_symbol, True, sec_facts, report)


def _validate_financials(
    financials: CanonicalFinancials,
    shares: CanonicalSharesOutstanding,
    *,
    allow_internal: bool,
) -> list[DataQualityIssue]:
    issues: list[DataQualityIssue] = []
    provenance_by_field = _provenance_by_field(financials.provenance)
    company = financials.company

    if not company.regulator_id:
        issues.append(_issue(
            "missing_regulator_id",
            "UK issuer identity needs a Companies House number or regulator identifier.",
            field="regulator_id",
        ))

    if str(company.exchange or "").upper() not in SUPPORTED_EXCHANGES:
        issues.append(_issue(
            "unsupported_exchange",
            "UK issuer exchange must be explicitly identified as LSE, AIM, or AQUIS.",
            field="exchange",
        ))

    if company.security_type not in SUPPORTED_SECURITY_TYPES:
        issues.append(_issue(
            "missing_or_unknown_security_type",
            "UK security type must be ordinary_share, adr, or investment_trust.",
            field="security_type",
        ))
    elif company.security_type not in PUBLIC_SCORING_SECURITY_TYPES:
        issues.append(_issue(
            "unsupported_scoring_security_type",
            f"UK {company.security_type} securities require a dedicated scoring model.",
            field="security_type",
        ))

    if not financials.source_documents:
        issues.append(_issue("missing_source_documents", "UK financials need source filing documents."))

    if not financials.periods:
        issues.append(_issue("missing_periods", "UK financials need normalized fiscal periods."))

    for document in financials.source_documents:
        if not _confidence_allowed(document.confidence, allow_internal):
            issues.append(_issue(
                "weak_document_confidence",
                f"Source document {document.document_id or '<unknown>'} is not public-score quality.",
                field="source_documents",
            ))

    if not allow_internal and financials.source_documents and not any(
        marker in document.source.upper()
        for document in financials.source_documents
        for marker in VERIFIED_SOURCE_MARKERS
    ):
        issues.append(_issue(
            "unverified_uk_source",
            "UK public scoring requires Companies House, FCA NSM, issuer, or licensed-source evidence.",
            field="source_documents",
        ))

    for field in REQUIRED_FIELDS:
        records = _records_for_field(financials, field)
        if not records:
            issues.append(_issue("missing_required_fact", f"Missing required UK fact: {field}.", field=field))
        elif len(_annual_record_keys(records)) < MIN_ANNUAL_PERIODS:
            issues.append(_issue(
                "insufficient_fact_history",
                f"UK fact {field} needs at least {MIN_ANNUAL_PERIODS} distinct annual periods.",
                field=field,
            ))
        provenance = provenance_by_field.get(field)
        if provenance is None:
            issues.append(_issue("missing_fact_provenance", f"Missing provenance for UK fact: {field}.", field=field))
        elif not _confidence_allowed(provenance.confidence, allow_internal):
            issues.append(_issue("weak_fact_confidence", f"Weak provenance confidence for UK fact: {field}.", field=field))
        elif _normalize_accounting_standard(provenance.accounting_standard) not in SUPPORTED_ACCOUNTING_STANDARDS:
            issues.append(_issue(
                "unsupported_accounting_standard",
                f"UK fact {field} needs explicit IFRS or UK GAAP mapping.",
                field=field,
            ))

    if not shares.shares_outstanding or shares.shares_outstanding <= 0:
        issues.append(_issue("missing_shares", "UK scoring needs positive shares outstanding.", field="shares"))
    if not shares.as_of:
        issues.append(_issue("missing_shares_date", "UK shares outstanding needs an as-of date.", field="shares"))
    if not shares.source:
        issues.append(_issue("missing_shares_source", "UK shares outstanding needs a source.", field="shares"))

    currencies = set()
    annual_periods = {
        (period.fiscal_year, period.period_end)
        for period in financials.periods
        if str(period.fiscal_period).upper() == "FY"
    }
    if len(annual_periods) < MIN_ANNUAL_PERIODS:
        issues.append(_issue(
            "insufficient_annual_history",
            f"UK scoring needs at least {MIN_ANNUAL_PERIODS} distinct annual fiscal periods.",
            field="periods",
        ))
    for period in financials.periods:
        if not period.currency:
            issues.append(_issue("missing_currency", "UK fiscal period needs an explicit currency.", field="currency"))
        else:
            currency = period.currency.upper()
            currencies.add(currency)
            if len(currency) != 3 or not currency.isalpha():
                issues.append(_issue(
                    "invalid_currency",
                    f"UK fiscal period has invalid ISO currency: {period.currency}.",
                    field="currency",
                ))
    if len(currencies) > 1:
        issues.append(_issue(
            "mixed_reporting_currencies",
            "UK historical scoring cannot combine fiscal periods reported in different currencies.",
            field="currency",
        ))

    for balance in financials.balance_sheet:
        assets = _field_value(balance, "total_assets")
        liabilities = _field_value(balance, "tot_lib")
        equity = _field_value(balance, "equity")
        if assets is not None and liabilities is not None and equity is not None:
            tolerance = max(abs(assets) * 0.01, 1.0)
            if abs(assets - (liabilities + equity)) <= tolerance:
                continue
            issues.append(_issue(
                "balance_sheet_not_reconciled",
                "UK balance sheet does not reconcile assets to liabilities plus equity "
                f"for {balance.get('period_end') or balance.get('fiscal_year') or 'a period'}.",
                field="balance_sheet",
            ))

    return issues


def _to_sec_facts(
    financials: CanonicalFinancials,
    shares: CanonicalSharesOutstanding,
    report: DataQualityReport,
) -> dict[str, Any]:
    provenance_by_field = _provenance_by_field(financials.provenance)
    sec_facts: dict[str, Any] = {
        "name": financials.company.name or financials.company.symbol,
        "sector": None,
        "source_market": "GB",
        "source_country": "United Kingdom",
        "source_regulator": _source_regulator(financials),
        "normalization_confidence": report.confidence,
        "can_score": report.can_score,
        "data_quality_issues": [asdict(issue) for issue in report.issues],
        "regulator_id": financials.company.regulator_id,
        "security_type": financials.company.security_type,
        "accounting_standard": financials.company.accounting_standard,
    }

    for target_field in FIELD_ALIASES:
        records = _records_for_field(financials, target_field)
        if records:
            sec_facts[target_field] = [
                _sec_record(
                    row,
                    target_field,
                    financials,
                    _provenance_for_row(financials.provenance, target_field, row)
                    or provenance_by_field.get(target_field),
                )
                for row in records
            ]

    first_period = financials.periods[0] if financials.periods else None
    sec_facts["shares"] = [{
        "value": shares.shares_outstanding,
        "end": shares.as_of,
        "year": first_period.fiscal_year if first_period else None,
        "currency": first_period.currency if first_period else financials.company.currency,
        "source_market": "GB",
        "source": shares.source,
        "confidence": report.confidence,
    }]
    if "bvps" not in sec_facts:
        derived_bvps = _derive_latest_bvps(sec_facts, shares)
        if derived_bvps:
            sec_facts["bvps"] = [derived_bvps]
    return sec_facts


def _derive_latest_bvps(
    sec_facts: dict[str, Any],
    shares: CanonicalSharesOutstanding,
) -> dict[str, Any] | None:
    equity = (sec_facts.get("equity") or [None])[0]
    share_count = shares.shares_outstanding
    if not equity or not share_count or share_count <= 0:
        return None
    value = equity.get("value")
    if value is None:
        return None
    return {
        **equity,
        "value": value / share_count,
        "source": shares.source,
        "normalization_method": "equity_divided_by_shares_outstanding",
    }


def _records_for_field(financials: CanonicalFinancials, field: str) -> list[dict[str, Any]]:
    rows = list(financials.income_statement) + list(financials.balance_sheet) + list(financials.cash_flow)
    return [row for row in rows if _field_value(row, field) is not None]


def _annual_record_keys(rows: list[dict[str, Any]]) -> set[tuple[Any, Any]]:
    return {
        (row.get("fiscal_year") or row.get("year"), row.get("period_end") or row.get("end"))
        for row in rows
        if str(row.get("fiscal_period") or row.get("period") or "FY").upper() == "FY"
    }


def _sec_record(
    row: dict[str, Any],
    field: str,
    financials: CanonicalFinancials,
    provenance: StatementProvenance | None,
) -> dict[str, Any]:
    period = _period_for_row(financials, row)
    record = {
        "value": _field_value(row, field),
        "year": row.get("fiscal_year") or row.get("year") or (period.fiscal_year if period else None),
        "end": row.get("period_end") or row.get("end") or row.get("end_date") or (period.period_end if period else None),
        "currency": row.get("currency") or (period.currency if period else financials.company.currency),
        "source_market": "GB",
    }
    if provenance:
        record.update({
            "source_document_id": provenance.source_document_id,
            "source_url": provenance.source_url,
            "confidence": provenance.confidence,
            "accounting_standard": provenance.accounting_standard,
        })
    return record


def _period_for_row(financials: CanonicalFinancials, row: dict[str, Any]):
    year = row.get("fiscal_year") or row.get("year")
    end = row.get("period_end") or row.get("end") or row.get("end_date")
    for period in financials.periods:
        if period.period_end == end or period.fiscal_year == year:
            return period
    return financials.periods[0] if financials.periods else None


def _field_value(row: dict[str, Any] | None, field: str) -> float | None:
    if not row:
        return None
    for alias in FIELD_ALIASES.get(field, (field,)):
        value = row.get(alias)
        if value is not None:
            try:
                return float(value)
            except (TypeError, ValueError):
                return None
    return None


def _latest_row(rows: tuple[dict, ...]) -> dict[str, Any] | None:
    return rows[0] if rows else None


def _provenance_by_field(items: tuple[StatementProvenance, ...]) -> dict[str, StatementProvenance]:
    result: dict[str, StatementProvenance] = {}
    for item in items:
        for field, aliases in FIELD_ALIASES.items():
            if item.fact_name == field or item.fact_name in aliases:
                result.setdefault(field, item)
    return result


def _provenance_for_row(
    items: tuple[StatementProvenance, ...],
    field: str,
    row: dict[str, Any],
) -> StatementProvenance | None:
    year = row.get("fiscal_year") or row.get("year")
    period = row.get("fiscal_period") or row.get("period") or "FY"
    aliases = FIELD_ALIASES.get(field, (field,))
    for item in items:
        if item.fact_name not in aliases and item.fact_name != field:
            continue
        if item.fiscal_year == year and (item.fiscal_period or "FY") == period:
            return item
    return None


def _source_regulator(financials: CanonicalFinancials) -> str:
    sources = {document.source.upper() for document in financials.source_documents}
    if any("FCA" in source or "NSM" in source for source in sources):
        return "FCA NSM"
    if any("COMPANIES HOUSE" in source for source in sources):
        return "Companies House"
    if any("ISSUER" in source for source in sources):
        return "issuer filing"
    return "verified source"


def _normalize_accounting_standard(value: str | None) -> str:
    normalized = str(value or "").strip().upper().replace("_", " ")
    aliases = {
        "UK ADOPTED IFRS": "UK-ADOPTED IFRS",
        "UK-ADOPTED INTERNATIONAL ACCOUNTING STANDARDS": "UK-ADOPTED IFRS",
        "INTERNATIONAL FINANCIAL REPORTING STANDARDS": "IFRS",
    }
    return aliases.get(normalized, normalized)


def _confidence_allowed(confidence: str, allow_internal: bool) -> bool:
    if confidence in PUBLIC_CONFIDENCE:
        return True
    return allow_internal and confidence == INTERNAL_CONFIDENCE


def _overall_confidence(financials: CanonicalFinancials) -> str:
    confidences = [doc.confidence for doc in financials.source_documents]
    confidences.extend(item.confidence for item in financials.provenance)
    if any(value == INTERNAL_CONFIDENCE for value in confidences):
        return INTERNAL_CONFIDENCE
    for confidence in ("regulatory_verified", "issuer_verified", "licensed_source_verified", "cross_checked"):
        if confidence in confidences:
            return confidence
    return "insufficient_source_evidence"


def _issue(code: str, message: str, field: str | None = None) -> DataQualityIssue:
    return DataQualityIssue(code=code, message=message, severity="error", field=field)
