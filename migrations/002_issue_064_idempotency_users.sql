-- ISSUE_064: durable command claims and replayable outcomes.
-- Rollout: additive table before enabling idempotent writes. Rollback: stop
-- sending idempotency keys, retain records for incident/replay investigation.
CREATE TABLE IF NOT EXISTS idempotency_records (
    user_id         TEXT NOT NULL,
    idempotency_key TEXT NOT NULL,
    operation       TEXT NOT NULL,
    request_hash    TEXT NOT NULL,
    status          TEXT NOT NULL CHECK (status IN ('processing', 'completed', 'failed')),
    response_json   JSONB,
    response_status INTEGER,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    expires_at      TIMESTAMPTZ NOT NULL,
    PRIMARY KEY (user_id, idempotency_key)
);
CREATE INDEX IF NOT EXISTS idx_idempotency_expiry ON idempotency_records (expires_at);
