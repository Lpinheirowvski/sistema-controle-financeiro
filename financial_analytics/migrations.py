"""Additive schema, verified legacy import, and opt-in deterministic demo data."""

import hashlib
import json
import logging
import os
import tempfile
from datetime import date
from decimal import Decimal
from pathlib import Path

from financial_analytics.db import connection
from financial_analytics.validation import TransactionInput

ROOT = Path(__file__).resolve().parent.parent
logger = logging.getLogger(__name__)
LEGACY_VERSION = "002_legacy_import"
DEMO_VERSION = "003_demo_2026"
CATEGORIES = [
    ("Uncategorized income", "income"),
    ("Uncategorized expense", "expense"),
    ("Consulting", "income"),
    ("Product sales", "income"),
    ("Housing", "expense"),
    ("Utilities", "expense"),
    ("Food", "expense"),
    ("Transport", "expense"),
    ("Health", "expense"),
    ("Education", "expense"),
    ("Leisure", "expense"),
]


def execute_script(cursor, path):
    """These checked-in scripts contain plain statements, no routines or delimiters."""
    source = Path(path).read_text(encoding="utf-8")
    source = "\n".join(line for line in source.splitlines() if not line.lstrip().startswith("--"))
    for statement in source.split(";"):
        if statement.strip():
            cursor.execute(statement)
            if cursor.with_rows:
                cursor.fetchall()


def _applied(cursor, version):
    cursor.execute("SELECT version FROM schema_migrations WHERE version = %s", (version,))
    return cursor.fetchone() is not None


def _mark(cursor, version):
    cursor.execute("INSERT INTO schema_migrations (version) VALUES (%s)", (version,))


def _backup(rows, database, directory):
    """A private, atomic JSON snapshot; a failed backup prevents the import."""
    payload = json.dumps(
        {"database": database, "table": "transacoes", "rows": rows},
        default=str,
        ensure_ascii=False,
        indent=2,
    ).encode("utf-8")
    checksum = hashlib.sha256(payload).hexdigest()
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    descriptor, temporary = tempfile.mkstemp(prefix=".legacy-", dir=directory)
    destination = directory / f"legacy-{database}-{checksum}.json"
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, destination)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
    logger.info("Legacy backup created (%s rows, sha256=%s)", len(rows), checksum)
    return destination


def _legacy_import(cursor, database, backup_dir):
    if _applied(cursor, LEGACY_VERSION):
        return 0
    cursor.execute(
        "SELECT 1 FROM information_schema.tables "
        "WHERE table_schema = %s AND table_name = 'transacoes'",
        (database,),
    )
    if cursor.fetchone() is None:
        # Do not mark absent sources: an operator can restore a legacy table later.
        return 0
    # Lock the source rows/range through backup and import. Stop legacy writers beforehand.
    cursor.execute("SELECT * FROM transacoes ORDER BY id FOR SHARE")
    rows = cursor.fetchall()
    _backup(rows, database, backup_dir)
    cursor.execute("SELECT id FROM accounts WHERE name = 'Legacy account'")
    account_id = cursor.fetchone()["id"]
    cursor.execute("SELECT id, kind FROM categories WHERE name LIKE 'Uncategorized %'")
    categories = {row["kind"]: row["id"] for row in cursor.fetchall()}
    for row in rows:
        kind = {"receita": "income", "despesa": "expense"}.get(row.get("tipo"))
        if kind is None:
            raise ValueError(f"Legacy row {row['id']} has an unsupported type; import aborted.")
        item = TransactionInput.parse(
            row["descricao"], row["valor"], row["data_transacao"], categories[kind], account_id
        )
        cursor.execute(
            "INSERT INTO transactions "
            "(description, amount, transaction_date, category_id, account_id, legacy_id) "
            "VALUES (%s, %s, %s, %s, %s, %s)",
            (
                row["descricao"],
                item.amount,
                item.transaction_date,
                item.category_id,
                item.account_id,
                row["id"],
            ),
        )
    cursor.execute(
        "SELECT COUNT(*) AS n, COALESCE(SUM(amount),0) AS total "
        "FROM transactions WHERE legacy_id IS NOT NULL"
    )
    actual = cursor.fetchone()
    if actual["n"] != len(rows) or actual["total"] != sum((r["valor"] for r in rows), Decimal(0)):
        raise ValueError("Legacy reconciliation failed; import rolled back.")
    _mark(cursor, LEGACY_VERSION)
    logger.info("Legacy import reconciled: %s rows", len(rows))
    return len(rows)


