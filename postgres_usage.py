from datetime import datetime, timezone

from fastapi import HTTPException
from postgres_db import get_postgres_connection


def current_month():
    return datetime.now(timezone.utc).strftime("%Y-%m")


def get_postgres_usage(customer_id: int):
    month = current_month()

    with get_postgres_connection() as db:
        with db.cursor() as cursor:
            cursor.execute(
                """
                SELECT monthly_limit
                FROM customer_plans
                WHERE customer_id = %s
                """,
                (customer_id,),
            )
            plan = cursor.fetchone()
            limit = plan["monthly_limit"] if plan else 100

            cursor.execute(
                """
                SELECT requests
                FROM usage_monthly
                WHERE customer_id = %s AND month = %s
                """,
                (customer_id, month),
            )
            usage = cursor.fetchone()

    used = usage["requests"] if usage else 0

    return {
        "month": month,
        "monthly_limit": limit,
        "requests_used": used,
        "requests_remaining": max(0, limit - used),
    }


def charge_postgres_request(customer_id: int):
    month = current_month()

    with get_postgres_connection() as db:
        with db.cursor() as cursor:
            cursor.execute(
                """
                SELECT id
                FROM api_keys
                WHERE id = %s AND active = TRUE
                FOR UPDATE
                """,
                (customer_id,),
            )

            if cursor.fetchone() is None:
                raise HTTPException(401, "Customer not found")

            cursor.execute(
                """
                SELECT monthly_limit
                FROM customer_plans
                WHERE customer_id = %s
                """,
                (customer_id,),
            )
            plan = cursor.fetchone()
            limit = plan["monthly_limit"] if plan else 100

            cursor.execute(
                """
                SELECT requests
                FROM usage_monthly
                WHERE customer_id = %s AND month = %s
                """,
                (customer_id, month),
            )
            usage = cursor.fetchone()
            used = usage["requests"] if usage else 0

            if used >= limit:
                raise HTTPException(
                    status_code=429,
                    detail="Monthly API request limit reached",
                )

            cursor.execute(
                """
                INSERT INTO usage_monthly
                    (customer_id, month, requests)
                VALUES (%s, %s, 1)
                ON CONFLICT (customer_id, month)
                DO UPDATE SET requests =
                    usage_monthly.requests + 1
                """,
                (customer_id, month),
            )

    return {
        "used": used + 1,
        "limit": limit,
        "remaining": limit - used - 1,
    }
