"""Authoritative SEC ingestion for eligible Canadian cross-listed issuers.

The SEC path is intentionally narrow: it accepts only issuers whose EDGAR
identity is Canadian and whose annual filings expose enough standardized XBRL
facts to pass the normal Canada quality gate. TSX-only issuers still require a
licensed SEDAR+ or issuer-document extraction source.
"""

from __future__ import annotations

import datetime as dt
import os
import re
from dataclasses import dataclass
from typing import Any

import lxml.html
import requests

from . import (
    CanonicalCompany,
    CanonicalFinancials,
    CanonicalFiscalPeriod,
    CanonicalSharesOutstanding,
    FilingDocument,
    StatementProvenance,
)
from .canada import is_canadian_symbol, normalize_canada_symbol
from .canada_db import ingest_verified_canada_financials
from .canada_normalization import REQUIRED_FIELDS, CanadaNormalizationResult

TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"
SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik}.json"
COMPANYFACTS_URL = "https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json"
ARCHIVE_DOCUMENT_URL = "https://www.sec.gov/Archives/edgar/data/{cik}/{accession}/{document}"
ARCHIVE_INDEX_URL = (
    "https://www.sec.gov/Archives/edgar/data/{cik}/{accession_path}/{accession}-index.html"
)

ANNUAL_FORMS = {"10-K", "10-K/A", "20-F", "20-F/A", "40-F", "40-F/A"}
BASE_ANNUAL_FORMS = {"10-K", "20-F", "40-F"}
CANADIAN_EDGAR_CODES = {"A0", "A1", "A2", "A3", "A4", "A5", "A6", "A7", "A8", "A9", "B0", "Z4"}
EXCHANGE_BY_SUFFIX = {".TO": "TSX", ".V": "TSXV", ".CN": "CSE", ".NE": "NEO"}
DEFAULT_YEARS = 11


class CanadaSecAcquisitionError(ValueError):
    """Raised before persistence when EDGAR cannot support an issuer safely."""


@dataclass(frozen=True)
class _FactSpec:
    name: str
    statement: str
    unit_kind: str
    candidates: tuple[tuple[str, str], ...]


