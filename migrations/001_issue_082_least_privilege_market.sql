-- ISSUE_082 market-object ownership and workload grants.
--
-- The web application and market workers both read and persist current market
-- and analysis artifacts, so each receives DML on the existing market schema.
-- They remain separate credentials so workers cannot reach the users database.
-- Read-only diagnostics receive market SELECT only. No rows or schemas change.

DO $issue_082_market_privileges$
DECLARE
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

    GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public
        TO cenvarn_app, cenvarn_market_worker;
    GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public
        TO cenvarn_app, cenvarn_market_worker;
    GRANT SELECT ON ALL TABLES IN SCHEMA public TO cenvarn_readonly;

    EXECUTE 'ALTER DEFAULT PRIVILEGES FOR ROLE cenvarn_migration IN SCHEMA public '
        'REVOKE ALL ON TABLES FROM PUBLIC';
    EXECUTE 'ALTER DEFAULT PRIVILEGES FOR ROLE cenvarn_migration IN SCHEMA public '
        'REVOKE ALL ON SEQUENCES FROM PUBLIC';
    EXECUTE 'ALTER DEFAULT PRIVILEGES FOR ROLE cenvarn_migration IN SCHEMA public '
        'REVOKE EXECUTE ON FUNCTIONS FROM PUBLIC';
    EXECUTE 'ALTER DEFAULT PRIVILEGES FOR ROLE cenvarn_migration IN SCHEMA public '
        'GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES '
        'TO cenvarn_app, cenvarn_market_worker';
    EXECUTE 'ALTER DEFAULT PRIVILEGES FOR ROLE cenvarn_migration IN SCHEMA public '
        'GRANT USAGE, SELECT ON SEQUENCES TO cenvarn_app, cenvarn_market_worker';
    EXECUTE 'ALTER DEFAULT PRIVILEGES FOR ROLE cenvarn_migration IN SCHEMA public '
        'GRANT SELECT ON TABLES TO cenvarn_readonly';
END
$issue_082_market_privileges$;
