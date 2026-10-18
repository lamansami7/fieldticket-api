from unittest.mock import MagicMock, patch

from postgres_customers import (
    authenticate_postgres_key,
    create_postgres_key,
)


def fake_connection(result):
    connection = MagicMock()
    cursor = MagicMock()

    connection.__enter__.return_value = connection
    connection.cursor.return_value.__enter__.return_value = cursor
    cursor.fetchone.return_value = result

    return connection, cursor


def test_create_postgres_key():
    connection, cursor = fake_connection({"id": 42})

    with patch(
        "postgres_customers.get_postgres_connection",
        return_value=connection,
    ):
        result = create_postgres_key("Test Company")

    assert result["customer_id"] == 42
    assert result["api_key"].startswith("ft_live_")

    statement, params = cursor.execute.call_args.args

    assert "INSERT INTO api_keys" in statement
    assert params[0] == "Test Company"
    assert params[1] != result["api_key"]


def test_authenticate_postgres_key():
    connection, cursor = fake_connection({
        "id": 42,
        "customer_name": "Test Company",
    })

    with patch(
        "postgres_customers.get_postgres_connection",
        return_value=connection,
    ):
        result = authenticate_postgres_key("ft_live_example")

    assert result["customer_id"] == 42
    assert result["customer_name"] == "Test Company"

    statement, params = cursor.execute.call_args.args

    assert "active = TRUE" in statement
    assert len(params[0]) == 64


def test_reject_unknown_postgres_key():
    connection, cursor = fake_connection(None)

    with patch(
        "postgres_customers.get_postgres_connection",
        return_value=connection,
    ):
        result = authenticate_postgres_key("invalid-key")

    assert result is None


def test_reject_empty_customer_name():
    try:
        create_postgres_key("   ")
    except ValueError:
        pass
    else:
        raise AssertionError("Empty customer name was accepted")
