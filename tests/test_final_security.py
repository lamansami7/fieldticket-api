import inspect
from unittest.mock import MagicMock, patch
import pytest
from fastapi import HTTPException
import manage_customers
import postgres_usage

def fake_connection(cursor):
    connection = MagicMock()
    connection.__enter__.return_value = connection
    connection.cursor.return_value.__enter__.return_value = cursor
    return connection

def test_revoked_customer_cannot_be_charged():
    cursor = MagicMock()
    cursor.fetchone.return_value = None
    connection = fake_connection(cursor)
    with patch.object(postgres_usage, "get_postgres_connection", return_value=connection):
        with pytest.raises(HTTPException) as error:
            postgres_usage.charge_postgres_request(999999)
    assert error.value.status_code == 401
    query = cursor.execute.call_args.args[0]
    assert "active = TRUE" in query
    assert "FOR UPDATE" not in query

def test_monthly_limit_rejects_extra_request_atomically():
    cursor = MagicMock()
    cursor.fetchone.side_effect = [{"id": 1}, {"monthly_limit": 5}, None]
    connection = fake_connection(cursor)
    with patch.object(postgres_usage, "get_postgres_connection", return_value=connection):
        with pytest.raises(HTTPException) as error:
            postgres_usage.charge_postgres_request(1)
    assert error.value.status_code == 429
    query = cursor.execute.call_args.args[0]
    assert "ON CONFLICT" in query
    assert "WHERE usage_monthly.requests < %s" in query

def test_successful_charge_returns_correct_balance():
    cursor = MagicMock()
    cursor.fetchone.side_effect = [{"id": 1}, {"monthly_limit": 10}, {"requests": 4}]
    connection = fake_connection(cursor)
    with patch.object(postgres_usage, "get_postgres_connection", return_value=connection):
        result = postgres_usage.charge_postgres_request(1)
    assert result == {"used": 4, "limit": 10, "remaining": 6}

def test_onboarding_write_failure_attempts_revocation(tmp_path):
    fake_customer = {"customer_id": 987654, "api_key": "fake-key-for-test-only"}
    cursor = MagicMock()
    connection = fake_connection(cursor)
    with (
        patch.object(manage_customers.Path, "home", return_value=tmp_path),
        patch.object(manage_customers, "create_postgres_key", return_value=fake_customer),
        patch.object(manage_customers, "get_postgres_connection", return_value=connection),
        patch.object(manage_customers.os, "open", side_effect=PermissionError("Simulated failure")),
    ):
        with pytest.raises(PermissionError):
            manage_customers.create_customer("Failure Test", 5)
    queries = [call.args[0] for call in cursor.execute.call_args_list]
    assert any("SET active = FALSE" in query for query in queries)

def test_monthly_quota_uses_atomic_postgres_upsert():
    source = inspect.getsource(postgres_usage.charge_postgres_request)
    assert "ON CONFLICT" in source
    assert "WHERE usage_monthly.requests < %s" in source
    assert "FOR UPDATE" not in source
