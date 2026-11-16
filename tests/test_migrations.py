import json
from decimal import Decimal

import pytest

from financial_analytics.db import connection
from financial_analytics.migrations import ROOT, execute_script, initialize

pytestmark = pytest.mark.integration


def legacy_source(settings, invalid=False):
    with connection(settings) as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                "CREATE TABLE transacoes (id INT PRIMARY KEY, descricao VARCHAR(100), "
                "tipo VARCHAR(20), valor DECIMAL(10,2), data_transacao DATE)"
            )
            cursor.execute(
                "INSERT INTO transacoes VALUES "
                "(1,'venda notebook','receita',2500,'2026-10-20'),"
                "(2,'conta de luz','despesa',350,'2026-10-21'),"
                "(3,'manutencao de computador','receita',800,'2026-10-22'),"
                "(4,'aluguel','despesa',1200,'2026-10-23'),"
                "(5,'venda de monitor','receita',950,'2026-10-24')"
            )
            if invalid:
                cursor.execute("UPDATE transacoes SET valor = -1 WHERE id = 5")


def test_legacy_preserved_and_init_idempotent(mysql_settings, tmp_path):
    legacy_source(mysql_settings)
    assert initialize(mysql_settings, seed=True, backup_dir=tmp_path) == {
        "imported": 5,
        "seeded": 240,
    }
    assert initialize(mysql_settings, seed=True, backup_dir=tmp_path) == {
        "imported": 0,
        "seeded": 0,
    }
    with connection(mysql_settings) as conn:
        with conn.cursor(dictionary=True) as cursor:
            cursor.execute("SELECT COUNT(*) AS n FROM transactions")
            assert cursor.fetchone()["n"] == 245
            cursor.execute("SELECT COUNT(*) AS n, SUM(valor) AS total FROM transacoes")
            assert cursor.fetchone() == {"n": 5, "total": Decimal("5800.00")}
            cursor.execute(
                "SELECT SUM(signed_amount) AS net FROM v_transaction_details "
                "WHERE legacy_id IS NOT NULL"
            )
            assert cursor.fetchone()["net"] == Decimal("2700.00")
            cursor.execute(
                "SELECT COUNT(DISTINCT MONTH(transaction_date)) AS months "
                "FROM transactions WHERE demo_key IS NOT NULL"
            )
            assert cursor.fetchone()["months"] == 12
    backups = list(tmp_path.glob("*.json"))
    assert len(backups) == 1
    assert len(json.loads(backups[0].read_text())["rows"]) == 5
    assert backups[0].stat().st_mode & 0o777 == 0o600


def test_invalid_legacy_rolls_back(mysql_settings, tmp_path):
    legacy_source(mysql_settings, invalid=True)
    with pytest.raises(ValueError):
        initialize(mysql_settings, seed=True, backup_dir=tmp_path)
    with connection(mysql_settings) as conn:
        with conn.cursor() as cursor:
            cursor.execute("SELECT COUNT(*) FROM transactions")
            assert cursor.fetchone()[0] == 0
            cursor.execute("SELECT COUNT(*) FROM schema_migrations")
            assert cursor.fetchone()[0] == 0
            cursor.execute("SELECT COUNT(*) FROM transacoes")
            assert cursor.fetchone()[0] == 5
    assert len(list(tmp_path.glob("*.json"))) == 1


def test_all_report_queries_execute_in_mysql(mysql_settings):
    initialize(mysql_settings, seed=True)
    with connection(mysql_settings) as conn:
        with conn.cursor() as cursor:
            # The standalone script targets the production schema; tests use a new database.
            source = (ROOT / "03_relatorios.sql").read_text()
            source = source.replace("USE controle_financeiro;", "")
            for statement in source.split(";"):
                if statement.strip():
                    cursor.execute(statement)
                    assert cursor.fetchall()
            execute_script(cursor, ROOT / "sql/001_schema.sql")


def test_backup_failure_prevents_import(mysql_settings, tmp_path):
    legacy_source(mysql_settings)
    not_a_directory = tmp_path / "blocked"
    not_a_directory.write_text("existing file")
    with pytest.raises(OSError):
        initialize(mysql_settings, seed=True, backup_dir=not_a_directory)
    with connection(mysql_settings) as conn:
        with conn.cursor() as cursor:
            cursor.execute("SELECT COUNT(*) FROM transactions")
            assert cursor.fetchone()[0] == 0
            cursor.execute("SELECT COUNT(*) FROM transacoes")
            assert cursor.fetchone()[0] == 5


def test_concurrent_initializers_do_not_duplicate_data(mysql_settings, tmp_path):
    from concurrent.futures import ThreadPoolExecutor

    legacy_source(mysql_settings)
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(
            pool.map(lambda _: initialize(mysql_settings, seed=True, backup_dir=tmp_path), range(2))
        )
    assert sum(result["imported"] for result in results) == 5
    assert sum(result["seeded"] for result in results) == 240
    with connection(mysql_settings) as conn:
        with conn.cursor() as cursor:
            cursor.execute("SELECT COUNT(*) FROM transactions")
            assert cursor.fetchone()[0] == 245


def test_duplicate_legacy_business_values_are_preserved(mysql_settings, tmp_path):
    legacy_source(mysql_settings)
    with connection(mysql_settings) as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                "INSERT INTO transacoes "
                "SELECT 6, descricao, tipo, valor, data_transacao "
                "FROM transacoes WHERE id=1"
            )
    assert initialize(mysql_settings, backup_dir=tmp_path)["imported"] == 6
    with connection(mysql_settings) as conn:
        with conn.cursor() as cursor:
            cursor.execute("SELECT COUNT(*), SUM(amount) FROM transactions")
            assert cursor.fetchone() == (6, Decimal("8300.00"))
