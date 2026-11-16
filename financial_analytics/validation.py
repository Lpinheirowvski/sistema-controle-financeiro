"""Validate money before handing it to MySQL. Financial values use Decimal."""

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, InvalidOperation


@dataclass(frozen=True)
class TransactionInput:
    description: str
    amount: Decimal
    transaction_date: date
    category_id: int
    account_id: int

    @classmethod
    def parse(cls, description, amount, transaction_date, category_id, account_id):
        if not isinstance(description, str):
            raise ValueError("Description must be text.")
        description = description.strip()
        if not 1 <= len(description) <= 200:
            raise ValueError("Description must contain 1–200 characters.")
        try:
            value = Decimal(str(amount))
            if (
                not value.is_finite()
                or value <= 0
                or value > Decimal("9999999999.99")
                or value != value.quantize(Decimal("0.01"))
            ):
                raise ValueError("Amount must be positive with at most two decimal places.")
        except InvalidOperation:
            raise ValueError("Enter a valid monetary amount.") from None
        if isinstance(transaction_date, datetime):
            transaction_date = transaction_date.date()
        if not isinstance(transaction_date, date) or transaction_date.year < 1000:
            raise ValueError("Enter a valid date (year 1000 or later).")
        ids = (category_id, account_id)
        if any(type(item) is not int or item <= 0 for item in ids):
            raise ValueError("Choose a valid category and account.")
        return cls(description, value.quantize(Decimal("0.01")), transaction_date, *ids)
