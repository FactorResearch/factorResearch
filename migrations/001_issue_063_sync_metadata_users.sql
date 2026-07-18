-- ISSUE_063: synchronization metadata for user-owned PostgreSQL records.
--
-- Rollout: additive columns with compatibility defaults, followed by a
-- backfill from existing timestamps/settings.  The application continues to
-- read the legacy JSON settings shape during rollout.
-- Rollback: restore the previous application version; the additive columns are
-- intentionally retained until a later expand-and-contract release.

ALTER TABLE user_weights
    ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS version BIGINT NOT NULL DEFAULT 1,
    ADD COLUMN IF NOT EXISTS deleted_at TIMESTAMPTZ;

UPDATE user_weights
SET created_at = COALESCE(created_at, updated_at::timestamptz)
WHERE created_at IS NULL;

ALTER TABLE user_weights
    ALTER COLUMN created_at SET DEFAULT NOW();

ALTER TABLE subscriptions
    ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS version BIGINT NOT NULL DEFAULT 1,
    ADD COLUMN IF NOT EXISTS deleted_at TIMESTAMPTZ;

UPDATE subscriptions
SET created_at = COALESCE(created_at, start_date, updated_at)
WHERE created_at IS NULL;

ALTER TABLE subscriptions
    ALTER COLUMN created_at SET DEFAULT NOW();

ALTER TABLE user_settings
    ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS version BIGINT NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS deleted_at TIMESTAMPTZ;

UPDATE user_settings
SET created_at = COALESCE(created_at, updated_at),
    version = GREATEST(
        version,
        CASE
            WHEN settings_json #>> '{_sync,version}' ~ '^[0-9]+$'
                THEN (settings_json #>> '{_sync,version}')::BIGINT
            ELSE 0
        END
    )
WHERE created_at IS NULL OR version = 0;

ALTER TABLE user_settings
    ALTER COLUMN created_at SET DEFAULT NOW();

CREATE INDEX IF NOT EXISTS idx_user_weights_sync
    ON user_weights (user_id, updated_at, version);
CREATE INDEX IF NOT EXISTS idx_subscriptions_sync
    ON subscriptions (user_id, updated_at, version);
CREATE INDEX IF NOT EXISTS idx_user_settings_sync
    ON user_settings (user_id, updated_at, version);
