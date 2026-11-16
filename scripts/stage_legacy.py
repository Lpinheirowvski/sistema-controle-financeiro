"""Copy transacoes from an isolated Docker container into an empty Compose database.

The source is read through docker exec; its network and credentials stay unchanged.
No existing destination legacy table is overwritten. Run before the v2 initializer.
"""

import argparse
import hashlib
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--source-container", default="financeiro-mysql")
parser.add_argument("--source-database", default="controle_financeiro")
args = parser.parse_args()
source_env = dict(os.environ)
source_env["MYSQL_PWD"] = os.getenv("LEGACY_MYSQL_PASSWORD", "")
source = ["docker", "exec", "-e", "MYSQL_PWD", args.source_container]
target = [
    "docker",
    "compose",
    "exec",
    "-T",
    "db",
    "sh",
    "-c",
    'MYSQL_PWD="$MYSQL_ROOT_PASSWORD" mysql -uroot "$MYSQL_DATABASE"',
]
check = subprocess.check_output(
    target,
    input=b"SELECT COUNT(*) FROM information_schema.tables WHERE "
    b"table_schema=DATABASE() AND table_name='transacoes';\n",
)
if check.decode().splitlines()[-1] != "0":
    raise SystemExit("Destination transacoes already exists; refusing to overwrite it.")
backup_dir = Path("backups")
backup_dir.mkdir(mode=0o700, exist_ok=True)
path = backup_dir / f"legacy-source-{datetime.now(timezone.utc):%Y%m%dT%H%M%S%fZ}.sql"
fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
with os.fdopen(fd, "wb") as handle:
    subprocess.run(
        source
        + [
            "mysqldump",
            "-uroot",
            "--single-transaction",
            "--no-tablespaces",
            "--skip-add-drop-table",
            args.source_database,
            "transacoes",
        ],
        env=source_env,
        stdout=handle,
        check=True,
    )
payload = path.read_bytes()
if not payload.strip():
    raise SystemExit("Source backup is empty; destination was not changed.")
subprocess.run(target, input=payload, check=True)
print(f"Legacy source copied. Private backup: {path}")
print(f"SHA256: {hashlib.sha256(payload).hexdigest()}")
print("Now run: docker compose run --rm migrate python -m financial_analytics.cli init --seed")
