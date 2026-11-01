"""Integration tests using independent real PostgreSQL connections."""
import os
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
import psycopg
import pytest
from fastapi import HTTPException
from postgres_rate_limits import charge_postgres_rate_limit
from postgres_usage import charge_postgres_request

TEST_DATABASE_URL = os.getenv("FIELD_TICKET_TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(not TEST_DATABASE_URL, reason="Set FIELD_TICKET_TEST_DATABASE_URL to run PostgreSQL integration tests")

def test_postgres_shared_rate_limit_is_atomic_under_concurrency(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", TEST_DATABASE_URL)
    customer_id = int(time.time_ns() % 8_000_000_000_000_000) + 1
    limit = 7
    with psycopg.connect(TEST_DATABASE_URL) as db:
        with db.cursor() as cursor:
            cursor.execute("DELETE FROM public.request_rate_limits WHERE customer_id = %s", (customer_id,))
    def attempt(_):
        try:
            charge_postgres_rate_limit(customer_id, limit=limit, window_seconds=60)
            return True
        except HTTPException as exc:
            if exc.status_code == 429:
                return False
            raise
    try:
        with ThreadPoolExecutor(max_workers=24) as pool:
            outcomes = list(pool.map(attempt, range(24)))
        assert sum(outcomes) == limit
        with psycopg.connect(TEST_DATABASE_URL) as db:
            with db.cursor() as cursor:
                cursor.execute("SELECT request_count FROM public.request_rate_limits WHERE customer_id = %s", (customer_id,))
                row = cursor.fetchone()
        assert row is not None and row[0] == limit
    finally:
        with psycopg.connect(TEST_DATABASE_URL) as db:
            with db.cursor() as cursor:
                cursor.execute("DELETE FROM public.request_rate_limits WHERE customer_id = %s", (customer_id,))

def test_postgres_monthly_quota_is_atomic_under_concurrency(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", TEST_DATABASE_URL)
    customer_id = int(time.time_ns() % 8_000_000_000_000_000) + 1
    limit = 6
    key_hash = uuid.uuid4().hex
    with psycopg.connect(TEST_DATABASE_URL) as db:
        with db.cursor() as cursor:
            cursor.execute("INSERT INTO public.api_keys (id, customer_name, key_hash, created_at, active) VALUES (%s, %s, %s, now(), TRUE)", (customer_id, "Concurrency test", key_hash))
            cursor.execute("INSERT INTO public.customer_plans (customer_id, monthly_limit) VALUES (%s, %s)", (customer_id, limit))
    def attempt(_):
        try:
            charge_postgres_request(customer_id)
            return True
        except HTTPException as exc:
            if exc.status_code == 429:
                return False
            raise
    try:
        with ThreadPoolExecutor(max_workers=20) as pool:
            outcomes = list(pool.map(attempt, range(20)))
        assert sum(outcomes) == limit
        with psycopg.connect(TEST_DATABASE_URL) as db:
            with db.cursor() as cursor:
                cursor.execute("SELECT requests FROM public.usage_monthly WHERE customer_id = %s AND month = to_char(now() AT TIME ZONE 'UTC', 'YYYY-MM')", (customer_id,))
                row = cursor.fetchone()
        assert row is not None and row[0] == limit
    finally:
        with psycopg.connect(TEST_DATABASE_URL) as db:
            with db.cursor() as cursor:
                cursor.execute("DELETE FROM public.usage_monthly WHERE customer_id = %s", (customer_id,))
                cursor.execute("DELETE FROM public.customer_plans WHERE customer_id = %s", (customer_id,))
                cursor.execute("DELETE FROM public.api_keys WHERE id = %s", (customer_id,))

def test_postgres_rate_window_rolls_over(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", TEST_DATABASE_URL)
    customer_id = int(time.time_ns() % 8_000_000_000_000_000) + 1
    try:
        assert charge_postgres_rate_limit(customer_id, limit=2, window_seconds=1)["requests_in_window"] == 1
        time.sleep(1.1)
        assert charge_postgres_rate_limit(customer_id, limit=2, window_seconds=1)["requests_in_window"] == 1
    finally:
        with psycopg.connect(TEST_DATABASE_URL) as db:
            with db.cursor() as cursor:
                cursor.execute("DELETE FROM public.request_rate_limits WHERE customer_id = %s", (customer_id,))
