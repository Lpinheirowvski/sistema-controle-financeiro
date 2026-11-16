from datetime import date
from decimal import Decimal

import pytest

from financial_analytics.analytics import monthly_cash_flow, running_balance, to_frame, totals
from financial_analytics.db import DatabaseError, connection
from financial_analytics.migrations import initialize
from financial_analytics.repository import Filters, TransactionRepository
from financial_analytics.validation import TransactionInput

pytestmark = pytest.mark.integration


@pytest.fixture
def repository(mysql_settings):
    initialize(mysql_settings)
    return TransactionRepository(mysql_settings)


def item(repo, amount="100.10", kind="income", day=date(2026, 1, 1), description="Example"):
    category = next(c["id"] for c in repo.categories() if c["kind"] == kind)
    return TransactionInput.parse(description, amount, day, category, repo.accounts()[0]["id"])


def test_crud_filters_and_optimistic_lock(repository):
    repo = repository
    first = repo.create(item(repo, description="Robert'); DROP TABLE transactions; --"))
    row = repo.get(first)
    assert row["amount"] == Decimal("100.10")
    assert row["description"].startswith("Robert');")
    repo.update(first, item(repo, amount="75.25", kind="expense"), row["revision"])
    updated = repo.get(first)
    assert updated["amount"] == Decimal("75.25")
    assert updated["kind"] == "expense"
    with pytest.raises(ValueError, match="changed"):
        repo.update(first, item(repo), row["revision"])
    assert not repo.list(Filters(kind="income"))
    assert len(repo.list(Filters(category_ids=(updated["category_id"],)))) == 1
    assert not repo.list(Filters(date(2026, 2, 1), date(2026, 2, 28)))
    with pytest.raises(ValueError, match="changed"):
        repo.delete(first, row["revision"])
    repo.delete(first, updated["revision"])
    with pytest.raises(ValueError, match="no longer exists"):
        repo.get(first)


def test_foreign_keys_and_checks(repository, mysql_settings):
    repo = repository
    good = item(repo)
    bad = TransactionInput.parse("Orphan", "1", date(2026, 1, 1), 999999, good.account_id)
    with pytest.raises(DatabaseError):
        repo.create(bad)
    with pytest.raises(DatabaseError):
        with connection(mysql_settings) as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    "INSERT INTO transactions "
                    "(description,amount,transaction_date,category_id,account_id) "
                    "VALUES (%s,%s,%s,%s,%s)",
                    ("Bad", -1, date(2026, 1, 1), good.category_id, good.account_id),
                )
    assert repo.list() == []
    created = repo.create(good)
    with pytest.raises(DatabaseError):
        with connection(mysql_settings) as conn:
            with conn.cursor() as cursor:
                cursor.execute("DELETE FROM categories WHERE id=%s", (good.category_id,))
    assert repo.get(created)


def test_sql_and_python_money_reconcile_with_missing_month(repository, mysql_settings):
    repo = repository
    repo.create(item(repo, amount="0.10"))
    repo.create(item(repo, amount="0.20"))
    repo.create(item(repo, amount="0.07", kind="expense", day=date(2026, 3, 1)))
    frame = to_frame(repo.list())
    assert totals(frame) == {
        "income": Decimal("0.30"),
        "expenses": Decimal("0.07"),
        "net": Decimal("0.23"),
        "count": 3,
    }
    monthly = monthly_cash_flow(frame, date(2026, 1, 1), date(2026, 3, 31))
    assert list(monthly.net) == [Decimal("0.30"), Decimal("0.00"), Decimal("-0.07")]
    assert running_balance(frame).cumulative_balance.iloc[-1] == Decimal("0.23")
    with connection(mysql_settings) as conn:
        with conn.cursor(dictionary=True) as cursor:
            cursor.execute("SELECT * FROM v_monthly_summary ORDER BY month")
            rows = cursor.fetchall()
    assert [r["net"] for r in rows] == list(monthly.net)
    assert rows[-1]["previous_net"] == 0  # February, not the last non-empty month.
    assert rows[-1]["net_change"] == Decimal("-0.07")
    assert rows[-1]["cumulative_net"] == Decimal("0.23")


def test_reinitialization_does_not_resurrect_deleted_demo(mysql_settings):
    initialize(mysql_settings, seed=True)
    repo = TransactionRepository(mysql_settings)
    row = repo.list()[0]
    repo.delete(row["id"], row["revision"])
    initialize(mysql_settings, seed=True)
    assert len(repo.list()) == 239
