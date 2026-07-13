"""Deterministic French filing normalization and public scoring gates."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from . import CanonicalFinancials, CanonicalSharesOutstanding, DataQualityIssue, DataQualityReport
from .france import FranceProviderAdapter, normalize_france_symbol

PUBLIC_CONFIDENCE = {"regulatory_verified", "issuer_verified", "licensed_source_verified", "cross_checked"}
INTERNAL_CONFIDENCE = "provider_normalized_internal_only"
REQUIRED_FIELDS = ("revenue", "net_inc", "total_assets", "tot_lib", "equity")
SUPPORTED_ACCOUNTING_STANDARDS = {"IFRS", "EU-ADOPTED IFRS", "FRENCH GAAP"}
SUPPORTED_EXCHANGES = {"EURONEXT PARIS", "XPAR"}
VERIFIED_SOURCE_MARKERS = ("AMF", "EURONEXT", "ISSUER", "LICENSED")
MIN_ANNUAL_PERIODS = 3

# Unknown French labels are deliberately excluded: they cannot silently score.
FIELD_ALIASES = {
    "revenue": ("revenue", "sales", "chiffre_affaires", "chiffre_d_affaires"),
    "earnings": ("earnings", "net_income", "net_inc", "resultat_net", "resultat_net_part_du_groupe"),
    "net_inc": ("net_inc", "net_income", "earnings", "resultat_net", "resultat_net_part_du_groupe"),
    "eps": ("eps", "basic_eps", "diluted_eps", "earnings_per_share", "resultat_par_action"),
    "op_income": ("op_income", "operating_income", "resultat_operationnel"),
    "ebit": ("ebit", "resultat_avant_interets_et_impots"),
    "cur_ast": ("cur_ast", "current_assets", "actifs_courants"),
    "cur_lib": ("cur_lib", "current_liabilities", "passifs_courants"),
    "cash": ("cash", "cash_and_equivalents", "tresorerie", "tresorerie_et_equivalents_de_tresorerie"),
    "lt_debt": ("lt_debt", "long_term_debt", "dettes_financieres_non_courantes"),
    "tot_lib": ("tot_lib", "total_liabilities", "liabilities", "total_des_passifs"),
    "total_assets": ("total_assets", "assets", "total_des_actifs"),
    "equity": ("equity", "shareholders_equity", "total_equity", "capitaux_propres"),
    "bvps": ("bvps", "book_value_per_share", "actif_net_par_action"),
    "ppe": ("ppe", "ppe_net", "property_plant_equipment", "immobilisations_corporelles"),
    "retained_earnings": ("retained_earnings", "benefices_non_repartis", "reserves_et_resultats"),
    "op_cf": ("op_cf", "operating_cash_flow", "flux_de_tresorerie_lies_aux_activites_operationnelles"),
    "cashflow": ("cashflow", "operating_cash_flow", "op_cf"),
    "capex": ("capex", "capital_expenditure", "investissements_en_immobilisations"),
}


@dataclass(frozen=True)
class FranceNormalizationResult:
    symbol: str
    can_score: bool
    sec_facts: dict[str, Any]
    quality_report: DataQualityReport


def build_france_scoring_facts(provider: FranceProviderAdapter, symbol: str, *, allow_internal: bool = False) -> FranceNormalizationResult:
    symbol = normalize_france_symbol(symbol)
    financials, shares = provider.get_financials(symbol), provider.get_shares_outstanding(symbol)
    issues = _validate(financials, shares, allow_internal)
    report = DataQualityReport("FR", not any(item.severity == "error" for item in issues), _confidence(financials), tuple(issues))
    return FranceNormalizationResult(symbol, report.can_score, _to_sec_facts(financials, shares, report) if report.can_score else {}, report)


def _validate(financials: CanonicalFinancials, shares: CanonicalSharesOutstanding, allow_internal: bool) -> list[DataQualityIssue]:
    issues: list[DataQualityIssue] = []; company = financials.company; provenance = _provenance(financials)
    if not company.regulator_id: issues.append(_issue("missing_regulator_id", "French issuer needs an LEI, AMF identifier, or issuer identifier.", "regulator_id"))
    if str(company.exchange or "").upper() not in SUPPORTED_EXCHANGES: issues.append(_issue("unsupported_exchange", "French issuer exchange must be Euronext Paris or XPAR.", "exchange"))
    if company.security_type != "ordinary_share": issues.append(_issue("unsupported_security_type", "French public scoring supports ordinary shares only.", "security_type"))
    if not financials.source_documents: issues.append(_issue("missing_source_documents", "French financials need source filing documents."))
    if not allow_internal and financials.source_documents and not any(marker in doc.source.upper() for doc in financials.source_documents for marker in VERIFIED_SOURCE_MARKERS): issues.append(_issue("unverified_france_source", "French public scoring requires AMF, Euronext Paris, issuer, or licensed-source evidence.", "source_documents"))
    for doc in financials.source_documents:
        if not _confidence_allowed(doc.confidence, allow_internal): issues.append(_issue("weak_document_confidence", "Source document is not public-score quality.", "source_documents"))
    annual = {(p.fiscal_year, p.period_end) for p in financials.periods if p.fiscal_period.upper() == "FY"}
    if len(annual) < MIN_ANNUAL_PERIODS: issues.append(_issue("insufficient_annual_history", "French scoring needs at least three distinct annual periods.", "periods"))
    currencies = {str(p.currency).upper() for p in financials.periods if p.currency}
    if any(not p.currency for p in financials.periods): issues.append(_issue("missing_currency", "French fiscal periods need explicit currency.", "currency"))
    if len(currencies) > 1: issues.append(_issue("mixed_reporting_currencies", "French scoring cannot combine fiscal periods in different currencies.", "currency"))
    for field in REQUIRED_FIELDS:
        rows, item = _records(financials, field), provenance.get(field)
        if not rows: issues.append(_issue("missing_required_fact", f"Missing required French fact: {field}.", field))
        elif len(_annual_keys(rows)) < MIN_ANNUAL_PERIODS: issues.append(_issue("insufficient_fact_history", f"French fact {field} needs three annual periods.", field))
        if item is None: issues.append(_issue("missing_fact_provenance", f"Missing provenance for French fact: {field}.", field))
        elif not _confidence_allowed(item.confidence, allow_internal): issues.append(_issue("weak_fact_confidence", f"Weak provenance confidence for French fact: {field}.", field))
        elif _standard(item.accounting_standard) not in SUPPORTED_ACCOUNTING_STANDARDS: issues.append(_issue("unsupported_accounting_standard", f"French fact {field} needs explicit IFRS or French GAAP mapping.", field))
    if not shares.shares_outstanding or shares.shares_outstanding <= 0: issues.append(_issue("missing_shares", "French scoring needs positive shares outstanding.", "shares"))
    if not shares.as_of or not shares.source: issues.append(_issue("missing_shares_evidence", "French shares need a dated source.", "shares"))
    for row in financials.balance_sheet:
        assets, liabilities, equity = (_value(row, name) for name in ("total_assets", "tot_lib", "equity"))
        if None not in (assets, liabilities, equity) and abs(assets - (liabilities + equity)) > max(abs(assets) * .01, 1): issues.append(_issue("balance_sheet_not_reconciled", "French balance sheet does not reconcile assets to liabilities plus equity.", "balance_sheet"))
    return issues


def _to_sec_facts(financials: CanonicalFinancials, shares: CanonicalSharesOutstanding, report: DataQualityReport) -> dict[str, Any]:
    provenance = _provenance(financials)
    result: dict[str, Any] = {"name": financials.company.name or financials.company.symbol, "sector": None, "source_market": "FR", "source_country": "France", "source_regulator": _regulator(financials), "normalization_confidence": report.confidence, "can_score": report.can_score, "data_quality_issues": [asdict(item) for item in report.issues], "regulator_id": financials.company.regulator_id, "security_type": financials.company.security_type, "accounting_standard": financials.company.accounting_standard}
    for field in FIELD_ALIASES:
        rows = _records(financials, field)
        if rows: result[field] = [_record(row, field, financials, provenance.get(field)) for row in rows]
    period = financials.periods[0] if financials.periods else None
    result["shares"] = [{"value": shares.shares_outstanding, "end": shares.as_of, "year": period.fiscal_year if period else None, "currency": period.currency if period else financials.company.currency, "source_market": "FR", "source": shares.source, "confidence": report.confidence}]
    if "bvps" not in result and result.get("equity"):
        result["bvps"] = [{**result["equity"][0], "value": result["equity"][0]["value"] / shares.shares_outstanding, "source": shares.source, "normalization_method": "equity_divided_by_shares_outstanding"}]
    return result


def _record(row, field, financials, provenance):
    period = next((item for item in financials.periods if item.period_end == (row.get("period_end") or row.get("end")) or item.fiscal_year == (row.get("fiscal_year") or row.get("year"))), financials.periods[0] if financials.periods else None)
    result = {"value": _value(row, field), "year": row.get("fiscal_year") or row.get("year") or (period.fiscal_year if period else None), "end": row.get("period_end") or row.get("end") or (period.period_end if period else None), "currency": row.get("currency") or (period.currency if period else financials.company.currency), "source_market": "FR"}
    if provenance: result.update({"source_document_id": provenance.source_document_id, "source_url": provenance.source_url, "confidence": provenance.confidence, "accounting_standard": provenance.accounting_standard})
    return result
def _records(financials, field): return [row for row in (*financials.income_statement, *financials.balance_sheet, *financials.cash_flow) if _value(row, field) is not None]
def _value(row, field):
    for name in FIELD_ALIASES.get(field, (field,)):
        try:
            if row.get(name) is not None: return float(row[name])
        except (TypeError, ValueError): pass
    return None
def _annual_keys(rows): return {(row.get("fiscal_year") or row.get("year"), row.get("period_end") or row.get("end")) for row in rows if str(row.get("fiscal_period") or row.get("period") or "FY").upper() == "FY"}
def _provenance(financials):
    return {field: item for item in financials.provenance for field, names in FIELD_ALIASES.items() if item.fact_name in names}
def _standard(value):
    raw = str(value or "").upper().replace("_", " ").strip()
    return {"INTERNATIONAL FINANCIAL REPORTING STANDARDS": "IFRS", "EU ADOPTED IFRS": "EU-ADOPTED IFRS", "FRENCH GENERALLY ACCEPTED ACCOUNTING PRINCIPLES": "FRENCH GAAP"}.get(raw, raw)
def _confidence_allowed(value, internal): return value in PUBLIC_CONFIDENCE or (internal and value == INTERNAL_CONFIDENCE)
def _confidence(financials):
    values = [item.confidence for item in (*financials.source_documents, *financials.provenance)]
    if INTERNAL_CONFIDENCE in values: return INTERNAL_CONFIDENCE
    return next((item for item in ("regulatory_verified", "issuer_verified", "licensed_source_verified", "cross_checked") if item in values), "insufficient_source_evidence")
def _regulator(financials):
    sources = {item.source.upper() for item in financials.source_documents}
    if any("AMF" in item for item in sources): return "AMF"
    if any("EURONEXT" in item for item in sources): return "Euronext Paris"
    if any("ISSUER" in item for item in sources): return "issuer filing"
    return "verified source"
def _issue(code, message, field=None): return DataQualityIssue(code, message, "error", field)
