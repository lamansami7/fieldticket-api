import os

os.environ["FIELDTICKET_API_KEY"] = "test-secret-key"

from fastapi.testclient import TestClient
from main import app

client = TestClient(app)

sample = {
    "ticket_number": "TEST-001",
    "contractor": "Demo Electric",
    "customer": "Demo Customer",
    "project": "Demo Project",
    "work_date": "2026-10-18",
    "description": "Extra electrical work",
    "labor": [
        {
            "description": "Electrician",
            "workers": 2,
            "hours_per_worker": 3,
            "hourly_rate": 85
        }
    ],
    "materials": [
        {
            "description": "Conduit",
            "quantity": 40,
            "unit": "feet",
            "unit_price": 2.5
        }
    ],
    "markup_percent": 10,
    "tax_rate_percent": 0
}

# Use an isolated SQLite database for automated tests.
import hashlib
import tempfile
from pathlib import Path
from unittest.mock import patch
import customer_keys

_test_dir = tempfile.TemporaryDirectory()
_test_db = Path(_test_dir.name) / "test.db"
_db_patch = patch.object(customer_keys, "DB_PATH", _test_db)
_db_patch.start()

TEST_KEY = "ft_test_" + "a" * 32

with customer_keys.connect() as db:
    db.execute(
        """
        INSERT INTO api_keys
        (customer_name, key_hash, created_at, active)
        VALUES (?, ?, ?, ?)
        """,
        (
            "Automated Test Customer",
            hashlib.sha256(TEST_KEY.encode()).hexdigest(),
            "2026-10-18T00:00:00+00:00",
            1
        )
    )
    db.commit()

headers = {"X-API-Key": TEST_KEY}


def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_requires_authentication():
    response = client.post(
        "/v1/tickets/calculate", json=sample
    )
    assert response.status_code == 401


def test_rejects_wrong_key():
    response = client.post(
        "/v1/tickets/calculate",
        json=sample,
        headers={"X-API-Key": "wrong-key"}
    )
    assert response.status_code == 401


def test_calculation():
    response = client.post(
        "/v1/tickets/calculate",
        json=sample,
        headers=headers
    )
    assert response.status_code == 200
    assert response.json()["total"] == "671.00"


def test_pdf():
    response = client.post(
        "/v1/tickets/pdf",
        json=sample,
        headers=headers
    )
    assert response.status_code == 200
    assert response.content.startswith(b"%PDF")


def test_invalid_workers():
    invalid = {
        **sample,
        "labor": [{
            **sample["labor"][0],
            "workers": -2
        }]
    }
    response = client.post(
        "/v1/tickets/calculate",
        json=invalid,
        headers=headers
    )
    assert response.status_code == 422


def test_invalid_tax():
    invalid = {**sample, "tax_rate_percent": 101}
    response = client.post(
        "/v1/tickets/calculate",
        json=invalid,
        headers=headers
    )
    assert response.status_code == 422


def test_revoked_key():
    import hashlib
    import customer_keys

    key_hash = hashlib.sha256(
        TEST_KEY.encode()
    ).hexdigest()

    with customer_keys.connect() as db:
        db.execute(
            "UPDATE api_keys SET active = 0 WHERE key_hash = ?",
            (key_hash,)
        )
        db.commit()

    response = client.post(
        "/v1/tickets/calculate",
        json=sample,
        headers=headers
    )

    assert response.status_code == 401
