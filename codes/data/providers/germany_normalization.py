"""Germany canonical-to-scoring bridge with deterministic German mappings."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from . import CanonicalFinancials, CanonicalSharesOutstanding, DataQualityIssue, DataQualityReport, StatementProvenance
from .germany import GermanyProviderAdapter, normalize_germany_symbol

PUBLIC_CONFIDENCE = {"regulatory_verified", "issuer_verified", "licensed_source_verified", "cross_checked"}
INTERNAL_CONFIDENCE = "provider_normalized_internal_only"
REQUIRED_FIELDS = ("revenue", "net_inc", "total_assets", "tot_lib", "equity")
SUPPORTED_ACCOUNTING_STANDARDS = {"IFRS", "EU-ADOPTED IFRS", "HGB"}
SUPPORTED_SECURITY_TYPES = {"ordinary_share", "adr", "investment_trust"}
PUBLIC_SCORING_SECURITY_TYPES = {"ordinary_share"}
SUPPORTED_EXCHANGES = {"XETRA", "FRA", "GETTEX", "STUTTGART"}
VERIFIED_SOURCE_MARKERS = ("BAFIN", "BUNDESANZEIGER", "UNTERNEHMENSREGISTER", "DEUTSCHE BOERSE", "ISSUER", "LICENSED")
MIN_ANNUAL_PERIODS = 3

# German labels are explicit; unknown labels must not silently map to scores.
FIELD_ALIASES = {
    "revenue": ("revenue", "sales", "umsatzerloese", "umsatzerl\u00f6se", "umsatz"),
    "earnings": ("earnings", "net_income", "net_inc", "jahresueberschuss", "jahres\u00fcberschuss"),
    "net_inc": ("net_inc", "net_income", "earnings", "jahresueberschuss", "jahres\u00fcberschuss"),
    "eps": ("eps", "basic_eps", "diluted_eps", "earnings_per_share", "ergebnis_je_aktie"),
    "op_income": ("op_income", "operating_income", "betriebsergebnis"),
    "ebit": ("ebit", "ergebnis_vor_zinsen_und_steuern"),
    "cur_ast": ("cur_ast", "current_assets", "kurzfristige_vermoegenswerte", "kurzfristige_verm\u00f6genswerte"),
    "cur_lib": ("cur_lib", "current_liabilities", "kurzfristige_verbindlichkeiten"),
    "cash": ("cash", "cash_and_equivalents", "fluessige_mittel", "fl\u00fcssige_mittel"),
    "lt_debt": ("lt_debt", "long_term_debt", "langfristige_finanzverbindlichkeiten"),
    "tot_lib": ("tot_lib", "total_liabilities", "liabilities", "verbindlichkeiten"),
    "total_assets": ("total_assets", "assets", "bilanzsumme"),
    "equity": ("equity", "shareholders_equity", "total_equity", "eigenkapital"),
    "bvps": ("bvps", "book_value_per_share", "buchwert_je_aktie"),
    "ppe": ("ppe", "ppe_net", "property_plant_equipment", "sachanlagen"),
    "retained_earnings": ("retained_earnings", "gewinnruecklagen", "gewinnr\u00fccklagen"),
    "op_cf": ("op_cf", "operating_cash_flow", "cashflow", "cashflow_aus_laufender_geschaeftstaetigkeit", "cashflow_aus_laufender_gesch\u00e4ftst\u00e4tigkeit"),
    "cashflow": ("cashflow", "operating_cash_flow", "op_cf"),
    "capex": ("capex", "capital_expenditure", "capital_expenditures", "investitionen_in_sachanlagen"),
}


@dataclass(frozen=True)
class GermanyNormalizationResult:
    symbol: str
    can_score: bool
    sec_facts: dict[str, Any]
    quality_report: DataQualityReport


def build_germany_scoring_facts(provider: GermanyProviderAdapter, symbol: str, *, allow_internal: bool = False) -> GermanyNormalizationResult:
    symbol = normalize_germany_symbol(symbol)
    financials, shares = provider.get_financials(symbol), provider.get_shares_outstanding(symbol)
    issues = _validate(financials, shares, allow_internal)
    report = DataQualityReport("DE", not any(issue.severity == "error" for issue in issues), _overall_confidence(financials), tuple(issues))
    return GermanyNormalizationResult(symbol, report.can_score, _to_sec_facts(financials, shares, report) if report.can_score else {}, report)


def _validate(financials: CanonicalFinancials, shares: CanonicalSharesOutstanding, allow_internal: bool) -> list[DataQualityIssue]:
    issues: list[DataQualityIssue] = []
    company = financials.company
    provenance = _provenance_by_field(financials.provenance)
    if not company.regulator_id: issues.append(_issue("missing_regulator_id", "German issuer needs LEI, register number, or regulator identifier.", "regulator_id"))
    if str(company.exchange or "").upper() not in SUPPORTED_EXCHANGES: issues.append(_issue("unsupported_exchange", "German issuer exchange must be XETRA, FRA, GETTEX, or STUTTGART.", "exchange"))
    if company.security_type not in SUPPORTED_SECURITY_TYPES: issues.append(_issue("missing_or_unknown_security_type", "German security type must be ordinary_share, adr, or investment_trust.", "security_type"))
    elif company.security_type not in PUBLIC_SCORING_SECURITY_TYPES: issues.append(_issue("unsupported_scoring_security_type", "German ADRs and investment trusts need dedicated scoring models.", "security_type"))
    if not financials.source_documents: issues.append(_issue("missing_source_documents", "German financials need source filing documents."))
    if not allow_internal and financials.source_documents and not any(marker in doc.source.upper() for doc in financials.source_documents for marker in VERIFIED_SOURCE_MARKERS): issues.append(_issue("unverified_germany_source", "German public scoring requires BaFin, Bundesanzeiger, Unternehmensregister, issuer, Deutsche Boerse, or licensed-source evidence.", "source_documents"))
    for doc in financials.source_documents:
        if not _confidence_allowed(doc.confidence, allow_internal): issues.append(_issue("weak_document_confidence", "Source document is not public-score quality.", "source_documents"))
    annual_periods = {(p.fiscal_year, p.period_end) for p in financials.periods if p.fiscal_period.upper() == "FY"}
    if len(annual_periods) < MIN_ANNUAL_PERIODS: issues.append(_issue("insufficient_annual_history", "German scoring needs at least three distinct annual periods.", "periods"))
    currencies = {str(p.currency).upper() for p in financials.periods if p.currency}
    if any(not p.currency for p in financials.periods): issues.append(_issue("missing_currency", "German fiscal periods need explicit currency.", "currency"))
    if len(currencies) > 1: issues.append(_issue("mixed_reporting_currencies", "German scoring cannot combine fiscal periods in different currencies.", "currency"))
    for field in REQUIRED_FIELDS:
        rows = _records(financials, field)
        if not rows: issues.append(_issue("missing_required_fact", f"Missing required German fact: {field}.", field))
        elif len(_annual_keys(rows)) < MIN_ANNUAL_PERIODS: issues.append(_issue("insufficient_fact_history", f"German fact {field} needs three annual periods.", field))
        item = provenance.get(field)
        if item is None: issues.append(_issue("missing_fact_provenance", f"Missing provenance for German fact: {field}.", field))
        elif not _confidence_allowed(item.confidence, allow_internal): issues.append(_issue("weak_fact_confidence", f"Weak provenance confidence for German fact: {field}.", field))
        elif _standard(item.accounting_standard) not in SUPPORTED_ACCOUNTING_STANDARDS: issues.append(_issue("unsupported_accounting_standard", f"German fact {field} needs explicit IFRS or HGB mapping.", field))
    if not shares.shares_outstanding or shares.shares_outstanding <= 0: issues.append(_issue("missing_shares", "German scoring needs positive shares outstanding.", "shares"))
    if not shares.as_of: issues.append(_issue("missing_shares_date", "German shares outstanding needs an as-of date.", "shares"))
    if not shares.source: issues.append(_issue("missing_shares_source", "German shares outstanding needs a source.", "shares"))
    for row in financials.balance_sheet:
        assets, liabilities, equity = _value(row, "total_assets"), _value(row, "tot_lib"), _value(row, "equity")
        if None not in (assets, liabilities, equity) and abs(assets - (liabilities + equity)) > max(abs(assets) * .01, 1): issues.append(_issue("balance_sheet_not_reconciled", "German balance sheet does not reconcile assets to liabilities plus equity.", "balance_sheet"))
    return issues


def _to_sec_facts(financials: CanonicalFinancials, shares: CanonicalSharesOutstanding, report: DataQualityReport) -> dict[str, Any]:
    provenance = _provenance_by_field(financials.provenance)
    facts: dict[str, Any] = {"name": financials.company.name or financials.company.symbol, "sector": None, "source_market": "DE", "source_country": "Germany", "source_regulator": _regulator(financials), "normalization_confidence": report.confidence, "can_score": report.can_score, "data_quality_issues": [asdict(x) for x in report.issues], "regulator_id": financials.company.regulator_id, "security_type": financials.company.security_type, "accounting_standard": financials.company.accounting_standard}
    for field in FIELD_ALIASES:
        rows = _records(financials, field)
        if rows: facts[field] = [_record(row, field, financials, provenance.get(field)) for row in rows]
    period = financials.periods[0] if financials.periods else None
    facts["shares"] = [{"value": shares.shares_outstanding, "end": shares.as_of, "year": period.fiscal_year if period else None, "currency": period.currency if period else financials.company.currency, "source_market": "DE", "source": shares.source, "confidence": report.confidence}]
    if "bvps" not in facts and facts.get("equity") and shares.shares_outstanding:
        facts["bvps"] = [{**facts["equity"][0], "value": facts["equity"][0]["value"] / shares.shares_outstanding, "source": shares.source, "normalization_method": "equity_divided_by_shares_outstanding"}]
    return facts


def _record(row, field, financials, provenance):
    year = row.get("fiscal_year") or row.get("year")
    end = row.get("period_end") or row.get("end") or row.get("end_date")
    period = next((item for item in financials.periods if item.period_end == end or item.fiscal_year == year), financials.periods[0] if financials.periods else None)
    result = {"value": _value(row, field), "year": year or (period.fiscal_year if period else None), "end": end or (period.period_end if period else None), "currency": row.get("currency") or (period.currency if period else financials.company.currency), "source_market": "DE"}
    if provenance:
        result.update({"source_document_id": provenance.source_document_id, "source_url": provenance.source_url, "confidence": provenance.confidence, "accounting_standard": provenance.accounting_standard})
    return result


def _records(financials, field): return [row for row in (*financials.income_statement, *financials.balance_sheet, *financials.cash_flow) if _value(row, field) is not None]
def _value(row, field):
    for name in FIELD_ALIASES.get(field, (field,)):
        if row.get(name) is None:
            continue
        try:
            return float(row[name])
        except (TypeError, ValueError):
            continue
    return None
def _annual_keys(rows): return {(row.get("fiscal_year") or row.get("year"), row.get("period_end") or row.get("end")) for row in rows if str(row.get("fiscal_period") or row.get("period") or "FY").upper() == "FY"}
def _provenance_by_field(items):
    result = {}
    for item in items:
        for field, names in FIELD_ALIASES.items():
            if item.fact_name in names: result.setdefault(field, item)
    return result
def _standard(value):
    raw = str(value or "").upper().replace("_", " ").strip()
    return {"INTERNATIONAL FINANCIAL REPORTING STANDARDS": "IFRS", "EU ADOPTED IFRS": "EU-ADOPTED IFRS", "DEUTSCHES HANDELSGESETZBUCH": "HGB"}.get(raw, raw)
def _confidence_allowed(value, internal): return value in PUBLIC_CONFIDENCE or (internal and value == INTERNAL_CONFIDENCE)
def _overall_confidence(financials):
    values = [x.confidence for x in (*financials.source_documents, *financials.provenance)]
    if INTERNAL_CONFIDENCE in values: return INTERNAL_CONFIDENCE
    return next((value for value in ("regulatory_verified", "issuer_verified", "licensed_source_verified", "cross_checked") if value in values), "insufficient_source_evidence")
def _regulator(financials):
    sources = {x.source.upper() for x in financials.source_documents}
    if any("BAFIN" in source for source in sources): return "BaFin"
    if any("BUNDESANZEIGER" in source or "UNTERNEHMENSREGISTER" in source for source in sources): return "Unternehmensregister"
    if any("ISSUER" in source for source in sources): return "issuer filing"
    return "verified source"
def _issue(code, message, field=None): return DataQualityIssue(code, message, "error", field)
