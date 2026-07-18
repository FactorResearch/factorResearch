"""Acceptance tests for ISSUE_050 financial data validation and quarantine."""

from codes.services.data_integrity import FinancialDataIntegrityEngine


def _payload(**overrides):
    payload = {
        "name": "Example Corp",
        "cik": "0000000001",
        "filer_type": "us",
        "total_assets": [{"year": 2024, "value": 150}],
        "tot_lib": [{"year": 2024, "value": 50}],
        "equity": [{"year": 2024, "value": 100}],
        "shares": [{"year": 2024, "value": 10}],
        "revenue": [{"year": 2024, "value": 200}],
    }
    payload.update(overrides)
    return payload


def test_valid_payload_is_accepted_and_scored() -> None:
    engine = FinancialDataIntegrityEngine()
    report = engine.validate("sec", "EX", _payload())
    assert report.accepted is True
    assert report.quality_score == 100


def test_invalid_payload_is_quarantined_and_cannot_be_accepted() -> None:
    engine = FinancialDataIntegrityEngine()
    invalid = _payload(total_assets=[{"year": 2024, "value": 999}], shares=[{"year": 2024, "value": -1}])
    report = engine.validate("sec", "EX", invalid)
    assert report.accepted is False
    assert {issue.code for issue in report.issues} == {"balance_sheet_not_reconciled", "invalid_shares"}
    assert engine.accept("sec", "EX", invalid, report) is None
    assert engine.quarantine_records()[0]["symbol"] == "EX"


def test_invalid_refresh_preserves_last_known_valid_payload() -> None:
    engine = FinancialDataIntegrityEngine()
    valid = _payload()
    valid_report = engine.validate("sec", "EX", valid)
    engine.accept("sec", "EX", valid, valid_report)
    invalid = _payload(total_assets=[{"year": 2024, "value": 999}])
    invalid_report = engine.validate("sec", "EX", invalid)

    assert engine.accept("sec", "EX", invalid, invalid_report) == valid
