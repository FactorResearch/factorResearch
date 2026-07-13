"""Standalone UK verified-source ingestion worker.

The worker imports source-verified exports produced from Companies House, FCA
NSM, issuer annual reports, or a licensed source. It deliberately performs no
web scraping and should not be imported by the Dash app process.

Usage:
    python -m codes.workers.uk_ingest_worker --symbol VOD.L --bundle-dir ./vod

    python -m codes.workers.uk_ingest_worker --symbol VOD.L \
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

from codes.data.providers.uk_ingestion import (  # noqa: E402
    UKVerifiedCsvBundle,
    import_uk_verified_csv_bundle,
)
from codes.data.providers.uk_normalization import PUBLIC_CONFIDENCE  # noqa: E402


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Import source-verified UK financials.")
    parser.add_argument("--symbol", required=True, help="UK symbol, e.g. VOD.L or VOD:LSE")
    parser.add_argument(
        "--bundle-dir",
        type=Path,
        help="Directory containing company.csv, periods.csv, documents.csv, facts.csv, and shares.csv.",
    )
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
    bundle = UKVerifiedCsvBundle(
        company_csv=_bundle_path(args, "company_csv", "company.csv"),
        periods_csv=_bundle_path(args, "periods_csv", "periods.csv"),
        documents_csv=_bundle_path(args, "documents_csv", "documents.csv"),
        facts_csv=_bundle_path(args, "facts_csv", "facts.csv"),
        shares_csv=_bundle_path(args, "shares_csv", "shares.csv"),
    )
    missing = _missing_bundle_files(bundle)
    if missing:
        print(
            "[UKIngest] input bundle is incomplete. This worker imports "
            "verified Companies House/FCA/issuer/licensed exports; it does not scrape source sites.",
            file=sys.stderr,
        )
        for label, path in missing:
            print(f"  missing {label}: {path}", file=sys.stderr)
        print(
            "See docs/track_b_uk.md for the required CSV schemas.",
            file=sys.stderr,
        )
        return 2

    try:
        result = import_uk_verified_csv_bundle(
            args.symbol,
            bundle,
            allow_internal=args.allow_internal,
        )
    except (FileNotFoundError, ValueError) as exc:
        print(f"[UKIngest] validation failed: {exc}", file=sys.stderr)
        print("[UKIngest] No source facts were written.", file=sys.stderr)
        return 2
    return _report_result(result, args.allow_internal, source="verified_csv")


def _report_result(result, allow_internal: bool, *, source: str) -> int:
    if result.can_score and result.quality_report.confidence in PUBLIC_CONFIDENCE:
        status = "public_score_ready"
    elif result.can_score:
        status = "stored_internal_only"
    else:
        status = "stored_quality_failed"
    print(
        f"[UKIngest] {result.symbol} {status} "
        f"target=market_db source={source} "
        f"confidence={result.quality_report.confidence} "
        f"issues={len(result.quality_report.issues)}"
    )
    return 0 if result.can_score or allow_internal else 2


def _bundle_path(args: argparse.Namespace, attribute: str, filename: str) -> Path | None:
    explicit = getattr(args, attribute)
    if explicit is not None:
        return explicit
    return args.bundle_dir / filename if args.bundle_dir is not None else None


def _missing_bundle_files(bundle: UKVerifiedCsvBundle) -> list[tuple[str, Path | None]]:
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
