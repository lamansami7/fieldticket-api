import os
import psycopg
from psycopg.rows import dict_row


def get_postgres_connection():
    database_url = os.environ.get("DATABASE_URL")

    if not database_url:
        raise RuntimeError(
            "DATABASE_URL is not configured. "
            "PostgreSQL connection unavailable."
        )

    return psycopg.connect(
        database_url,
        row_factory=dict_row,
        connect_timeout=10,
    )


def check_postgres_connection():
    with get_postgres_connection() as db:
        with db.cursor() as cursor:
            cursor.execute("SELECT 1 AS status")
            result = cursor.fetchone()

    return result["status"] == 1
