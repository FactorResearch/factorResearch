"""Standalone Canada verified-source ingestion worker.

This worker imports structured exports from a verified Canada extraction
process into the market database. It does not scrape SEDAR+ and should not be
imported by the Dash app process.

Usage:
    python -m codes.workers.canada_ingest_worker \
        --symbol SHOP.TO \
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


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Import verified Canada source exports.")
    parser.add_argument("--symbol", required=True, help="Canadian symbol, e.g. SHOP.TO or SHOP:TSX")
    parser.add_argument("--company-csv", required=True, type=Path)
    parser.add_argument("--periods-csv", required=True, type=Path)
    parser.add_argument("--documents-csv", required=True, type=Path)
    parser.add_argument("--facts-csv", required=True, type=Path)
    parser.add_argument("--shares-csv", required=True, type=Path)
    parser.add_argument(
        "--allow-internal",
        action="store_true",
        help="Allow provider_normalized_internal_only payloads for internal QA storage.",
    )
    return parser


def run_from_args(args: argparse.Namespace) -> int:
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
    if result.can_score and result.quality_report.confidence in PUBLIC_CONFIDENCE:
        status = "public_score_ready"
    elif result.can_score:
        status = "stored_internal_only"
    else:
        status = "stored_quality_failed"
    print(
        f"[CanadaIngest] {result.symbol} {status} "
        "target=market_db "
        f"confidence={result.quality_report.confidence} "
        f"issues={len(result.quality_report.issues)}"
    )
    return 0 if result.can_score or args.allow_internal else 2


def _missing_bundle_files(bundle: CanadaVerifiedCsvBundle) -> list[tuple[str, Path]]:
    files = (
        ("company CSV", bundle.company_csv),
        ("periods CSV", bundle.periods_csv),
        ("documents CSV", bundle.documents_csv),
        ("facts CSV", bundle.facts_csv),
        ("shares CSV", bundle.shares_csv),
    )
    return [(label, path) for label, path in files if not path.is_file()]


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    return run_from_args(parser.parse_args(argv))


if __name__ == "__main__":
    raise SystemExit(main())
