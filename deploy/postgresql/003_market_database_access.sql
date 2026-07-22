-- ISSUE_082 market-database connection and schema ownership boundary.
-- Run as the database owner while connected to the market database, after the
-- canonical cluster roles exist and before the release migration command.

DO $issue_082_market_database$
DECLARE
    relation RECORD;
BEGIN
    EXECUTE format('REVOKE CONNECT, TEMPORARY ON DATABASE %I FROM PUBLIC', current_database());
    EXECUTE format(
        'GRANT CONNECT ON DATABASE %I TO cenvarn_app, cenvarn_migration, '
        'cenvarn_market_worker, cenvarn_readonly',
        current_database()
    );
    EXECUTE format(
        'REVOKE CONNECT ON DATABASE %I FROM cenvarn_service',
        current_database()
    );
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
END
$issue_082_market_database$;

REVOKE ALL ON SCHEMA public FROM PUBLIC;
ALTER SCHEMA public OWNER TO cenvarn_migration;
GRANT USAGE ON SCHEMA public TO cenvarn_app, cenvarn_market_worker, cenvarn_readonly;
GRANT ALL ON SCHEMA public TO cenvarn_migration;
