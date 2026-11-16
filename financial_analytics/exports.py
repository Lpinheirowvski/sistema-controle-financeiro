"""In-memory CSV/Excel reports, with spreadsheet formula injection protection."""

from io import BytesIO

import pandas as pd


def _safe_text(value):
    if isinstance(value, str) and value.lstrip().startswith(("=", "+", "-", "@")):
        return "'" + value
    return value


def safe_frame(frame):
    return frame.map(_safe_text)


def csv_bytes(frame):
    return safe_frame(frame).to_csv(index=False).encode("utf-8-sig")


def excel_bytes(transactions, monthly):
    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        safe_frame(transactions).to_excel(writer, sheet_name="Transactions", index=False)
        safe_frame(monthly).to_excel(writer, sheet_name="Monthly summary", index=False)
        for sheet in writer.book.worksheets:
            sheet.freeze_panes = "A2"
            sheet.auto_filter.ref = sheet.dimensions
            for column in sheet.columns:
                sheet.column_dimensions[column[0].column_letter].width = 22
    return output.getvalue()
