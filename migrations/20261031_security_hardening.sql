-- Run once as the Neon database owner after the base application tables exist.
CREATE TABLE IF NOT EXISTS public.request_rate_limits (
    customer_id BIGINT PRIMARY KEY,
    window_start TIMESTAMPTZ NOT NULL,
    request_count INTEGER NOT NULL CHECK (request_count >= 0)
);
CREATE INDEX IF NOT EXISTS request_rate_limits_window_idx
    ON public.request_rate_limits(window_start);

-- Dedicated non-login privilege bundle for the web service.
CREATE ROLE fieldticket_runtime NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS;
GRANT CONNECT ON DATABASE neondb TO fieldticket_runtime;
GRANT USAGE ON SCHEMA public TO fieldticket_runtime;
REVOKE CREATE ON SCHEMA public FROM fieldticket_runtime;

GRANT SELECT ON TABLE public.api_keys TO fieldticket_runtime;
GRANT SELECT ON TABLE public.customer_plans TO fieldticket_runtime;
GRANT SELECT, INSERT, UPDATE ON TABLE public.usage_monthly TO fieldticket_runtime;
GRANT SELECT, INSERT, UPDATE ON TABLE public.request_rate_limits TO fieldticket_runtime;
