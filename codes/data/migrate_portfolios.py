"""Explicit release command for checksummed legacy portfolio imports."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path


def _user_ids(values: list[str], source_file: Path | None) -> list[str]:
    users = [value.strip() for value in values if value.strip()]
    if source_file:
        users.extend(
            line.strip()
            for line in source_file.read_text(encoding="utf-8").splitlines()
            if line.strip() and not line.lstrip().startswith("#")
        )
    return list(dict.fromkeys(users))


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Import encrypted legacy portfolio files into PostgreSQL"
    )
    parser.add_argument("user_ids", nargs="*", help="Authenticated owner ids to import")
    parser.add_argument("--user-file", type=Path, help="One authenticated owner id per line")
    parser.add_argument(
        "--keep-files",
        action="store_true",
        help="Verify imports but retain encrypted legacy files for a later approved purge",
    )
    args = parser.parse_args()
    users = _user_ids(args.user_ids, args.user_file)
    if not users:
        parser.error("provide at least one user id or --user-file")

    migration_url = os.environ.get("DATABASE_MIGRATION_USERS_URL")
    if migration_url:
        os.environ["DATABASE_USERS_URL"] = migration_url
    os.environ["PORTFOLIO_STORAGE_BACKEND"] = "postgres"

    # Import after environment selection so the repository binds only to the
    # dedicated release credential, never a web-worker connection pool.
    from codes.portfolio import migrate_legacy_user

    results = [migrate_legacy_user(user_id, purge_files=not args.keep_files) for user_id in users]
    print(json.dumps({"users": results}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
