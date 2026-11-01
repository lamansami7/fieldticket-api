import os
from fastapi import HTTPException
from postgres_db import get_postgres_connection

def charge_postgres_rate_limit(customer_id: int, *, limit: int | None = None, window_seconds: int = 60) -> dict:
    """Atomically enforce a customer-scoped fixed window across all API instances."""
    if limit is None:
        try:
            limit = int(os.environ.get("FIELD_TICKET_RATE_LIMIT_PER_MINUTE", "60"))
        except ValueError as exc:
            raise RuntimeError("FIELD_TICKET_RATE_LIMIT_PER_MINUTE must be an integer") from exc
    if not 1 <= limit <= 10000:
        raise RuntimeError("Rate limit must be between 1 and 10000")
    if not 1 <= window_seconds <= 3600:
        raise ValueError("window_seconds must be between 1 and 3600")
    with get_postgres_connection() as db:
        with db.cursor() as cursor:
            cursor.execute("""
                WITH bucket AS (
                    SELECT to_timestamp(floor(extract(epoch FROM clock_timestamp()) / %s) * %s) AS starts_at
                )
                INSERT INTO request_rate_limits (customer_id, window_start, request_count)
                SELECT %s, starts_at, 1 FROM bucket
                ON CONFLICT (customer_id) DO UPDATE
                   SET window_start = EXCLUDED.window_start,
                       request_count = CASE
                           WHEN request_rate_limits.window_start < EXCLUDED.window_start THEN 1
                           WHEN request_rate_limits.request_count < %s THEN request_rate_limits.request_count + 1
                           ELSE request_rate_limits.request_count
                       END
                RETURNING request_count
            """, (window_seconds, window_seconds, customer_id, limit))
            row = cursor.fetchone()
    count = row["request_count"]
    if count > limit:
        raise HTTPException(status_code=429, detail="Request rate limit exceeded. Please retry shortly.", headers={"Retry-After": str(window_seconds)})
    return {"requests_in_window": count, "limit": limit, "window_seconds": window_seconds}
