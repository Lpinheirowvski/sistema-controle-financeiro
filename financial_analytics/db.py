"""Short-lived connections with commit/rollback and sanitized errors."""

import logging
import os
from contextlib import contextmanager

import mysql.connector

from financial_analytics.config import Settings

logger = logging.getLogger(__name__)


class DatabaseError(RuntimeError):
    """Safe, user-facing database error."""


def configure_logging():
    logging.basicConfig(
        level=os.getenv("LOG_LEVEL", "INFO"),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )


@contextmanager
def connection(settings: Settings | None = None):
    config = settings or Settings.from_env()
    options = dict(
        host=config.host,
        port=config.port,
        database=config.database,
        user=config.user,
        password=config.password,
        connection_timeout=10,
        autocommit=False,
        charset="utf8mb4",
        use_unicode=True,
        sql_mode="STRICT_TRANS_TABLES,NO_ZERO_DATE,NO_ZERO_IN_DATE,"
        "ERROR_FOR_DIVISION_BY_ZERO,NO_ENGINE_SUBSTITUTION,ONLY_FULL_GROUP_BY",
    )
    if config.ssl_ca:
        options.update(ssl_ca=config.ssl_ca, ssl_verify_cert=True, ssl_verify_identity=True)
    conn = None
    try:
        conn = mysql.connector.connect(**options)
        yield conn
        conn.commit()
    except mysql.connector.Error as exc:
        if conn:
            conn.rollback()
        logger.error("MySQL operation failed (code=%s)", exc.errno)
        raise DatabaseError(
            "Database operation failed. Check configuration and server logs."
        ) from None
    except Exception:
        if conn:
            conn.rollback()
        raise
    finally:
        if conn:
            conn.close()
