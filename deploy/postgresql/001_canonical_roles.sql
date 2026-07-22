-- ISSUE_082 cluster role bootstrap.
--
-- An administrator runs this idempotent script once per PostgreSQL cluster
-- before database-specific access scripts and release migrations. Canonical
-- roles are NOLOGIN authorization groups; environment-specific blue/green
-- LOGIN principals receive exactly one membership and keep passwords outside
-- SQL, source control, process output, and shell history.

DO $issue_082_roles$
DECLARE
    role_name TEXT;
BEGIN
    FOREACH role_name IN ARRAY ARRAY[
        'cenvarn_app',
        'cenvarn_service',
        'cenvarn_migration',
        'cenvarn_market_worker',
        'cenvarn_readonly'
    ]
    LOOP
        IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = role_name) THEN
            EXECUTE format('CREATE ROLE %I', role_name);
        END IF;
        EXECUTE format(
            'ALTER ROLE %I NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE '
            'NOREPLICATION NOBYPASSRLS',
            role_name
        );
    END LOOP;
END
$issue_082_roles$;

-- Prevent accidental privilege inheritance between canonical workloads.
REVOKE cenvarn_service, cenvarn_migration, cenvarn_market_worker, cenvarn_readonly
    FROM cenvarn_app;
REVOKE cenvarn_app, cenvarn_migration, cenvarn_market_worker, cenvarn_readonly
    FROM cenvarn_service;
REVOKE cenvarn_app, cenvarn_service, cenvarn_market_worker, cenvarn_readonly
    FROM cenvarn_migration;
REVOKE cenvarn_app, cenvarn_service, cenvarn_migration, cenvarn_readonly
    FROM cenvarn_market_worker;
REVOKE cenvarn_app, cenvarn_service, cenvarn_migration, cenvarn_market_worker
    FROM cenvarn_readonly;
