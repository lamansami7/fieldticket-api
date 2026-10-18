from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException

from postgres_usage import (
    charge_postgres_request,
    get_postgres_usage,
)


def fake_connection(results):
    connection = MagicMock()
    cursor = MagicMock()

    connection.__enter__.return_value = connection
    connection.cursor.return_value.__enter__.return_value = cursor
    cursor.fetchone.side_effect = results

    return connection, cursor


def test_get_postgres_usage():
    connection, cursor = fake_connection([
        {"monthly_limit": 100},
        {"requests": 25},
    ])

    with patch(
        "postgres_usage.get_postgres_connection",
        return_value=connection,
    ):
        result = get_postgres_usage(42)

    assert result["monthly_limit"] == 100
    assert result["requests_used"] == 25
    assert result["requests_remaining"] == 75


def test_charge_postgres_request():
    connection, cursor = fake_connection([
        {"id": 42},
        {"monthly_limit": 100},
        {"requests": 25},
    ])

    with patch(
        "postgres_usage.get_postgres_connection",
        return_value=connection,
    ):
        result = charge_postgres_request(42)

    assert result["used"] == 26
    assert result["remaining"] == 74
    assert cursor.execute.call_count == 4


def test_reject_postgres_quota_exceeded():
    connection, cursor = fake_connection([
        {"id": 42},
        {"monthly_limit": 100},
        {"requests": 100},
    ])

    with patch(
        "postgres_usage.get_postgres_connection",
        return_value=connection,
    ):
        with pytest.raises(HTTPException) as error:
            charge_postgres_request(42)

    assert error.value.status_code == 429
    assert cursor.execute.call_count == 3


def test_reject_missing_postgres_customer():
    connection, cursor = fake_connection([None])

    with patch(
        "postgres_usage.get_postgres_connection",
        return_value=connection,
    ):
        with pytest.raises(HTTPException) as error:
            charge_postgres_request(999)

    assert error.value.status_code == 401
    assert cursor.execute.call_count == 1
