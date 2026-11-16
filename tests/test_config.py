import pytest

from financial_analytics.config import Settings
from financial_analytics.repository import Filters


def test_password_is_not_in_configuration_repr():
    settings = Settings("localhost", 3306, "financial_test", "user", "private-value")
    assert "private-value" not in repr(settings)


def test_unsafe_database_identifier_rejected(monkeypatch):
    for key, value in {
        "DB_HOST": "localhost",
        "DB_NAME": "db;DROP",
        "DB_USER": "user",
        "DB_PASSWORD": "private",
    }.items():
        monkeypatch.setenv(key, value)
    with pytest.raises(ValueError, match="DB_NAME"):
        Settings.from_env()


def test_unsafe_filter_rejected():
    with pytest.raises(ValueError):
        Filters(kind="income' OR 1=1 --")
