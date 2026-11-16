"""Exercise Streamlit forms against a real, disposable MySQL database."""

from decimal import Decimal

import pytest
from streamlit.testing.v1 import AppTest

from financial_analytics.migrations import ROOT, initialize
from financial_analytics.repository import TransactionRepository

pytestmark = pytest.mark.integration


def test_dashboard_filter_add_edit_delete(mysql_settings, monkeypatch):
    initialize(mysql_settings, seed=True)
    for key, value in {
        "DB_HOST": mysql_settings.host,
        "DB_PORT": str(mysql_settings.port),
        "DB_NAME": mysql_settings.database,
        "DB_USER": mysql_settings.user,
        "DB_PASSWORD": mysql_settings.password,
    }.items():
        monkeypatch.setenv(key, value)
    repo = TransactionRepository(mysql_settings)
    at = AppTest.from_file(str(ROOT / "app.py"), default_timeout=30).run()
    assert not at.exception
    assert not at.error
    assert at.metric[3].value == "240"
    next(s for s in at.selectbox if s.label == "Transaction type").select("Expense").run()
    assert at.metric[0].value == "R$ 0.00"
    assert at.metric[3].value == "192"
    next(s for s in at.selectbox if s.label == "Transaction type").select("All types").run()
    at.text_input(key="description-new").input("Dashboard test transaction")
    at.text_input(key="amount-new").input("42.10")
    next(b for b in at.button if b.label == "Add transaction").click().run()
    assert not at.exception
    assert not at.error
    row = next(r for r in repo.list() if r["description"] == "Dashboard test transaction")
    assert row["amount"] == Decimal("42.10")
    assert at.metric[3].value == "241"
    next(s for s in at.selectbox if s.label == "Select a transaction").select(row["id"]).run()
    at.text_input(key=f"amount-{row['id']}-1").input("43.20")
    next(b for b in at.button if b.label == "Save changes").click().run()
    assert not at.exception
    assert not at.error
    assert repo.get(row["id"])["amount"] == Decimal("43.20")
    at.checkbox(key=f"delete-confirm-{row['id']}").check().run()
    next(b for b in at.button if b.label == "Delete transaction").click().run()
    assert not at.exception
    assert not at.error
    assert len(repo.list()) == 240
