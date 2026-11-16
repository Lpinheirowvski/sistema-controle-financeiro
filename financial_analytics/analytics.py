"""Exact financial calculations; Pandas organizes data, charts alone use floats."""

from datetime import date
from decimal import Decimal

import pandas as pd

ZERO = Decimal("0.00")
COLUMNS = [
    "id",
    "description",
    "amount",
    "transaction_date",
    "category_id",
    "account_id",
    "legacy_id",
    "demo_key",
    "revision",
    "created_at",
    "updated_at",
    "category",
    "kind",
    "account",
    "signed_amount",
]


def to_frame(rows):
    return pd.DataFrame(rows, columns=COLUMNS)


def totals(frame):
    income = sum(frame.loc[frame.kind == "income", "amount"], ZERO)
    expenses = sum(frame.loc[frame.kind == "expense", "amount"], ZERO)
    return {"income": income, "expenses": expenses, "net": income - expenses, "count": len(frame)}


def monthly_cash_flow(frame, start, end):
    """Calendar months, including empty ones. Cumulative net starts at the filter boundary."""
    rows, cumulative = [], ZERO
    month = start.replace(day=1)
    last = end.replace(day=1)
    while month <= last:
        selected = frame[
            frame.transaction_date.map(
                lambda value, current=month: value.year == current.year
                and value.month == current.month
            ).astype(bool)
        ]
        values = totals(selected)
        cumulative += values["net"]
        rows.append({"month": month.isoformat()[:7], **values, "cumulative_net": cumulative})
        if month.year == 9999 and month.month == 12:
            break
        month = date(month.year + (month.month == 12), month.month % 12 + 1, 1)
    return pd.DataFrame(rows)


def expense_categories(frame):
    expenses = frame[frame.kind == "expense"]
    if expenses.empty:
        return pd.DataFrame(columns=["category", "expenses"])
    return (
        expenses.groupby("category", as_index=False)
        .agg(expenses=("amount", "sum"))
        .sort_values("expenses", ascending=False)
    )


def running_balance(frame):
    ordered = frame.sort_values(["transaction_date", "id"]).copy()
    running = ZERO
    values = []
    for value in ordered.signed_amount:
        running += value
        values.append(running)
    ordered["cumulative_balance"] = values
    return ordered
