from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_backup_streams_encrypted_archives_atomically():
    script = (ROOT / "scripts" / "backup_db.sh").read_text()
    assert "pg_dump" in script and "| openssl enc" in script
    assert "-pass env:BACKUP_ENCRYPTION_KEY" in script
    assert ".pending" in script and 'mv "$pending_file" "$enc_file"' in script
    assert "DATABASE_USERS_URL DATABASE_MARKET_URL" in script
    assert "trap 'rm -f" in script
    assert "raw_file" not in script
    assert script.count("factorresearch_") >= 3


def test_restore_never_writes_plaintext_dump_and_cleans_failures():
    script = (ROOT / "scripts" / "restore_test.sh").read_text()
    assert "openssl enc -d" in script and "| pg_restore" in script
    assert "--exit-on-error" in script
    assert "mktemp" not in script and "tmp_dump" not in script
    assert script.count("dropdb") >= 2
