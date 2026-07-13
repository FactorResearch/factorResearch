"""Standalone Canada verified-source ingestion worker.

By default this worker acquires official SEC filings for eligible Canadian
cross-listed issuers. Verified CSV exports remain supported for licensed
SEDAR+/issuer extraction pipelines. It never scrapes SEDAR+ and should not be
imported by the Dash app process.

Usage:
    python -m codes.workers.canada_ingest_worker --symbol SHOP.TO

    python -m codes.workers.canada_ingest_worker --symbol SHOP.TO \
        --company-csv company.csv \
        --periods-csv periods.csv \
        --documents-csv documents.csv \
        --facts-csv facts.csv \
        --shares-csv shares.csv
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from codes.data.providers.canada_ingestion import (  # noqa: E402
    CanadaVerifiedCsvBundle,
    import_canada_verified_csv_bundle,
)
from codes.data.providers.canada_normalization import PUBLIC_CONFIDENCE  # noqa: E402
from codes.data.providers.canada_sec import (  # noqa: E402
    CanadaSecAcquisitionError,
    import_canada_sec_filings,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Acquire and import verified Canada financials.")
    parser.add_argument("--symbol", required=True, help="Canadian symbol, e.g. SHOP.TO or SHOP:TSX")
    parser.add_argument(
        "--sec-ticker",
        help="SEC ticker override when the U.S. and Canadian listing symbols differ.",
    )
    parser.add_argument("--years", type=int, default=11, help="Annual fiscal years to retain (3-20).")
    parser.add_argument("--company-csv", type=Path)
    parser.add_argument("--periods-csv", type=Path)
    parser.add_argument("--documents-csv", type=Path)
    parser.add_argument("--facts-csv", type=Path)
    parser.add_argument("--shares-csv", type=Path)
    parser.add_argument(
        "--allow-internal",
        action="store_true",
        help="Allow provider_normalized_internal_only payloads for internal QA storage.",
    )
    return parser


def run_from_args(args: argparse.Namespace) -> int:
    if not _csv_requested(args):
        try:
            result = import_canada_sec_filings(
                args.symbol,
                sec_ticker=args.sec_ticker,
                years=args.years,
            )
        except CanadaSecAcquisitionError as exc:
            print(f"[CanadaIngest] {exc}", file=sys.stderr)
            print(
                "[CanadaIngest] No data was written. TSX-only issuers require a licensed "
                "SEDAR+ or verified issuer-document export; public SEDAR+ pages are not scraped.",
                file=sys.stderr,
            )
            return 2
        return _report_result(result, args.allow_internal, source="sec_edgar")

    bundle = CanadaVerifiedCsvBundle(
        company_csv=args.company_csv,
        periods_csv=args.periods_csv,
        documents_csv=args.documents_csv,
        facts_csv=args.facts_csv,
        shares_csv=args.shares_csv,
    )
    missing = _missing_bundle_files(bundle)
    if missing:
        print(
            "[CanadaIngest] input bundle is incomplete. This worker imports "
            "existing verified exports; it does not download SEDAR+ filings.",
            file=sys.stderr,
        )
        for label, path in missing:
            print(f"  missing {label}: {path}", file=sys.stderr)
        print(
            "See docs/track_b_canada.md for the required CSV schemas.",
            file=sys.stderr,
        )
        return 2

    result = import_canada_verified_csv_bundle(
        args.symbol,
        bundle,
        allow_internal=args.allow_internal,
    )
    return _report_result(result, args.allow_internal, source="verified_csv")


def _report_result(result, allow_internal: bool, *, source: str) -> int:
    if result.can_score and result.quality_report.confidence in PUBLIC_CONFIDENCE:
        status = "public_score_ready"
    elif result.can_score:
        status = "stored_internal_only"
    else:
        status = "stored_quality_failed"
    print(
        f"[CanadaIngest] {result.symbol} {status} "
        f"target=market_db source={source} "
        f"confidence={result.quality_report.confidence} "
        f"issues={len(result.quality_report.issues)}"
    )
    return 0 if result.can_score or allow_internal else 2


def _csv_requested(args: argparse.Namespace) -> bool:
    return any((
        args.company_csv,
        args.periods_csv,
        args.documents_csv,
        args.facts_csv,
        args.shares_csv,
    ))


def _missing_bundle_files(bundle: CanadaVerifiedCsvBundle) -> list[tuple[str, Path | None]]:
    files = (
        ("company CSV", bundle.company_csv),
        ("periods CSV", bundle.periods_csv),
        ("documents CSV", bundle.documents_csv),
        ("facts CSV", bundle.facts_csv),
        ("shares CSV", bundle.shares_csv),
    )
    return [(label, path) for label, path in files if path is None or not path.is_file()]


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    return run_from_args(parser.parse_args(argv))


if __name__ == "__main__":
    raise SystemExit(main())
