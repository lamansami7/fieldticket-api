from unittest.mock import MagicMock, patch

from postgres_schema import initialize_postgres


def test_postgres_schema_initialization():
    connection = MagicMock()
    cursor = MagicMock()

    connection.__enter__.return_value = connection
    connection.cursor.return_value.__enter__.return_value = cursor

    with patch(
        "postgres_schema.get_postgres_connection",
        return_value=connection,
    ):
        result = initialize_postgres()

    assert result is True
    assert cursor.execute.call_count == 3

    statements = [
        call.args[0]
        for call in cursor.execute.call_args_list
    ]

    assert "CREATE TABLE IF NOT EXISTS api_keys" in statements[0]
    assert "CREATE TABLE IF NOT EXISTS usage_monthly" in statements[1]
    assert "CREATE TABLE IF NOT EXISTS customer_plans" in statements[2]