_FACT_SPECS = (
    _FactSpec("revenue", "income", "money", (
        ("ifrs-full", "Revenue"),
        ("ifrs-full", "InsuranceRevenue"),
        ("us-gaap", "Revenues"),
        ("us-gaap", "RevenueFromContractWithCustomerExcludingAssessedTax"),
        ("us-gaap", "SalesRevenueNet"),
        ("us-gaap", "InterestAndDividendIncomeOperating"),
        ("us-gaap", "RevenuesNetOfInterestExpense"),
        ("us-gaap", "InterestAndNoninterestIncome"),
    )),
    _FactSpec("net_inc", "income", "money", (
        ("ifrs-full", "ProfitLoss"),
        ("ifrs-full", "ProfitLossAttributableToOwnersOfParent"),
        ("us-gaap", "NetIncomeLoss"),
        ("us-gaap", "ProfitLoss"),
        ("us-gaap", "NetIncomeLossAvailableToCommonStockholdersBasic"),
    )),
    _FactSpec("eps", "income", "per_share", (
        ("ifrs-full", "BasicEarningsLossPerShare"),
        ("ifrs-full", "DilutedEarningsLossPerShare"),
        ("us-gaap", "EarningsPerShareBasic"),
        ("us-gaap", "EarningsPerShareDiluted"),
    )),
    _FactSpec("op_income", "income", "money", (
        ("ifrs-full", "ProfitLossFromOperatingActivities"),
        ("us-gaap", "OperatingIncomeLoss"),
        ("us-gaap", "IncomeLossFromContinuingOperationsBeforeIncomeTaxesExtraordinaryItemsNoncontrollingInterest"),
    )),
    _FactSpec("gross_profit", "income", "money", (
        ("ifrs-full", "GrossProfit"),
        ("us-gaap", "GrossProfit"),
    )),
    _FactSpec("total_assets", "balance", "money", (
        ("ifrs-full", "Assets"),
        ("us-gaap", "Assets"),
    )),
    _FactSpec("tot_lib", "balance", "money", (
        ("ifrs-full", "Liabilities"),
        ("us-gaap", "Liabilities"),
    )),
    _FactSpec("equity", "balance", "money", (
        ("ifrs-full", "Equity"),
        ("ifrs-full", "EquityAttributableToOwnersOfParent"),
        ("us-gaap", "StockholdersEquity"),
        ("us-gaap", "StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest"),
    )),
    _FactSpec("cur_ast", "balance", "money", (
        ("ifrs-full", "CurrentAssets"),
        ("us-gaap", "AssetsCurrent"),
    )),
    _FactSpec("cur_lib", "balance", "money", (
        ("ifrs-full", "CurrentLiabilities"),
        ("us-gaap", "LiabilitiesCurrent"),
    )),
    _FactSpec("cash", "balance", "money", (
        ("ifrs-full", "CashAndCashEquivalents"),
        ("ifrs-full", "CashAndCashEquivalentsAndOtherShorttermInvestments"),
        ("us-gaap", "CashAndCashEquivalentsAtCarryingValue"),
        ("us-gaap", "CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents"),
    )),
    _FactSpec("lt_debt", "balance", "money", (
        ("ifrs-full", "NoncurrentBorrowings"),
        ("us-gaap", "LongTermDebtNoncurrent"),
        ("us-gaap", "LongTermDebt"),
    )),
    _FactSpec("retained_earnings", "balance", "money", (
        ("ifrs-full", "RetainedEarnings"),
        ("us-gaap", "RetainedEarningsAccumulatedDeficit"),
    )),
    _FactSpec("ppe_net", "balance", "money", (
        ("ifrs-full", "PropertyPlantAndEquipment"),
        ("us-gaap", "PropertyPlantAndEquipmentNet"),
    )),
    _FactSpec("goodwill", "balance", "money", (
        ("ifrs-full", "Goodwill"),
        ("us-gaap", "Goodwill"),
    )),
    _FactSpec("inventory", "balance", "money", (
        ("ifrs-full", "Inventories"),
        ("us-gaap", "InventoryNet"),
    )),
    _FactSpec("op_cf", "cash_flow", "money", (
        ("ifrs-full", "CashFlowsFromUsedInOperatingActivities"),
        ("us-gaap", "NetCashProvidedByUsedInOperatingActivities"),
        ("us-gaap", "NetCashProvidedByUsedInOperatingActivitiesContinuingOperations"),
    )),
    _FactSpec("capex", "cash_flow", "money", (
        ("ifrs-full", "PurchaseOfPropertyPlantAndEquipment"),
        ("us-gaap", "PaymentsToAcquirePropertyPlantAndEquipment"),
        ("us-gaap", "PaymentsForAdditionsToPropertyPlantAndEquipment"),
    )),
    _FactSpec("dividends", "cash_flow", "money", (
        ("ifrs-full", "DividendsPaidClassifiedAsFinancingActivities"),
        ("ifrs-full", "DividendsPaidOrdinaryShares"),
        ("us-gaap", "PaymentsOfDividendsCommonStock"),
        ("us-gaap", "PaymentsOfDividends"),
    )),
    _FactSpec("r_and_d", "cash_flow", "money", (
        ("ifrs-full", "ResearchAndDevelopmentExpense"),
        ("us-gaap", "ResearchAndDevelopmentExpense"),
    )),
)

_SPEC_BY_NAME = {spec.name: spec for spec in _FACT_SPECS}


def import_canada_sec_filings(
    symbol: str,
    *,
    sec_ticker: str | None = None,
    years: int = DEFAULT_YEARS,
    session: Any = None,
) -> CanadaNormalizationResult:
    """Acquire an eligible Canadian issuer from EDGAR and persist atomically."""
    financials, shares = acquire_canada_sec_financials(
        symbol,
        sec_ticker=sec_ticker,
        years=years,
        session=session,
    )
    return ingest_verified_canada_financials(symbol, financials, shares)


