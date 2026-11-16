#!/usr/bin/env bash
# Runs only when the official MySQL image initializes a NEW data volume.
set -euo pipefail
[[ "$MYSQL_DATABASE" =~ ^[a-zA-Z0-9_]+$ ]] || exit 1
[[ "$DB_USER" =~ ^[a-zA-Z0-9_]+$ ]] || exit 1
# Quote SQL literals with quote doubling under NO_BACKSLASH_ESCAPES.
escaped_password=$(printf '%s' "$DB_PASSWORD" | sed "s/'/''/g")
MYSQL_PWD="$MYSQL_ROOT_PASSWORD" mysql --protocol=socket -uroot <<SQL
SET SESSION sql_mode = 'NO_BACKSLASH_ESCAPES';
CREATE USER IF NOT EXISTS '$DB_USER'@'%' IDENTIFIED BY '$escaped_password';
GRANT SELECT, INSERT, UPDATE, DELETE ON \`$MYSQL_DATABASE\`.* TO '$DB_USER'@'%';
SQL
