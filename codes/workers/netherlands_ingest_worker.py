"""Import a verified Netherlands CSV bundle into the market database."""
from __future__ import annotations
import argparse, os, sys
from pathlib import Path
from dotenv import load_dotenv
load_dotenv();sys.path.insert(0,os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from codes.data.providers.netherlands_ingestion import NetherlandsVerifiedCsvBundle,import_netherlands_verified_csv_bundle
from codes.data.providers.netherlands_normalization import PUBLIC_CONFIDENCE
def build_parser():
    p=argparse.ArgumentParser(description="Import source-verified Netherlands financials.");p.add_argument("--symbol",required=True,help="Netherlands symbol, e.g. ASML.AS");p.add_argument("--bundle-dir",type=Path)
    for x in ("company","periods","documents","facts","shares"):p.add_argument(f"--{x}-csv",type=Path)
    p.add_argument("--allow-internal",action="store_true");return p
def run_from_args(args):
    b=NetherlandsVerifiedCsvBundle(*(_path(args,f"{x}_csv",f"{x}.csv") for x in ("company","periods","documents","facts","shares")));missing=[(x,p) for x,p in zip(("company CSV","periods CSV","documents CSV","facts CSV","shares CSV"),b.__dict__.values()) if p is None or not p.is_file()]
    if missing:
        print("[NetherlandsIngest] input bundle is incomplete; no source facts were written.",file=sys.stderr)
        for n,p in missing:print(f"  missing {n}: {p}",file=sys.stderr)
        print("See docs/track_b_netherlands.md for the required CSV schemas.",file=sys.stderr);return 2
    try:r=import_netherlands_verified_csv_bundle(args.symbol,b,allow_internal=args.allow_internal)
    except (FileNotFoundError,ValueError) as e:print(f"[NetherlandsIngest] validation failed: {e}",file=sys.stderr);return 2
    status="public_score_ready" if r.can_score and r.quality_report.confidence in PUBLIC_CONFIDENCE else "stored_internal_only" if r.can_score else "stored_quality_failed";print(f"[NetherlandsIngest] {r.symbol} {status} target=market_db source=verified_csv confidence={r.quality_report.confidence} issues={len(r.quality_report.issues)}");return 0 if r.can_score or args.allow_internal else 2
def _path(args,key,name): return getattr(args,key) or (args.bundle_dir/name if args.bundle_dir else None)
def main(argv=None):return run_from_args(build_parser().parse_args(argv))
if __name__=="__main__":raise SystemExit(main())
