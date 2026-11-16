"""Initialization and automated report exports: python -m financial_analytics.cli."""

import argparse
import logging
from datetime import date
from pathlib import Path

from financial_analytics.analytics import monthly_cash_flow, to_frame, totals
from financial_analytics.db import DatabaseError, configure_logging
from financial_analytics.exports import csv_bytes, excel_bytes
from financial_analytics.migrations import initialize
from financial_analytics.repository import Filters, TransactionRepository


def main():
    parser = argparse.ArgumentParser(description="Financial Analytics System v2.0")
    commands = parser.add_subparsers(dest="command", required=True)
    init = commands.add_parser("init", help="Apply additive schema and import legacy data")
    init.add_argument("--seed", action="store_true", help="Add 240 demo transactions once")
    export = commands.add_parser("export", help="Export a filtered report for automation")
    export.add_argument("--start", type=date.fromisoformat, required=True)
    export.add_argument("--end", type=date.fromisoformat, required=True)
    export.add_argument("--output", type=Path, default=Path("reports"))
    args = parser.parse_args()
    configure_logging()
    try:
        if args.command == "init":
            result = initialize(seed=args.seed)
            print(
                f"Initialization complete: {result['imported']} imported, "
                f"{result['seeded']} seeded."
            )
        else:
            filters = Filters(args.start, args.end)
            frame = to_frame(TransactionRepository().list(filters))
            monthly = monthly_cash_flow(frame, args.start, args.end)
            args.output.mkdir(parents=True, exist_ok=True)
            (args.output / "transactions.csv").write_bytes(csv_bytes(frame))
            (args.output / "financial-report.xlsx").write_bytes(excel_bytes(frame, monthly))
            print(f"Exported {totals(frame)['count']} transactions to {args.output}.")
    except (ValueError, DatabaseError, OSError) as exc:
        logging.getLogger(__name__).error("%s", exc)
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()
