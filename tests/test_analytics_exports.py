from datetime import date
from decimal import Decimal
from io import BytesIO

import pandas as pd
from openpyxl import load_workbook

from financial_analytics.analytics import monthly_cash_flow, to_frame, totals
from financial_analytics.exports import csv_bytes, excel_bytes


def test_empty_period_is_zero_filled():
    frame = to_frame([])
    assert totals(frame) == {"income": 0, "expenses": 0, "net": 0, "count": 0}
    monthly = monthly_cash_flow(frame, date(2026, 1, 15), date(2026, 3, 4))
    assert list(monthly.month) == ["2026-01", "2026-02", "2026-03"]
    assert all(value == Decimal("0.00") for value in monthly.net)


def test_exports_protect_formulas_and_retain_money():
    frame = pd.DataFrame(
        {
            "description": ["=1+1", " @SUM(A1)", "Normal"],
            "amount": [Decimal("0.10"), Decimal("0.20"), Decimal("1234.56")],
        }
    )
    csv = csv_bytes(frame).decode("utf-8-sig")
    assert "'=1+1" in csv
    assert "' @SUM(A1)" in csv
    assert "1234.56" in csv
    workbook = load_workbook(BytesIO(excel_bytes(frame, pd.DataFrame({"net": [Decimal("0.30")]}))))
    assert workbook.sheetnames == ["Transactions", "Monthly summary"]
    assert workbook["Transactions"]["A2"].data_type == "s"
    assert workbook["Transactions"]["A2"].value == "'=1+1"
    assert Decimal(str(workbook["Transactions"]["B4"].value)) == Decimal("1234.56")
