-- ISSUE_116: PostgreSQL authority for tenant-owned portfolios and simulations.
--
-- Rollout is additive. The release process creates the schema before an
-- explicit, checksummed legacy import. Runtime processes never apply DDL.
-- Rollback disables the PostgreSQL portfolio adapter in a non-production
-- emergency; imported rows are retained for deterministic reconciliation.

CREATE TABLE IF NOT EXISTS portfolios (
    portfolio_id UUID PRIMARY KEY,
    owner_id TEXT NOT NULL,
    name TEXT NOT NULL,
    version BIGINT NOT NULL DEFAULT 1 CHECK (version > 0),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deleted_at TIMESTAMPTZ,
    UNIQUE (owner_id, name),
    UNIQUE (portfolio_id, owner_id)
);

CREATE TABLE IF NOT EXISTS portfolio_holdings (
    portfolio_id UUID NOT NULL,
    owner_id TEXT NOT NULL,
    symbol TEXT NOT NULL,
    security_id UUID,
    shares NUMERIC(28, 10) NOT NULL CHECK (shares > 0),
    price_at_add NUMERIC(28, 10) NOT NULL CHECK (price_at_add >= 0),
    company_name TEXT NOT NULL DEFAULT '',
    added_date DATE NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (portfolio_id, symbol),
    FOREIGN KEY (portfolio_id, owner_id)
        REFERENCES portfolios(portfolio_id, owner_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS portfolio_transactions (
    transaction_id UUID PRIMARY KEY,
    portfolio_id UUID NOT NULL,
    owner_id TEXT NOT NULL,
    portfolio_version BIGINT NOT NULL,
    operation TEXT NOT NULL CHECK (operation IN ('create', 'add', 'update', 'remove', 'restore', 'delete')),
    symbol TEXT,
    shares NUMERIC(28, 10),
    price NUMERIC(28, 10),
    occurred_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    metadata_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    FOREIGN KEY (portfolio_id, owner_id)
        REFERENCES portfolios(portfolio_id, owner_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS portfolio_tombstones (
    portfolio_id UUID PRIMARY KEY,
    owner_id TEXT NOT NULL,
    name TEXT NOT NULL,
    version BIGINT NOT NULL,
    deleted_at TIMESTAMPTZ NOT NULL,
    metadata_json JSONB NOT NULL DEFAULT '{}'::jsonb
);

CREATE TABLE IF NOT EXISTS portfolio_simulation_results (
    simulation_id UUID PRIMARY KEY,
    portfolio_id UUID NOT NULL,
    owner_id TEXT NOT NULL,
    portfolio_version BIGINT NOT NULL,
    model_version TEXT NOT NULL,
    input_checksum TEXT NOT NULL,
    result_json JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    expires_at TIMESTAMPTZ NOT NULL,
    deleted_at TIMESTAMPTZ,
    UNIQUE (portfolio_id, portfolio_version, model_version, input_checksum),
    FOREIGN KEY (portfolio_id, owner_id)
        REFERENCES portfolios(portfolio_id, owner_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS portfolio_legacy_imports (
    owner_id TEXT NOT NULL,
    source_key TEXT NOT NULL,
    source_checksum TEXT NOT NULL,
    portfolio_id UUID,
    status TEXT NOT NULL CHECK (status IN ('processing', 'completed', 'failed', 'rolled_back')),
    error_code TEXT,
    started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at TIMESTAMPTZ,
    PRIMARY KEY (owner_id, source_key)
);

CREATE INDEX IF NOT EXISTS idx_portfolios_owner_updated
    ON portfolios (owner_id, updated_at, version);
CREATE INDEX IF NOT EXISTS idx_holdings_owner
    ON portfolio_holdings (owner_id, portfolio_id);
CREATE INDEX IF NOT EXISTS idx_transactions_owner_time
    ON portfolio_transactions (owner_id, occurred_at);
CREATE INDEX IF NOT EXISTS idx_tombstones_owner_time
    ON portfolio_tombstones (owner_id, deleted_at);
CREATE INDEX IF NOT EXISTS idx_simulations_owner_expiry
    ON portfolio_simulation_results (owner_id, expires_at)
    WHERE deleted_at IS NULL;
CREATE INDEX IF NOT EXISTS idx_legacy_imports_owner_status
    ON portfolio_legacy_imports (owner_id, status);

ALTER TABLE portfolios ENABLE ROW LEVEL SECURITY;
ALTER TABLE portfolios FORCE ROW LEVEL SECURITY;
ALTER TABLE portfolio_holdings ENABLE ROW LEVEL SECURITY;
ALTER TABLE portfolio_holdings FORCE ROW LEVEL SECURITY;
ALTER TABLE portfolio_transactions ENABLE ROW LEVEL SECURITY;
ALTER TABLE portfolio_transactions FORCE ROW LEVEL SECURITY;
ALTER TABLE portfolio_tombstones ENABLE ROW LEVEL SECURITY;
ALTER TABLE portfolio_tombstones FORCE ROW LEVEL SECURITY;
ALTER TABLE portfolio_simulation_results ENABLE ROW LEVEL SECURITY;
ALTER TABLE portfolio_simulation_results FORCE ROW LEVEL SECURITY;
ALTER TABLE portfolio_legacy_imports ENABLE ROW LEVEL SECURITY;
ALTER TABLE portfolio_legacy_imports FORCE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS portfolios_owner_isolation ON portfolios;
CREATE POLICY portfolios_owner_isolation ON portfolios
    USING (owner_id = current_setting('app.user_id', true))
    WITH CHECK (owner_id = current_setting('app.user_id', true));
DROP POLICY IF EXISTS holdings_owner_isolation ON portfolio_holdings;
CREATE POLICY holdings_owner_isolation ON portfolio_holdings
    USING (owner_id = current_setting('app.user_id', true))
    WITH CHECK (owner_id = current_setting('app.user_id', true));
DROP POLICY IF EXISTS transactions_owner_isolation ON portfolio_transactions;
CREATE POLICY transactions_owner_isolation ON portfolio_transactions
    USING (owner_id = current_setting('app.user_id', true))
    WITH CHECK (owner_id = current_setting('app.user_id', true));
DROP POLICY IF EXISTS tombstones_owner_isolation ON portfolio_tombstones;
CREATE POLICY tombstones_owner_isolation ON portfolio_tombstones
    USING (owner_id = current_setting('app.user_id', true))
    WITH CHECK (owner_id = current_setting('app.user_id', true));
DROP POLICY IF EXISTS simulations_owner_isolation ON portfolio_simulation_results;
CREATE POLICY simulations_owner_isolation ON portfolio_simulation_results
    USING (owner_id = current_setting('app.user_id', true))
    WITH CHECK (owner_id = current_setting('app.user_id', true));
DROP POLICY IF EXISTS legacy_imports_owner_isolation ON portfolio_legacy_imports;
CREATE POLICY legacy_imports_owner_isolation ON portfolio_legacy_imports
    USING (owner_id = current_setting('app.user_id', true))
    WITH CHECK (owner_id = current_setting('app.user_id', true));

REVOKE ALL ON portfolios, portfolio_holdings, portfolio_transactions,
    portfolio_tombstones, portfolio_simulation_results, portfolio_legacy_imports
    FROM PUBLIC;
