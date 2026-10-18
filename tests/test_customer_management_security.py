from unittest.mock import MagicMock, patch

import pytest

import manage_customers


def test_rejects_blank_customer_name():
    with pytest.raises(ValueError):
        manage_customers.create_customer("   ", 100)


def test_rejects_negative_monthly_limit():
    with pytest.raises(ValueError):
        manage_customers.create_customer("Example Company", -1)


def test_customer_creation_does_not_start_for_invalid_input():
    with patch.object(
        manage_customers,
        "create_postgres_key",
    ) as create_key:
        with pytest.raises(ValueError):
            manage_customers.create_customer("", 100)

        with pytest.raises(ValueError):
            manage_customers.create_customer("Company", -5)

        create_key.assert_not_called()


def test_missing_customer_cannot_be_disabled():
    cursor = MagicMock()
    cursor.rowcount = 0

    connection = MagicMock()
    connection.__enter__.return_value = connection
    connection.cursor.return_value.__enter__.return_value = cursor

    with patch.object(
        manage_customers,
        "get_postgres_connection",
        return_value=connection,
    ):
        with pytest.raises(
            ValueError,
            match="Customer ID not found",
        ):
            manage_customers.disable_customer(999999)


def test_failed_key_save_triggers_revocation(tmp_path):
    fake_customer = {
        "customer_id": 999999,
        "api_key": "test-key-not-real",
    }

    cursor = MagicMock()
    connection = MagicMock()
    connection.__enter__.return_value = connection
    connection.cursor.return_value.__enter__.return_value = cursor

    with (
        patch.object(
            manage_customers.Path,
            "home",
            return_value=tmp_path,
        ),
        patch.object(
            manage_customers,
            "create_postgres_key",
            return_value=fake_customer,
        ),
        patch.object(
            manage_customers,
            "get_postgres_connection",
            return_value=connection,
        ),
        patch.object(
            manage_customers.os,
            "open",
            side_effect=PermissionError("Simulated write failure"),
        ),
    ):
        with pytest.raises(PermissionError):
            manage_customers.create_customer("Test Company", 10)

    sql_statements = [
        call.args[0]
        for call in cursor.execute.call_args_list
    ]

    assert any(
        "SET active = FALSE" in statement
        for statement in sql_statements
    )


def test_quota_charge_checks_active_customer():
    import inspect
    from postgres_usage import charge_postgres_request

    source = inspect.getsource(charge_postgres_request)

    assert "active = TRUE" in source
    assert "FOR UPDATE" in source
