# FieldTicket production hardening

## Shared short-window throttling
The PostgreSQL API applies an atomic per-customer rate limit before the existing monthly quota. Default: 60 requests per fixed 60-second window. Configure \`FIELD_TICKET_RATE_LIMIT_PER_MINUTE\` on Render (valid range 1–10000). All instances share \`public.request_rate_limits\`; buckets are keyed by authenticated API-key customer ID, never caller-supplied identity or forwarded IP.

Apply \`migrations/20261031_security_hardening.sql\` before deploying. Existing request-size protection and monthly quota remain.

## Least-privilege database credentials
The migration creates \`fieldticket_runtime\` as a NOLOGIN, non-superuser, non-owner role with only required table permissions.
1. Run the migration as Neon database owner.
2. In Neon, create a separate LOGIN role for the web service, e.g. \`fieldticket_app_login\`, with a generated password.
3. Grant membership: \`GRANT fieldticket_runtime TO fieldticket_app_login;\`
4. Set Render \`DATABASE_URL\` to that login role's connection string.
5. Set \`FIELD_TICKET_ADMIN_DATABASE_URL\` only in a trusted operator environment. It is used by \`manage_customers.py\` and schema setup, never web requests.

Do not put the owner/admin URL in Render's \`DATABASE_URL\`. Do not commit connection strings. Rotate any runtime credential that previously had owner privileges.

## Real PostgreSQL concurrency tests
Integration tests open independent PostgreSQL connections concurrently. They are skipped unless \`FIELD_TICKET_TEST_DATABASE_URL\` points to a disposable PostgreSQL database with the migration applied.
\`\`\`bash
python -m pytest -q
FIELD_TICKET_TEST_DATABASE_URL='postgresql://...' python -m pytest -q tests/test_postgres_concurrency.py
\`\`\`
Never point these tests at production; they create and delete temporary rate-limit rows.