def acquire_canada_sec_financials(
    symbol: str,
    *,
    sec_ticker: str | None = None,
    years: int = DEFAULT_YEARS,
    session: Any = None,
) -> tuple[CanonicalFinancials, CanonicalSharesOutstanding]:
    """Return canonical annual facts without writing downloaded source payloads."""
    normalized_symbol = normalize_canada_symbol(symbol)
    if not is_canadian_symbol(normalized_symbol):
        raise CanadaSecAcquisitionError(
            f"{symbol!r} is not a supported Canadian listing symbol (.TO, .V, .CN, or .NE)."
        )
    years = max(3, min(int(years), 20))
    client = session or requests
    requested_sec_ticker = (sec_ticker or _default_sec_ticker(normalized_symbol)).upper().strip()
    cik, ticker_name = _resolve_sec_ticker(client, requested_sec_ticker)
    submissions = _get_json(client, SUBMISSIONS_URL.format(cik=cik), "SEC submissions")
    _validate_canadian_identity(normalized_symbol, requested_sec_ticker, submissions)

    filing_rows = _annual_filing_rows(submissions)
    if not filing_rows:
        raise CanadaSecAcquisitionError(
            f"{normalized_symbol} has no SEC 10-K, 20-F, or 40-F annual filing. "
            "A licensed SEDAR+ or verified issuer-document source is required."
        )

    payload = _get_json(client, COMPANYFACTS_URL.format(cik=cik), "SEC CompanyFacts")
    facts = payload.get("facts") or {}
    if not facts:
        raise CanadaSecAcquisitionError(f"{normalized_symbol} has no standardized SEC CompanyFacts data.")

    currency = _detect_reporting_currency(facts, years)
    extracted = {
        spec.name: _extract_spec(facts, spec, currency, years)
        for spec in _FACT_SPECS
    }
    _derive_liabilities_if_needed(extracted, facts, currency)
    core_periods = _common_core_periods(extracted)
    if len(core_periods) < 3:
        missing = [name for name in REQUIRED_FIELDS if not extracted.get(name)]
        detail = (
            f" Missing: {', '.join(missing)}."
            if missing
            else f" Only {len(core_periods)} aligned fiscal period(s) were available; at least 3 are required."
        )
        raise CanadaSecAcquisitionError(
            f"{normalized_symbol} does not expose enough aligned annual XBRL facts for verified scoring.{detail}"
        )

    extracted = _filter_to_periods(extracted, core_periods)
    shares, shares_record = _extract_shares(
        client,
        cik,
        facts,
        filing_rows,
        years,
    )
    if shares is None or shares_record is None:
        raise CanadaSecAcquisitionError(
            f"{normalized_symbol} has no dated, authoritative shares-outstanding fact in its SEC annual filing."
        )

    filing_map = {row["accession"]: row for row in filing_rows}
    statement_rows, provenance, used_records = _canonical_statement_rows(
        extracted,
        core_periods,
        currency,
        cik,
        filing_map,
    )
    used_records.append(shares_record)
    documents = _source_documents(used_records, cik, filing_map)
    periods = tuple(
        CanonicalFiscalPeriod(year, "FY", end, currency)
        for year, end in sorted(core_periods, reverse=True)
    )
    exchange = next(
        (name for suffix, name in EXCHANGE_BY_SUFFIX.items() if normalized_symbol.endswith(suffix)),
        None,
    )
    company = CanonicalCompany(
        symbol=normalized_symbol,
        name=submissions.get("name") or ticker_name,
        exchange=exchange,
        country="Canada",
        currency=currency,
    )
    return (
        CanonicalFinancials(
            company=company,
            periods=periods,
            income_statement=tuple(statement_rows["income"]),
            balance_sheet=tuple(statement_rows["balance"]),
            cash_flow=tuple(statement_rows["cash_flow"]),
            source_documents=tuple(documents),
            provenance=tuple(provenance),
        ),
        CanonicalSharesOutstanding(
            symbol=normalized_symbol,
            shares_outstanding=shares,
            as_of=shares_record["end"],
            source=f"SEC EDGAR {shares_record['accession']}",
        ),
    )


