-- ISSUE_082 analytics ownership and workload grants.
-- Product telemetry and custom analysis snapshots remain writable by the web
-- application. Read-only support receives migration metadata only because
-- analytics rows may contain user identifiers and are not yet masked.

DO $issue_082_analytics_privileges$
DECLARE
    analytics_table TEXT;
    analytics_sequence TEXT;
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

    -- Analytics may intentionally share the market database outside production.
    -- Restrict ownership and revocation to analytics-owned objects so this
    -- migration cannot remove market-worker or market read-only grants.
    FOREACH analytics_table IN ARRAY ARRAY[
        'analytics_events',
        'analysis_versions',
        'analysis_snapshots',
        'custom_analysis_snapshots'
    ]
    LOOP
        EXECUTE format('ALTER TABLE %I OWNER TO cenvarn_migration', analytics_table);
        EXECUTE format('REVOKE ALL ON %I FROM PUBLIC', analytics_table);
        EXECUTE format(
            'REVOKE ALL ON %I FROM cenvarn_service, cenvarn_market_worker, cenvarn_readonly',
            analytics_table
        );
        EXECUTE format(
            'GRANT SELECT, INSERT, UPDATE, DELETE ON %I TO cenvarn_app',
            analytics_table
        );
    END LOOP;

    FOREACH analytics_sequence IN ARRAY ARRAY[
        'analytics_events_id_seq',
        'analysis_snapshots_id_seq'
    ]
    LOOP
        EXECUTE format('ALTER SEQUENCE %I OWNER TO cenvarn_migration', analytics_sequence);
        EXECUTE format('REVOKE ALL ON SEQUENCE %I FROM PUBLIC', analytics_sequence);
        EXECUTE format(
            'REVOKE ALL ON SEQUENCE %I '
            'FROM cenvarn_service, cenvarn_market_worker, cenvarn_readonly',
            analytics_sequence
        );
        EXECUTE format(
            'GRANT USAGE, SELECT ON SEQUENCE %I TO cenvarn_app',
            analytics_sequence
        );
    END LOOP;

    GRANT SELECT ON schema_migrations TO cenvarn_readonly;

    EXECUTE 'ALTER DEFAULT PRIVILEGES FOR ROLE cenvarn_migration IN SCHEMA public '
        'REVOKE ALL ON TABLES FROM PUBLIC';
    EXECUTE 'ALTER DEFAULT PRIVILEGES FOR ROLE cenvarn_migration IN SCHEMA public '
        'REVOKE ALL ON SEQUENCES FROM PUBLIC';
    EXECUTE 'ALTER DEFAULT PRIVILEGES FOR ROLE cenvarn_migration IN SCHEMA public '
        'REVOKE EXECUTE ON FUNCTIONS FROM PUBLIC';
    EXECUTE 'ALTER DEFAULT PRIVILEGES FOR ROLE cenvarn_migration IN SCHEMA public '
        'GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO cenvarn_app';
    EXECUTE 'ALTER DEFAULT PRIVILEGES FOR ROLE cenvarn_migration IN SCHEMA public '
        'GRANT USAGE, SELECT ON SEQUENCES TO cenvarn_app';
END
$issue_082_analytics_privileges$;
