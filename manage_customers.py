import argparse
import os
import subprocess
import sys

from postgres_customers import create_postgres_key
from postgres_db import get_postgres_connection
from postgres_usage import get_postgres_usage


def connect():
    if os.getenv("DATABASE_URL"):
        return

    result = subprocess.run(
        [
            "neonctl", "connection-string", "production",
            "--project-id", "young-glitter-67961256",
            "--database-name", "neondb",
            "--role-name", "neondb_owner",
            "--ssl", "require",
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    os.environ["DATABASE_URL"] = result.stdout.strip()


def list_customers():
    with get_postgres_connection() as db:
        with db.cursor() as cursor:
            cursor.execute("""
                SELECT a.id, a.customer_name, a.active,
                       COALESCE(p.monthly_limit, 100)
                FROM api_keys a
                LEFT JOIN customer_plans p
                    ON p.customer_id = a.id
                ORDER BY a.id
            """)
            rows = cursor.fetchall()

    for row in rows:
        print(
            f"ID: {row['id']} | "
            f"Name: {row['customer_name']} | "
            f"Active: {row['active']} | "
            f"Monthly limit: {row['coalesce']}"
        )


def create_customer(name, limit):
    if limit < 0:
        raise ValueError("Monthly limit cannot be negative.")

    customer = create_postgres_key(name)

    with get_postgres_connection() as db:
        with db.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO customer_plans
                    (customer_id, monthly_limit)
                VALUES (%s, %s)
                """,
                (customer["customer_id"], limit),
            )

    print("Customer created!")
    print("Customer ID:", customer["customer_id"])
    import json
    from pathlib import Path

    key_dir = Path.home() / ".fieldticket-keys"
    key_dir.mkdir(mode=0o700, exist_ok=True)
    key_dir.chmod(0o700)

    key_file = key_dir / f"customer-{customer['customer_id']}.json"

    fd = os.open(
        str(key_file),
        os.O_WRONLY | os.O_CREAT | os.O_EXCL,
        0o600,
    )

    with os.fdopen(fd, "w") as file:
        json.dump({
            "customer_id": customer["customer_id"],
            "customer": name,
            "api_key": customer["api_key"],
        }, file, indent=2)

    print("API key saved privately to:", key_file)
    print("Never share this file or commit it to GitHub.")


def show_usage(customer_id):
    usage = get_postgres_usage(customer_id)
    print(usage)


def disable_customer(customer_id):
    with get_postgres_connection() as db:
        with db.cursor() as cursor:
            cursor.execute(
                "UPDATE api_keys SET active = FALSE WHERE id = %s",
                (customer_id,),
            )
            if cursor.rowcount == 0:
                raise ValueError("Customer ID not found.")

    print(f"Customer {customer_id} disabled.")


def main():
    parser = argparse.ArgumentParser()
    commands = parser.add_subparsers(
        dest="command", required=True
    )

    commands.add_parser("list")

    create = commands.add_parser("create")
    create.add_argument("name")
    create.add_argument("--limit", type=int, default=100)

    usage = commands.add_parser("usage")
    usage.add_argument("customer_id", type=int)

    disable = commands.add_parser("disable")
    disable.add_argument("customer_id", type=int)

    args = parser.parse_args()
    connect()

    if args.command == "list":
        list_customers()
    elif args.command == "create":
        create_customer(args.name, args.limit)
    elif args.command == "usage":
        show_usage(args.customer_id)
    elif args.command == "disable":
        disable_customer(args.customer_id)


if __name__ == "__main__":
    main()
