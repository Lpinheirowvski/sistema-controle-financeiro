"""Parameterized queries and transaction CRUD. No SQL values are interpolated."""

import logging
from dataclasses import dataclass
from datetime import date

from financial_analytics.db import connection
from financial_analytics.validation import TransactionInput

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Filters:
    start: date | None = None
    end: date | None = None
    category_ids: tuple[int, ...] = ()
    kind: str | None = None

    def __post_init__(self):
        if any(value is not None and type(value) is not date for value in (self.start, self.end)):
            raise ValueError("Filter dates must be dates.")
        if self.start and self.end and self.start > self.end:
            raise ValueError("Start date must be on or before end date.")
        if self.kind not in (None, "income", "expense"):
            raise ValueError("Choose income, expense or all types.")
        if any(type(value) is not int or value <= 0 for value in self.category_ids):
            raise ValueError("Invalid category filter.")


def where_clause(filters):
    clauses, params = [], []
    for value, sql in [
        (filters.start, "transaction_date >= %s"),
        (filters.end, "transaction_date <= %s"),
        (filters.kind, "kind = %s"),
    ]:
        if value is not None:
            clauses.append(sql)
            params.append(value)
    if filters.category_ids:
        clauses.append("category_id IN (" + ",".join(["%s"] * len(filters.category_ids)) + ")")
        params.extend(filters.category_ids)
    return (" WHERE " + " AND ".join(clauses) if clauses else ""), params


class TransactionRepository:
    def __init__(self, settings=None):
        self.settings = settings

    def _query(self, sql, params=()):
        with connection(self.settings) as conn:
            with conn.cursor(dictionary=True) as cursor:
                cursor.execute(sql, params)
                return cursor.fetchall()

    def list(self, filters=None):
        where, params = where_clause(filters or Filters())
        return self._query(
            "SELECT * FROM v_transaction_details" + where + " ORDER BY transaction_date, id", params
        )

    def get(self, transaction_id):
        rows = self._query("SELECT * FROM v_transaction_details WHERE id = %s", (transaction_id,))
        if not rows:
            raise ValueError("Transaction no longer exists. Refresh the page.")
        return rows[0]

    def categories(self):
        return self._query("SELECT id, name, kind FROM categories ORDER BY kind, name")

    def accounts(self):
        return self._query("SELECT id, name, account_type FROM accounts ORDER BY name")

    def date_bounds(self):
        return self._query(
            "SELECT MIN(transaction_date) AS first_date, "
            "MAX(transaction_date) AS last_date FROM transactions"
        )[0]

    @staticmethod
    def _values(item):
        item = TransactionInput.parse(
            item.description, item.amount, item.transaction_date, item.category_id, item.account_id
        )
        return (
            item.description,
            item.amount,
            item.transaction_date,
            item.category_id,
            item.account_id,
        )

    def create(self, item):
        with connection(self.settings) as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    "INSERT INTO transactions (description, amount, transaction_date, "
                    "category_id, account_id) VALUES (%s,%s,%s,%s,%s)",
                    self._values(item),
                )
                transaction_id = cursor.lastrowid
        logger.info("Transaction created (id=%s)", transaction_id)
        return transaction_id

    def update(self, transaction_id, item, revision):
        with connection(self.settings) as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    "UPDATE transactions SET description=%s, amount=%s, "
                    "transaction_date=%s, category_id=%s, account_id=%s, "
                    "revision=revision+1 WHERE id=%s AND revision=%s",
                    self._values(item) + (transaction_id, revision),
                )
                if cursor.rowcount != 1:
                    raise ValueError("Transaction changed or was removed. Refresh before saving.")
        logger.info("Transaction updated (id=%s)", transaction_id)

    def delete(self, transaction_id, revision):
        with connection(self.settings) as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    "DELETE FROM transactions WHERE id=%s AND revision=%s",
                    (transaction_id, revision),
                )
                if cursor.rowcount != 1:
                    raise ValueError("Transaction changed or was removed. Refresh before deleting.")
        logger.info("Transaction deleted (id=%s)", transaction_id)
