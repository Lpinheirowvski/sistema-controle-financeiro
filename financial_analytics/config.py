"""Environment configuration. Passwords never appear in repr or logs."""

import os
import re
from dataclasses import dataclass, field

from dotenv import load_dotenv


@dataclass(frozen=True)
class Settings:
    host: str
    port: int
    database: str
    user: str
    password: str = field(repr=False)
    ssl_ca: str | None = None

    @classmethod
    def from_env(cls):
        load_dotenv()
        required = ("DB_HOST", "DB_NAME", "DB_USER", "DB_PASSWORD")
        if any(not os.getenv(name) for name in required):
            raise ValueError("Set DB_HOST, DB_NAME, DB_USER and DB_PASSWORD in the environment.")
        database = os.environ["DB_NAME"]
        if not re.fullmatch(r"[a-zA-Z0-9_]+", database):
            raise ValueError("DB_NAME must contain only letters, digits and underscores.")
        port = int(os.getenv("DB_PORT", "3306"))
        if not 1 <= port <= 65535:
            raise ValueError("DB_PORT must be between 1 and 65535.")
        return cls(
            os.environ["DB_HOST"],
            port,
            database,
            os.environ["DB_USER"],
            os.environ["DB_PASSWORD"],
            os.getenv("DB_SSL_CA") or None,
        )
