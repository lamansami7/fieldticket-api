import argparse
import json
import os
import subprocess
from pathlib import Path

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
                           AS monthly_limit
                FROM api_keys a
                LEFT JOIN customer_plans p
                    ON p.customer_id = a.id
                ORDER BY a.id
            """)
            rows = cursor.fetchall()

    if not rows:
        print("No customers found.")

    for row in rows:
        print(
            f"ID: {row['id']} | "
            f"Name: {row['customer_name']} | "
            f"Active: {row['active']} | "
            f"Monthly limit: {row['monthly_limit']}"
        )


def create_customer(name, limit):
    name = name.strip()

    if not name:
        raise ValueError("Customer name cannot be empty.")

    if limit < 0:
        raise ValueError("Monthly limit cannot be negative.")

    key_dir = Path.home() / ".fieldticket-keys"
    key_dir.mkdir(mode=0o700, exist_ok=True)
    key_dir.chmod(0o700)

    customer = create_postgres_key(name)
    customer_id = customer["customer_id"]
    key_file = key_dir / f"customer-{customer_id}.json"

    try:
        fd = os.open(
            str(key_file),
            os.O_WRONLY | os.O_CREAT | os.O_EXCL,
            0o600,
        )

        with os.fdopen(fd, "w") as file:
            json.dump({
                "customer_id": customer_id,
                "customer": name,
                "api_key": customer["api_key"],
            }, file, indent=2)
            file.flush()
            os.fsync(file.fileno())

        with get_postgres_connection() as db:
            with db.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO customer_plans
                        (customer_id, monthly_limit)
                    VALUES (%s, %s)
                    """,
                    (customer_id, limit),
                )

    except Exception:
        # Never leave a newly created key active after
        # a failed onboarding operation.
        try:
            with get_postgres_connection() as db:
                with db.cursor() as cursor:
                    cursor.execute(
                        """
                        UPDATE api_keys
                        SET active = FALSE
                        WHERE id = %s
                        """,
                        (customer_id,),
                    )
        except Exception:
            print(
                "WARNING: Could not confirm key revocation. "
                f"Manually inspect customer {customer_id}."
            )

        try:
            key_file.unlink(missing_ok=True)
        except OSError:
            pass

        raise

    print("Customer created successfully!")
    print("Customer ID:", customer_id)
    print("Monthly limit:", limit)
    print("Private key file:", key_file)


def show_usage(customer_id):
    with get_postgres_connection() as db:
        with db.cursor() as cursor:
            cursor.execute(
                "SELECT id FROM api_keys WHERE id = %s",
                (customer_id,),
            )
            if cursor.fetchone() is None:
                raise ValueError("Customer ID not found.")

    print(get_postgres_usage(customer_id))


def disable_customer(customer_id):
    with get_postgres_connection() as db:
        with db.cursor() as cursor:
            cursor.execute(
                """
                UPDATE api_keys
                SET active = FALSE
                WHERE id = %s
                """,
                (customer_id,),
            )
            if cursor.rowcount == 0:
                raise ValueError("Customer ID not found.")

    print(f"Customer {customer_id} disabled.")


def main():
    parser = argparse.ArgumentParser(
        description="FieldTicket customer administration"
    )

    commands = parser.add_subparsers(
        dest="command",
        required=True,
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
