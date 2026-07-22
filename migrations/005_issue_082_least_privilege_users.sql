-- ISSUE_082 users-object privileges and service RLS access.
--
-- Canonical roles are provisioned before production migrations. Local
-- disposable databases may omit them; in that case this migration deliberately
-- leaves local ownership unchanged. Production startup separately verifies the
-- complete role catalog, so this compatibility branch cannot weaken production.
-- The migration changes only ownership, grants, and policies and does not
-- rewrite rows. Recovery is forward repair while runtime stays offline.

DO $issue_082_users_privileges$
DECLARE
    protected RECORD;
    relation RECORD;
BEGIN
    IF (
        SELECT COUNT(*) FROM pg_roles
        WHERE rolname IN (
            'cenvarn_app', 'cenvarn_service', 'cenvarn_migration',
            'cenvarn_market_worker', 'cenvarn_readonly'
        )
    ) <> 5 THEN
        RETURN;
    END IF;

    REVOKE ALL ON ALL TABLES IN SCHEMA public FROM PUBLIC;
    REVOKE ALL ON ALL SEQUENCES IN SCHEMA public FROM PUBLIC;
    REVOKE EXECUTE ON ALL FUNCTIONS IN SCHEMA public FROM PUBLIC;
    REVOKE ALL ON ALL TABLES IN SCHEMA public
        FROM cenvarn_app, cenvarn_service, cenvarn_market_worker, cenvarn_readonly;
    REVOKE ALL ON ALL SEQUENCES IN SCHEMA public
        FROM cenvarn_app, cenvarn_service, cenvarn_market_worker, cenvarn_readonly;

    FOR relation IN
        SELECT class.relkind, class.relname
        FROM pg_class AS class
        JOIN pg_namespace AS namespace ON namespace.oid = class.relnamespace
        WHERE namespace.nspname = 'public'
          AND class.relkind IN ('r', 'p', 'S', 'v', 'm')
        ORDER BY CASE WHEN class.relkind = 'S' THEN 2 ELSE 1 END
    LOOP
        EXECUTE format('ALTER %s %I OWNER TO cenvarn_migration',
            CASE
                WHEN relation.relkind = 'S' THEN 'SEQUENCE'
                WHEN relation.relkind = 'm' THEN 'MATERIALIZED VIEW'
                WHEN relation.relkind = 'v' THEN 'VIEW'
                ELSE 'TABLE'
            END,
            relation.relname
        );
    END LOOP;

    GRANT SELECT ON schema_migrations TO cenvarn_app, cenvarn_service, cenvarn_readonly;
    GRANT SELECT, INSERT, UPDATE, DELETE ON waitlist_signups TO cenvarn_service;
    GRANT USAGE, SELECT ON SEQUENCE subscriptions_id_seq TO cenvarn_app, cenvarn_service;

    FOR protected IN
        SELECT *
        FROM (VALUES
            ('user_weights'),
            ('subscriptions'),
            ('user_settings'),
            ('user_usage'),
            ('idempotency_records'),
            ('portfolios'),
            ('portfolio_holdings'),
            ('portfolio_transactions'),
            ('portfolio_tombstones'),
            ('portfolio_simulation_results'),
            ('portfolio_legacy_imports')
        ) AS registry(table_name)
    LOOP
        EXECUTE format(
            'GRANT SELECT, INSERT, UPDATE, DELETE ON %I TO cenvarn_app, cenvarn_service',
            protected.table_name
        );
        EXECUTE format(
            'DROP POLICY IF EXISTS %I ON %I',
            protected.table_name || '_service_access',
            protected.table_name
        );
        EXECUTE format(
            'CREATE POLICY %I ON %I FOR ALL TO cenvarn_service '
            'USING (true) WITH CHECK (true)',
            protected.table_name || '_service_access',
            protected.table_name
        );
    END LOOP;

    EXECUTE 'ALTER DEFAULT PRIVILEGES FOR ROLE cenvarn_migration IN SCHEMA public '
        'REVOKE ALL ON TABLES FROM PUBLIC';
    EXECUTE 'ALTER DEFAULT PRIVILEGES FOR ROLE cenvarn_migration IN SCHEMA public '
        'REVOKE ALL ON SEQUENCES FROM PUBLIC';
    EXECUTE 'ALTER DEFAULT PRIVILEGES FOR ROLE cenvarn_migration IN SCHEMA public '
        'REVOKE EXECUTE ON FUNCTIONS FROM PUBLIC';
END
$issue_082_users_privileges$;
