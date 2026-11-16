"""Integration tests create only uniquely named databases ending in _test_<hex>."""

import os
import uuid
from dataclasses import replace

import pytest

from financial_analytics.config import Settings
from financial_analytics.db import connection


@pytest.fixture
def mysql_settings():
    if os.getenv("RUN_MYSQL_TESTS") != "1":
        pytest.skip("Set RUN_MYSQL_TESTS=1 for real MySQL integration tests.")
    settings = Settings.from_env()
    if not settings.database.endswith("_test"):
        pytest.fail("Integration server DB_NAME must end with _test; refusing unsafe target.")
    name = "financial_test_" + uuid.uuid4().hex
    with connection(settings) as conn:
        with conn.cursor() as cursor:
            cursor.execute(f"CREATE DATABASE `{name}` CHARACTER SET utf8mb4")
    try:
        yield replace(settings, database=name)
    finally:
        # Only remove the database created by this fixture, never the configured source.
        with connection(settings) as conn:
            with conn.cursor() as cursor:
                cursor.execute(f"DROP DATABASE `{name}`")