def _resolve_sec_ticker(client: Any, ticker: str) -> tuple[str, str]:
    payload = _get_json(client, TICKERS_URL, "SEC ticker map")
    rows = payload.values() if isinstance(payload, dict) else payload
    for row in rows:
        if str(row.get("ticker") or "").upper() == ticker:
            return str(row["cik_str"]).zfill(10), str(row.get("title") or ticker)
    raise CanadaSecAcquisitionError(
        f"SEC ticker {ticker!r} was not found. For a dual listing with different symbols, pass --sec-ticker."
    )


def _validate_canadian_identity(symbol: str, sec_ticker: str, submissions: dict) -> None:
    addresses = submissions.get("addresses") or {}
    address_rows = [addresses.get("business") or {}, addresses.get("mailing") or {}]
    codes = {str(submissions.get("stateOfIncorporation") or "").upper()}
    codes.update(str(row.get("stateOrCountry") or "").upper() for row in address_rows)
    descriptions = " ".join(str(row.get("stateOrCountryDescription") or "") for row in address_rows)
    if not (codes & CANADIAN_EDGAR_CODES or "CANADA" in descriptions.upper()):
        name = submissions.get("name") or sec_ticker
        raise CanadaSecAcquisitionError(
            f"{symbol} resolved to SEC ticker {sec_ticker} ({name}), but EDGAR does not identify "
            "that issuer as Canadian. No data was written; verify the dual-list mapping with --sec-ticker."
        )


def _detect_reporting_currency(facts: dict, years: int) -> str:
    scores: dict[str, tuple[int, int]] = {}
    for currency in _monetary_units(facts):
        fields = 0
        rows = 0
        for name in REQUIRED_FIELDS:
            spec = _SPEC_BY_NAME[name]
            count = max(
                (
                    len(_annual_records(_concept_entries(facts, ns, concept, currency), years))
                    for ns, concept in spec.candidates
                ),
                default=0,
            )
            if count:
                fields += 1
                rows += count
        scores[currency] = (fields, rows)
    if not scores:
        raise CanadaSecAcquisitionError("SEC CompanyFacts contains no annual monetary reporting currency.")
    return max(scores, key=lambda code: (scores[code], code == "CAD", code))


def _monetary_units(facts: dict) -> set[str]:
    units = set()
    for spec in _FACT_SPECS:
        if spec.unit_kind != "money":
            continue
        for namespace, concept in spec.candidates:
            concept_data = (facts.get(namespace) or {}).get(concept) or {}
            for unit in (concept_data.get("units") or {}):
                if re.fullmatch(r"[A-Z]{3}", unit):
                    units.add(unit)
    return units


def _extract_spec(facts: dict, spec: _FactSpec, currency: str, years: int) -> list[dict]:
    unit = currency if spec.unit_kind == "money" else f"{currency}/shares"
    by_period: dict[tuple[int, str], dict] = {}
    for namespace, concept in spec.candidates:
        records = _annual_records(_concept_entries(facts, namespace, concept, unit), years)
        for record in records:
            record.update({
                "fact_name": spec.name,
                "namespace": namespace,
                "concept": concept,
                "currency": currency,
                "normalization_method": "canada_sec_edgar_v1",
            })
            by_period.setdefault((record["year"], record["end"]), record)
    return sorted(by_period.values(), key=lambda row: row["end"], reverse=True)[:years]


def _concept_entries(facts: dict, namespace: str, concept: str, unit: str) -> list[dict]:
    return list(
        (((facts.get(namespace) or {}).get(concept) or {}).get("units") or {}).get(unit)
        or []
    )


