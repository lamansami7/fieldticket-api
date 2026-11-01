from unittest.mock import patch
import pytest
from fastapi.testclient import TestClient
from database_backend import use_postgres
from main import app

client = TestClient(app)

def test_sqlite_is_default():
    with patch.dict("os.environ", {}, clear=True):
        assert use_postgres() is False

def test_postgres_selection():
    with patch.dict("os.environ", {"DATABASE_BACKEND": "postgres"}):
        assert use_postgres() is True

def test_invalid_backend():
    with patch.dict("os.environ", {"DATABASE_BACKEND": "invalid"}):
        with pytest.raises(RuntimeError):
            use_postgres()

def test_postgres_usage_endpoint():
    customer = {"customer_id": 42, "customer_name": "Test Company"}
    usage = {"month": "2026-10", "monthly_limit": 100, "requests_used": 25, "requests_remaining": 75}
    with patch.dict("os.environ", {"DATABASE_BACKEND": "postgres"}):
        with patch("postgres_customers.authenticate_postgres_key", return_value=customer):
            with patch("postgres_usage.get_postgres_usage", return_value=usage):
                response = client.get("/v1/usage", headers={"X-API-Key": "test-key"})
    assert response.status_code == 200
    assert response.json()["requests_remaining"] == 75

def test_postgres_calculate_charges_shared_and_monthly_limits():
    sample = {
        "ticket_number": "PG-001", "contractor": "Test Contractor",
        "customer": "Test Customer", "project": "Test Project",
        "work_date": "2026-10-18", "description": "PostgreSQL backend test",
        "labor": [], "materials": [], "tax_rate_percent": 0, "markup_percent": 0,
    }
    customer = {"customer_id": 42, "customer_name": "Test Company"}
    with patch.dict("os.environ", {"DATABASE_BACKEND": "postgres"}):
        with patch("postgres_customers.authenticate_postgres_key", return_value=customer):
            with patch("postgres_rate_limits.charge_postgres_rate_limit") as throttle:
                with patch("postgres_usage.charge_postgres_request") as quota:
                    response = client.post("/v1/tickets/calculate", json=sample, headers={"X-API-Key": "test-key"})
    assert response.status_code == 200
    throttle.assert_called_once_with(42)
    quota.assert_called_once_with(42)

def test_runtime_and_admin_connections_are_separate(monkeypatch):
    from postgres_db import get_postgres_connection
    monkeypatch.setenv("DATABASE_URL", "postgresql://runtime:test@db/runtime")
    monkeypatch.setenv("FIELD_TICKET_ADMIN_DATABASE_URL", "postgresql://admin:test@db/admin")
    with patch("postgres_db.psycopg.connect") as connect:
        get_postgres_connection()
        get_postgres_connection(admin=True)
    assert connect.call_args_list[0].args[0] == "postgresql://runtime:test@db/runtime"
    assert connect.call_args_list[1].args[0] == "postgresql://admin:test@db/admin"
