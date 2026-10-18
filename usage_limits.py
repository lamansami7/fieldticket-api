import sqlite3
from datetime import datetime, timezone

from fastapi import HTTPException
from customer_keys import connect


def initialize_usage():
    with connect() as db:
        db.execute("""
            CREATE TABLE IF NOT EXISTS usage_monthly (
                customer_id INTEGER NOT NULL,
                month TEXT NOT NULL,
                requests INTEGER NOT NULL DEFAULT 0,
                PRIMARY KEY (customer_id, month)
            )
        """)
        db.execute("""
            CREATE TABLE IF NOT EXISTS customer_plans (
                customer_id INTEGER PRIMARY KEY,
                monthly_limit INTEGER NOT NULL DEFAULT 100
                    CHECK (monthly_limit >= 0)
            )
        """)
        db.commit()


def charge_request(customer_id: int):
    month = datetime.now(timezone.utc).strftime("%Y-%m")

    with connect() as db:
        db.execute("BEGIN IMMEDIATE")

        row = db.execute(
            """
            SELECT monthly_limit
            FROM customer_plans
            WHERE customer_id = ?
            """,
            (customer_id,)
        ).fetchone()

        limit = row[0] if row else 100

        usage = db.execute(
            """
            SELECT requests
            FROM usage_monthly
            WHERE customer_id = ? AND month = ?
            """,
            (customer_id, month)
        ).fetchone()

        used = usage[0] if usage else 0

        if used >= limit:
            raise HTTPException(
                status_code=429,
                detail="Monthly API request limit reached"
            )

        db.execute(
            """
            INSERT INTO usage_monthly
                (customer_id, month, requests)
            VALUES (?, ?, 1)
            ON CONFLICT(customer_id, month)
            DO UPDATE SET requests = requests + 1
            """,
            (customer_id, month)
        )
        db.commit()

        return {
            "used": used + 1,
            "limit": limit,
            "remaining": limit - used - 1,
        }