def _annual_records(entries: list[dict], years: int) -> list[dict]:
    by_end: dict[str, dict] = {}
    for entry in entries:
        if entry.get("form") not in ANNUAL_FORMS or entry.get("fp") not in {None, "FY"}:
            continue
        end = str(entry.get("end") or "")
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", end):
            continue
        if entry.get("start") and not _annual_duration(entry["start"], end):
            continue
        try:
            value = float(entry.get("val"))
        except (TypeError, ValueError):
            continue
        if not entry.get("accn"):
            continue
        record = {
            "year": int(end[:4]),
            "end": end,
            "value": value,
            "accession": str(entry["accn"]),
            "filed": entry.get("filed"),
            "form": entry.get("form"),
        }
        current = by_end.get(end)
        if current is None or str(record.get("filed") or "") >= str(current.get("filed") or ""):
            by_end[end] = record
    return sorted(by_end.values(), key=lambda row: row["end"], reverse=True)[:years]


def _annual_duration(start: str, end: str) -> bool:
    try:
        days = (dt.date.fromisoformat(end) - dt.date.fromisoformat(str(start))).days
    except ValueError:
        return False
    return 270 <= days <= 430


def _derive_liabilities_if_needed(
    extracted: dict[str, list[dict]],
    facts: dict,
    currency: str,
) -> None:
    existing_liabilities = {
        (row["year"], row["end"]): row for row in extracted.get("tot_lib", [])
    }
    aligned_equity = {
        (row["year"], row["end"]): row for row in extracted.get("equity", [])
    }
    for asset in extracted.get("total_assets", []):
        key = (asset["year"], asset["end"])
        if key in existing_liabilities:
            continue
        eq = _matching_record_in_accession(
            facts,
            _SPEC_BY_NAME["equity"],
            currency,
            asset["end"],
            asset["accession"],
        )
        if eq is None:
            continue
        eq.update({
            "fact_name": "equity",
            "currency": currency,
            "normalization_method": "canada_sec_edgar_v1",
        })
        aligned_equity[key] = eq
        existing_liabilities[key] = {
            **asset,
            "fact_name": "tot_lib",
            "value": asset["value"] - eq["value"],
            "concept": "AssetsMinusEquity",
            "normalization_method": "assets_minus_equity",
        }
    extracted["equity"] = [aligned_equity[key] for key in sorted(aligned_equity, reverse=True)]
    extracted["tot_lib"] = [
        existing_liabilities[key] for key in sorted(existing_liabilities, reverse=True)
    ]


def _matching_record_in_accession(
    facts: dict,
    spec: _FactSpec,
    currency: str,
    end: str,
    accession: str,
) -> dict | None:
    for namespace, concept in spec.candidates:
        for entry in _concept_entries(facts, namespace, concept, currency):
            if entry.get("form") not in ANNUAL_FORMS:
                continue
            if entry.get("end") != end or entry.get("accn") != accession:
                continue
            try:
                value = float(entry.get("val"))
            except (TypeError, ValueError):
                continue
            return {
                "year": int(end[:4]),
                "end": end,
                "value": value,
                "accession": accession,
                "filed": entry.get("filed"),
                "form": entry.get("form"),
                "namespace": namespace,
                "concept": concept,
            }
    return None


def _common_core_periods(extracted: dict[str, list[dict]]) -> set[tuple[int, str]]:
    period_sets = [
        {(row["year"], row["end"]) for row in extracted.get(name, [])}
        for name in REQUIRED_FIELDS
    ]
    if any(not periods for periods in period_sets):
        return set()
    return set.intersection(*period_sets)


def _filter_to_periods(
    extracted: dict[str, list[dict]],
    periods: set[tuple[int, str]],
) -> dict[str, list[dict]]:
    return {
        name: [row for row in rows if (row["year"], row["end"]) in periods]
        for name, rows in extracted.items()
    }


