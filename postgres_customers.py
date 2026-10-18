import hashlib
import secrets
from datetime import datetime, timezone

from postgres_db import get_postgres_connection


def create_postgres_key(customer_name: str):
    if not customer_name.strip():
        raise ValueError("Customer name is required")

    raw_key = "ft_live_" + secrets.token_urlsafe(32)
    key_hash = hashlib.sha256(raw_key.encode()).hexdigest()

    with get_postgres_connection() as db:
        with db.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO api_keys
                    (customer_name, key_hash, created_at)
                VALUES (%s, %s, %s)
                RETURNING id
                """,
                (
                    customer_name.strip(),
                    key_hash,
                    datetime.now(timezone.utc),
                ),
            )
            customer_id = cursor.fetchone()["id"]

    return {
        "customer_id": customer_id,
        "api_key": raw_key,
    }


def authenticate_postgres_key(raw_key: str):
    if not raw_key:
        return None

    key_hash = hashlib.sha256(raw_key.encode()).hexdigest()

    with get_postgres_connection() as db:
        with db.cursor() as cursor:
            cursor.execute(
                """
                SELECT id, customer_name
                FROM api_keys
                WHERE key_hash = %s AND active = TRUE
                """,
                (key_hash,),
            )
            customer = cursor.fetchone()

    if customer is None:
        return None

    return {
        "customer_id": customer["id"],
        "customer_name": customer["customer_name"],
    }
