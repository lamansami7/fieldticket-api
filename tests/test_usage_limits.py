import hashlib
import tempfile
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

import customer_keys
from main import app
from usage_limits import initialize_usage

client = TestClient(app)

TEST_KEY = "ft_test_quota_example_key"
TEST_CUSTOMER = "Quota Test Customer"

sample = {
    "ticket_number": "QUOTA-001",
    "contractor": "Test Contractor",
    "customer": "Test Customer",
    "project": "Test Project",
    "work_date": "2026-10-18",
    "description": "Testing monthly request limits",
    "labor": [],
    "materials": [],
    "tax_rate_percent": 0,
    "markup_percent": 0,
}


def test_monthly_quota():
    with tempfile.TemporaryDirectory() as directory:
        test_db = Path(directory) / "quota.db"

        with patch.object(customer_keys, "DB_PATH", test_db):
            with customer_keys.connect() as db:
                cursor = db.execute(
                    """
                    INSERT INTO api_keys
                    (customer_name, key_hash, created_at, active)
                    VALUES (?, ?, ?, 1)
                    """,
                    (
                        TEST_CUSTOMER,
                        hashlib.sha256(
                            TEST_KEY.encode()
                        ).hexdigest(),
                        "2026-10-18T00:00:00+00:00",
                    )
                )
                customer_id = cursor.lastrowid
                db.commit()

            initialize_usage()

            with customer_keys.connect() as db:
                db.execute(
                    """
                    INSERT INTO customer_plans
                    (customer_id, monthly_limit)
                    VALUES (?, ?)
                    """,
                    (customer_id, 2)
                )
                db.commit()

            headers = {"X-API-Key": TEST_KEY}

            first = client.post(
                "/v1/tickets/calculate",
                json=sample,
                headers=headers
            )
            second = client.post(
                "/v1/tickets/calculate",
                json=sample,
                headers=headers
            )
            third = client.post(
                "/v1/tickets/calculate",
                json=sample,
                headers=headers
            )

            assert first.status_code == 200
            assert second.status_code == 200
            assert third.status_code == 429

            assert (
                third.json()["detail"]
                == "Monthly API request limit reached"
            )