def _extract_shares(
    client: Any,
    cik: str,
    facts: dict,
    filing_rows: list[dict],
    years: int,
) -> tuple[float | None, dict | None]:
    latest_base = next((row for row in filing_rows if row["form"] in BASE_ANNUAL_FORMS), None)
    if latest_base and latest_base.get("primary_document"):
        url = _filing_url(cik, latest_base["accession"], latest_base["primary_document"])
        response = _get(client, url, "SEC annual filing")
        inline = _inline_xbrl_shares(response.content, latest_base)
        if inline:
            return inline["value"], inline

    candidates = (
        ("dei", "EntityCommonStockSharesOutstanding"),
        ("us-gaap", "CommonStockSharesOutstanding"),
    )
    best: list[dict] = []
    for namespace, concept in candidates:
        rows = _annual_records(_concept_entries(facts, namespace, concept, "shares"), years)
        rows = [row for row in rows if row["value"] > 0]
        for row in rows:
            row.update({"namespace": namespace, "concept": concept, "fact_name": "shares"})
        if len(rows) > len(best):
            best = rows
    if not best:
        return None, None
    return best[0]["value"], best[0]


def _inline_xbrl_shares(content: bytes, filing: dict) -> dict | None:
    try:
        root = lxml.html.fromstring(content)
    except (TypeError, ValueError):
        return None
    contexts: dict[str, tuple[str | None, str | None]] = {}
    for element in root.iter():
        if str(element.tag).lower() != "xbrli:context":
            continue
        instant = next(
            ("".join(child.itertext()).strip() for child in element.iter()
             if str(child.tag).lower() == "xbrli:instant"),
            None,
        )
        member = next(
            ("".join(child.itertext()).strip() for child in element.iter()
             if str(child.tag).lower().endswith(":explicitmember")
             and str(child.get("dimension") or "").lower().endswith(":statementclassofstockaxis")),
            None,
        )
        contexts[str(element.get("id") or "")] = (instant, member)

    values = []
    for element in root.iter():
        if str(element.tag).lower() != "ix:nonfraction":
            continue
        if str(element.get("name") or "").lower() != "dei:entitycommonstocksharesoutstanding":
            continue
        context_id = element.get("contextref") or ""
        instant, member = contexts.get(context_id, (None, None))
        value = _inline_number("".join(element.itertext()), element.get("scale"), element.get("sign"))
        if instant and value and value > 0:
            values.append((instant, member, value))
    if not values:
        return None
    latest = max(item[0] for item in values)
    latest_values = [item for item in values if item[0] == latest]
    dimensioned = [item for item in latest_values if item[1]]
    selected = dimensioned or latest_values
    unique = {(member or "total", value) for _instant, member, value in selected}
    return {
        "year": int(latest[:4]),
        "end": latest,
        "value": float(sum(value for _member, value in unique)),
        "accession": filing["accession"],
        "filed": filing.get("filing_date"),
        "form": filing.get("form"),
        "namespace": "dei",
        "concept": "EntityCommonStockSharesOutstanding",
        "fact_name": "shares",
    }


def _inline_number(text: str, scale: str | None, sign: str | None) -> float | None:
    value_text = re.sub(r"[^0-9.()-]", "", text or "")
    if not value_text:
        return None
    negative = value_text.startswith("(") and value_text.endswith(")")
    value_text = value_text.strip("()")
    try:
        value = float(value_text)
        value *= 10 ** int(scale or 0)
    except (TypeError, ValueError):
        return None
    if negative or sign == "-":
        value *= -1
    return value


def _canonical_statement_rows(
    extracted: dict[str, list[dict]],
    periods: set[tuple[int, str]],
    currency: str,
    cik: str,
    filing_map: dict[str, dict],
) -> tuple[dict[str, list[dict]], list[StatementProvenance], list[dict]]:
    rows: dict[str, dict[tuple[int, str], dict]] = {"income": {}, "balance": {}, "cash_flow": {}}
    provenance = []
    used_records = []
    for spec in _FACT_SPECS:
        for record in extracted.get(spec.name, []):
            key = (record["year"], record["end"])
            if key not in periods:
                continue
            item = rows[spec.statement].setdefault(key, {
                "fiscal_year": record["year"],
                "fiscal_period": "FY",
                "period_end": record["end"],
                "currency": currency,
            })
            item[spec.name] = record["value"]
            source_url = _record_url(record, cik, filing_map)
            provenance.append(StatementProvenance(
                fact_name=spec.name,
                source_document_id=record["accession"],
                fiscal_year=record["year"],
                fiscal_period="FY",
                source_url=source_url,
                confidence="regulatory_verified",
                accounting_standard=_accounting_standard(record.get("namespace")),
                extraction_method="sec_companyfacts_api",
                normalization_method=record.get("normalization_method") or "canada_sec_edgar_v1",
            ))
            used_records.append(record)
    return (
        {
            statement: [grouped[key] for key in sorted(grouped, reverse=True)]
            for statement, grouped in rows.items()
        },
        provenance,
        used_records,
    )


