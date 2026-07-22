-- ISSUE_080 secures every present user-owned table at PostgreSQL's tenant
-- boundary. The users database is authoritative; normal application methods
-- write through the provider-neutral text owner supplied in
-- app.current_user_id. Stripe reconciliation, erasure, waitlist, and release
-- migrations use separately configured privileged connections.
--
-- This additive migration takes brief metadata locks while enabling RLS and
-- replacing policies. It does not rewrite table data. Rollback is forward-only:
-- keep runtime offline and repair a failed policy rather than disable RLS and
-- weaken tenant isolation.

DO $issue_080_rls$
DECLARE
    protected RECORD;
BEGIN
    FOR protected IN
        SELECT *
        FROM (VALUES
            ('user_weights', 'user_id'),
            ('subscriptions', 'user_id'),
            ('user_settings', 'user_id'),
            ('user_usage', 'user_id'),
            ('idempotency_records', 'user_id'),
            ('portfolios', 'owner_id'),
            ('portfolio_holdings', 'owner_id'),
            ('portfolio_transactions', 'owner_id'),
            ('portfolio_tombstones', 'owner_id'),
            ('portfolio_simulation_results', 'owner_id'),
            ('portfolio_legacy_imports', 'owner_id')
        ) AS registry(table_name, owner_column)
    LOOP
        EXECUTE format('ALTER TABLE %I ENABLE ROW LEVEL SECURITY', protected.table_name);
        EXECUTE format('ALTER TABLE %I FORCE ROW LEVEL SECURITY', protected.table_name);

        -- PostgreSQL has no CREATE POLICY IF NOT EXISTS. Inspecting the
        -- catalog before replacement keeps reruns deterministic and makes the
        -- canonical policy name the only accepted ownership contract.
        IF EXISTS (
            SELECT 1
            FROM pg_policies
            WHERE schemaname = 'public'
              AND tablename = protected.table_name
              AND policyname = protected.table_name || '_tenant_isolation'
        ) THEN
            EXECUTE format(
                'DROP POLICY %I ON %I',
                protected.table_name || '_tenant_isolation',
                protected.table_name
            );
        END IF;

        EXECUTE format(
            'CREATE POLICY %I ON %I FOR ALL '
            'USING (%I = NULLIF(current_setting(''app.current_user_id'', true), '''')) '
            'WITH CHECK (%I = NULLIF(current_setting(''app.current_user_id'', true), ''''))',
            protected.table_name || '_tenant_isolation',
            protected.table_name,
            protected.owner_column,
            protected.owner_column
        );
    END LOOP;
END
$issue_080_rls$;

-- Remove the ISSUE_116 compatibility policies after the canonical policies
-- exist. Dropping them first would create a transient policy gap if migration
-- execution were inspected inside the owning transaction.
DROP POLICY IF EXISTS portfolios_owner_isolation ON portfolios;
DROP POLICY IF EXISTS holdings_owner_isolation ON portfolio_holdings;
DROP POLICY IF EXISTS transactions_owner_isolation ON portfolio_transactions;
DROP POLICY IF EXISTS tombstones_owner_isolation ON portfolio_tombstones;
DROP POLICY IF EXISTS simulations_owner_isolation ON portfolio_simulation_results;
DROP POLICY IF EXISTS legacy_imports_owner_isolation ON portfolio_legacy_imports;

REVOKE ALL ON user_weights, subscriptions, user_settings, user_usage,
    idempotency_records, portfolios, portfolio_holdings, portfolio_transactions,
    portfolio_tombstones, portfolio_simulation_results, portfolio_legacy_imports
    FROM PUBLIC;
