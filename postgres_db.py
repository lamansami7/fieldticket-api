import os
import psycopg
from psycopg.rows import dict_row

def get_postgres_connection(*, admin: bool = False):
    """Separate web-runtime credentials from operator credentials."""
    variable = "FIELD_TICKET_ADMIN_DATABASE_URL" if admin else "DATABASE_URL"
    database_url = os.environ.get(variable)
    if not database_url:
        raise RuntimeError(f"{variable} is not configured. PostgreSQL connection unavailable.")
    return psycopg.connect(database_url, row_factory=dict_row, connect_timeout=10)

def check_postgres_connection():
    with get_postgres_connection() as db:
        with db.cursor() as cursor:
            cursor.execute("SELECT 1 AS status")
            result = cursor.fetchone()
    return result["status"] == 1
