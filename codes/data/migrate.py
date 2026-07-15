"""Idempotent release-phase database schema migration."""

from codes.data import db, temporal
from codes.services.analysis_snapshot_service import ensure_schema_if_configured


def main() -> None:
    db.init_db()
    temporal.ensure_schema()
    db.init_user_db()
    ensure_schema_if_configured()


if __name__ == "__main__":
    main()