def demo_transactions(categories, accounts):
    """240 reproducible records: 20 per month, January–December 2026, in BRL."""
    expenses = ["Housing", "Utilities", "Food", "Transport", "Health", "Education", "Leisure"]
    for month in range(1, 13):
        for index in range(20):
            income = index < 4
            name = (
                ("Consulting" if index % 2 == 0 else "Product sales")
                if income
                else (expenses[(index - 4) % len(expenses)])
            )
            cents = (
                (180000 + month * 4500 + index * 1275)
                if income
                else (7500 + (index - 4) * 1875 + month * 225)
            )
            yield (
                f"Demo · {name} · {month:02d}/{index + 1:02d}",
                Decimal(cents) / 100,
                date(2026, month, index + 1),
                categories[name],
                accounts["Main checking" if index % 3 else "Cash wallet"],
                f"demo-2026-{month:02d}-{index:02d}",
            )


def initialize(settings=None, *, seed=False, backup_dir=None):
    with connection(settings) as conn:
        cursor = conn.cursor(dictionary=True)
        lock_name = f"financial-v2:{conn.database}"
        cursor.execute("SELECT GET_LOCK(%s, 30) AS acquired", (lock_name,))
        if cursor.fetchone()["acquired"] != 1:
            raise ValueError("Another initialization is running. Try again later.")
        try:
            cursor.execute("SELECT VERSION() AS version")
            if cursor.fetchone()["version"] != "8.0.46":
                raise ValueError("This project requires MySQL 8.0.46.")
            execute_script(cursor, ROOT / "sql/001_schema.sql")
            for name, kind in CATEGORIES:
                cursor.execute(
                    "INSERT INTO categories (name, kind) VALUES (%s, %s) "
                    "ON DUPLICATE KEY UPDATE name = VALUES(name)",
                    (name, kind),
                )
            for name, account_type in [
                ("Legacy account", "checking"),
                ("Main checking", "checking"),
                ("Cash wallet", "cash"),
            ]:
                cursor.execute(
                    "INSERT INTO accounts (name, account_type) VALUES (%s, %s) "
                    "ON DUPLICATE KEY UPDATE name = VALUES(name)",
                    (name, account_type),
                )
            imported = _legacy_import(
                cursor, conn.database, backup_dir or os.getenv("BACKUP_DIR", "backups")
            )
            seeded = 0
            if seed and not _applied(cursor, DEMO_VERSION):
                cursor.execute("SELECT id, name FROM categories")
                categories = {r["name"]: r["id"] for r in cursor.fetchall()}
                cursor.execute("SELECT id, name FROM accounts")
                accounts = {r["name"]: r["id"] for r in cursor.fetchall()}
                records = list(demo_transactions(categories, accounts))
                cursor.executemany(
                    "INSERT INTO transactions "
                    "(description, amount, transaction_date, category_id, "
                    "account_id, demo_key) VALUES (%s,%s,%s,%s,%s,%s)",
                    records,
                )
                _mark(cursor, DEMO_VERSION)
                seeded = len(records)
            conn.commit()
            return {"imported": imported, "seeded": seeded}
        except Exception:
            conn.rollback()
            raise
        finally:
            cursor.execute("SELECT RELEASE_LOCK(%s)", (lock_name,))
            cursor.fetchone()
            cursor.close()