def _source_documents(records: list[dict], cik: str, filing_map: dict[str, dict]) -> list[FilingDocument]:
    by_accession: dict[str, list[dict]] = {}
    for record in records:
        by_accession.setdefault(record["accession"], []).append(record)
    documents = []
    for accession, accession_records in by_accession.items():
        metadata = filing_map.get(accession) or {}
        documents.append(FilingDocument(
            document_id=accession,
            source="SEC EDGAR",
            url=_record_url(accession_records[0], cik, filing_map),
            filing_date=metadata.get("filing_date") or accession_records[0].get("filed"),
            period_end=(
                metadata.get("report_date")
                or max(
                    (str(row.get("end") or "") for row in accession_records if row.get("fact_name") != "shares"),
                    default="",
                )
                or None
            ),
            form=metadata.get("form") or accession_records[0].get("form"),
            confidence="regulatory_verified",
        ))
    return sorted(documents, key=lambda document: document.filing_date or "", reverse=True)


def _accounting_standard(namespace: str | None) -> str:
    return "IFRS" if namespace == "ifrs-full" else "US-GAAP"


def _annual_filing_rows(submissions: dict) -> list[dict]:
    recent = ((submissions.get("filings") or {}).get("recent") or {})
    rows = []
    for index, form in enumerate(recent.get("form") or []):
        filing_date = _list_value(recent, "filingDate", index)
        report_date = _list_value(recent, "reportDate", index)
        accession = _list_value(recent, "accessionNumber", index)
        document = _list_value(recent, "primaryDocument", index)
        if form not in ANNUAL_FORMS or not accession:
            continue
        rows.append({
            "form": form,
            "filing_date": filing_date,
            "report_date": report_date,
            "accession": accession,
            "primary_document": document,
        })
    return sorted(rows, key=lambda row: row["filing_date"] or "", reverse=True)


def _list_value(mapping: dict, key: str, index: int):
    values = mapping.get(key) or []
    return values[index] if index < len(values) else None


def _record_url(record: dict, cik: str, filing_map: dict[str, dict]) -> str:
    metadata = filing_map.get(record["accession"]) or {}
    return _filing_url(cik, record["accession"], metadata.get("primary_document"))


def _filing_url(cik: str, accession: str, primary_document: str | None) -> str:
    cik_int = str(int(cik))
    accession_path = accession.replace("-", "")
    if primary_document:
        return ARCHIVE_DOCUMENT_URL.format(
            cik=cik_int,
            accession=accession_path,
            document=primary_document,
        )
    return ARCHIVE_INDEX_URL.format(
        cik=cik_int,
        accession_path=accession_path,
        accession=accession,
    )


def _default_sec_ticker(symbol: str) -> str:
    return next(symbol[:-len(suffix)] for suffix in EXCHANGE_BY_SUFFIX if symbol.endswith(suffix))


def _get_json(client: Any, url: str, label: str) -> dict:
    response = _get(client, url, label)
    try:
        return response.json()
    except ValueError as exc:
        raise CanadaSecAcquisitionError(f"{label} returned invalid JSON.") from exc


def _get(client: Any, url: str, label: str):
    headers = {
        "User-Agent": os.getenv("SEC_USER_AGENT", "GrahamScoreApp/1.0 contact@example.com"),
        "Accept-Encoding": "gzip, deflate",
    }
    try:
        response = client.get(url, headers=headers, timeout=30)
        response.raise_for_status()
        return response
    except requests.RequestException as exc:
        raise CanadaSecAcquisitionError(f"{label} request failed: {exc}") from exc
