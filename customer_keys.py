import hashlib
import secrets
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

DB_PATH = Path(__file__).parent / "fieldticket.db"


def connect():
    db = sqlite3.connect(DB_PATH)
    db.execute("""
        CREATE TABLE IF NOT EXISTS api_keys (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            customer_name TEXT NOT NULL,
            key_hash TEXT NOT NULL UNIQUE,
            created_at TEXT NOT NULL,
            active INTEGER NOT NULL DEFAULT 1
        )
    """)
    db.commit()
    return db


def create_key(customer_name):
    raw_key = "ft_live_" + secrets.token_urlsafe(32)
    key_hash = hashlib.sha256(raw_key.encode()).hexdigest()

    with connect() as db:
        db.execute(
            """INSERT INTO api_keys
            (customer_name, key_hash, created_at)
            VALUES (?, ?, ?)""",
            (
                customer_name,
                key_hash,
                datetime.now(timezone.utc).isoformat()
            )
        )

    print("\nCustomer:", customer_name)
    print("API KEY:", raw_key)
    print("\nSave this key securely.")
    print("It will not be displayed again.")


if __name__ == "__main__":
    if len(sys.argv) != 2 or not sys.argv[1].strip():
        print('Usage: python customer_keys.py "Customer Name"')
        sys.exit(1)

    create_key(sys.argv[1].strip())
