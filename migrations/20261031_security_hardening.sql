-- Run as Neon database owner after base application tables exist.
CREATE TABLE IF NOT EXISTS public.request_rate_limits (
    customer_id BIGINT PRIMARY KEY, window_start TIMESTAMPTZ NOT NULL,
    request_count INTEGER NOT NULL CHECK (request_count >= 0)
);
CREATE INDEX IF NOT EXISTS request_rate_limits_window_idx ON public.request_rate_limits(window_start);
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'fieldticket_runtime') THEN
        CREATE ROLE fieldticket_runtime NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS;
    END IF;
    EXECUTE format('GRANT CONNECT ON DATABASE %I TO fieldticket_runtime', current_database());
END $$;
GRANT USAGE ON SCHEMA public TO fieldticket_runtime;
REVOKE CREATE ON SCHEMA public FROM fieldticket_runtime;
GRANT SELECT ON TABLE public.api_keys TO fieldticket_runtime;
GRANT SELECT ON TABLE public.customer_plans TO fieldticket_runtime;
GRANT SELECT, INSERT, UPDATE ON TABLE public.usage_monthly TO fieldticket_runtime;
GRANT SELECT, INSERT, UPDATE ON TABLE public.request_rate_limits TO fieldticket_runtime;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO fieldticket_runtime;
