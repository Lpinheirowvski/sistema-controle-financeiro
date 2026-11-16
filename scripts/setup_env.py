"""Create private local credentials once, without overwriting an existing .env."""

import os
import secrets
from pathlib import Path

path = Path(".env")
content = (
    f"MYSQL_ROOT_PASSWORD={secrets.token_urlsafe(36)}\n"
    f"DB_MIGRATION_PASSWORD={secrets.token_urlsafe(36)}\n"
    f"DB_PASSWORD={secrets.token_urlsafe(36)}\n"
    "DB_HOST=127.0.0.1\nDB_PORT=3306\nDB_NAME=controle_financeiro\n"
    "DB_USER=financial_app\nDB_SSL_CA=\nLOG_LEVEL=INFO\nBACKUP_DIR=backups\n"
)
try:
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
except FileExistsError:
    raise SystemExit(".env already exists; no changes made.") from None
with os.fdopen(fd, "w") as handle:
    handle.write(content)
print("Created .env with random credentials (permissions 0600).")
