from datetime import date
from decimal import Decimal

import pytest

from financial_analytics.validation import TransactionInput


@pytest.mark.parametrize("value", ["0", "-1", "1.001", "NaN", "Infinity", "x", "10000000000"])
def test_invalid_money(value):
    with pytest.raises(ValueError):
        TransactionInput.parse("Example", value, date(2026, 1, 1), 1, 1)


def test_money_is_decimal():
    item = TransactionInput.parse(" Example ", "0.10", date(2026, 1, 1), 1, 1)
    assert item.amount == Decimal("0.10")
    assert item.description == "Example"


@pytest.mark.parametrize("description", ["", "  ", None, "x" * 201])
def test_invalid_description(description):
    with pytest.raises(ValueError):
        TransactionInput.parse(description, 1, date(2026, 1, 1), 1, 1)


@pytest.mark.parametrize("category,account", [(0, 1), (1, -1), (True, 1), ("1", 1)])
def test_invalid_relationship(category, account):
    with pytest.raises(ValueError):
        TransactionInput.parse("Example", 1, date(2026, 1, 1), category, account)
