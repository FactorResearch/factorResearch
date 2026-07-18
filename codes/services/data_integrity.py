"""Validation boundary for external financial data (ISSUE_050).

This service validates provider payloads before they reach persistence or
scoring. It owns schema/type, temporal, range, and cross-field checks, keeps a
last-known-valid value for safe in-process fallback, and records rejected
payload metadata through the audit journal without logging raw financial data.
Provider adapters remain responsible for normalization into canonical fields.
"""

from __future__ import annotations

import hashlib
import math
from dataclasses import dataclass
from datetime import date, datetime, timezone
from threading import RLock
from typing import Any

from codes.services.audit_journal import audit_journal

_REQUIRED_SEC_FIELDS = ("name", "cik", "filer_type")
_NUMERIC_FIELDS = {
    "eps", "bvps", "cur_ast", "cur_lib", "lt_debt", "tot_lib", "equity",
    "shares", "total_assets", "cash", "net_inc", "revenue", "gross_profit",
    "op_income", "op_cf", "capex", "r_and_d", "acquisitions", "dividends",
}


@dataclass(frozen=True)
class IntegrityIssue:
    """A safe, machine-readable validation finding."""

    code: str
    message: str
    severity: str = "error"
    field: str | None = None


@dataclass(frozen=True)
class IntegrityReport:
    """Validation result and quality score for one provider response."""

    provider: str
    symbol: str
    accepted: bool
    quality_score: int
    issues: tuple[IntegrityIssue, ...] = ()
    used_last_known_valid: bool = False


class FinancialDataIntegrityEngine:
    """Validate, quarantine, and safely retain normalized financial payloads."""

    def __init__(self) -> None:
        self._last_valid: dict[tuple[str, str], dict[str, Any]] = {}
        self._quarantine: list[dict[str, Any]] = []
        self._lock = RLock()

    def validate(self, provider: str, symbol: str, payload: dict[str, Any]) -> IntegrityReport:
        """Validate a normalized SEC-shaped financial payload without mutation."""
        issues: list[IntegrityIssue] = []
        if not isinstance(payload, dict):
            issues.append(IntegrityIssue("schema_payload_type", "Provider payload must be an object."))
            return self._report(provider, symbol, issues)
        for field in _REQUIRED_SEC_FIELDS:
            if not payload.get(field):
                issues.append(IntegrityIssue("missing_required_field", f"Required field is missing: {field}.", field=field))
        for field in _NUMERIC_FIELDS:
            records = payload.get(field)
            if records is None:
                continue
            if not isinstance(records, list):
                issues.append(IntegrityIssue("schema_record_type", f"Field {field} must be a list.", field=field))
                continue
            self._validate_records(field, records, issues)
        self._validate_cross_fields(payload, issues)
        return self._report(provider, symbol, issues)

    def accept(self, provider: str, symbol: str, payload: dict[str, Any], report: IntegrityReport) -> dict[str, Any] | None:
        """Accept valid data or quarantine it and return the last valid value."""
        key = (str(provider).lower(), str(symbol).upper())
        with self._lock:
            if report.accepted:
                self._last_valid[key] = dict(payload)
                return payload
            fingerprint = hashlib.sha256(repr(sorted(payload.items())).encode("utf-8")).hexdigest()
            quarantine = {
                "provider": key[0], "symbol": key[1], "fingerprint": fingerprint,
                "quality_score": report.quality_score,
                "issue_codes": [issue.code for issue in report.issues],
                "received_at": datetime.now(timezone.utc).isoformat(),
            }
            self._quarantine.append(quarantine)
            audit_journal.record(
                "provider_data_validation",
                action="quarantine",
                component=key[0],
                outcome="rejected",
                details={"symbol": key[1], "quality_score": report.quality_score, "issue_codes": quarantine["issue_codes"]},
            )
            fallback = self._last_valid.get(key)
            return dict(fallback) if fallback is not None else None

    def quarantine_records(self) -> tuple[dict[str, Any], ...]:
        """Return redacted quarantine metadata for diagnostics and tests."""
        with self._lock:
            return tuple(dict(item) for item in self._quarantine)

    @staticmethod
    def _validate_records(field: str, records: list[Any], issues: list[IntegrityIssue]) -> None:
        years: set[int] = set()
        for index, record in enumerate(records):
            if not isinstance(record, dict):
                issues.append(IntegrityIssue("schema_record_type", f"{field}[{index}] must be an object.", field=field))
                continue
            _validate_record_value(field, index, record.get("value"), issues)
            parsed_year = _parse_record_year(field, index, record.get("year"), issues)
            if parsed_year is not None:
                if parsed_year in years:
                    issues.append(IntegrityIssue("duplicate_period", f"{field} contains duplicate annual periods.", field=field))
                years.add(parsed_year)

    @staticmethod
    def _validate_cross_fields(payload: dict[str, Any], issues: list[IntegrityIssue]) -> None:
        assets = _latest_value(payload.get("total_assets"))
        liabilities = _latest_value(payload.get("tot_lib"))
        equity = _latest_value(payload.get("equity"))
        if assets is not None and liabilities is not None and equity is not None:
            tolerance = max(abs(assets) * 0.01, 1.0)
            if abs(assets - liabilities - equity) > tolerance:
                issues.append(IntegrityIssue("balance_sheet_not_reconciled", "Assets do not reconcile to liabilities plus equity.", field="balance_sheet"))
        shares = _latest_value(payload.get("shares"))
        if shares is not None and shares <= 0:
            issues.append(IntegrityIssue("invalid_shares", "Shares outstanding must be positive.", field="shares"))

    @staticmethod
    def _report(provider: str, symbol: str, issues: list[IntegrityIssue]) -> IntegrityReport:
        score = max(0, 100 - 25 * len(issues))
        return IntegrityReport(str(provider), str(symbol).upper(), not issues, score, tuple(issues))


def _latest_value(records: Any) -> float | None:
    if not isinstance(records, list) or not records:
        return None
    value = records[0].get("value") if isinstance(records[0], dict) else None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _validate_record_value(field: str, index: int, value: Any, issues: list[IntegrityIssue]) -> None:
    if value is None:
        return
    try:
        number = float(value)
    except (TypeError, ValueError):
        issues.append(IntegrityIssue("non_numeric_value", f"{field}[{index}] value is not numeric.", field=field))
        return
    if not math.isfinite(number):
        issues.append(IntegrityIssue("non_finite_value", f"{field}[{index}] value is not finite.", field=field))


def _parse_record_year(field: str, index: int, year: Any, issues: list[IntegrityIssue]) -> int | None:
    if year is None:
        return None
    try:
        parsed_year = int(year)
    except (TypeError, ValueError):
        issues.append(IntegrityIssue("invalid_period", f"{field}[{index}] year is invalid.", field=field))
        return None
    if parsed_year < 1900 or parsed_year > date.today().year + 1:
        issues.append(IntegrityIssue("invalid_period", f"{field}[{index}] year is outside the supported range.", field=field))
    return parsed_year


financial_data_integrity = FinancialDataIntegrityEngine()
