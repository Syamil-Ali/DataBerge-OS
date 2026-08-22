from __future__ import annotations

import re
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from threading import Lock
from typing import Any, Iterator

from app import settings

_pool = None
_pool_lock = Lock()


def uses_postgres(db_path: Path | None = None) -> bool:
    return db_path is None and bool(settings.DATABASE_URL)


class PostgresConnection:
    def __init__(self, connection: Any) -> None:
        self.connection = connection

    @staticmethod
    def _sql(statement: str) -> str:
        converted = statement.replace("?", "%s")
        converted = re.sub(
            r"max\(0,\s*storage_used\s*\+\s*%s\)",
            "greatest(0, storage_used + %s)",
            converted,
            flags=re.I,
        )
        return converted

    def execute(self, statement: str, params: Any = None):
        return self.connection.execute(self._sql(statement), params or ())

    def executescript(self, script: str) -> None:
        for statement in script.split(";"):
            if statement.strip():
                self.connection.execute(statement)

    def commit(self) -> None:
        self.connection.commit()

    def rollback(self) -> None:
        self.connection.rollback()

    def close(self) -> None:
        return None


def _postgres_pool():
    global _pool
    with _pool_lock:
        if _pool is None:
            from psycopg.rows import dict_row
            from psycopg_pool import ConnectionPool

            _pool = ConnectionPool(
                conninfo=settings.DATABASE_URL,
                min_size=settings.DATABASE_POOL_MIN,
                max_size=settings.DATABASE_POOL_MAX,
                kwargs={"row_factory": dict_row},
                open=True,
            )
    return _pool


@contextmanager
def connect(db_path: Path | None = None) -> Iterator[Any]:
    if uses_postgres(db_path):
        pool = _postgres_pool()
        with pool.connection() as raw:
            connection = PostgresConnection(raw)
            try:
                yield connection
                connection.commit()
            except Exception:
                connection.rollback()
                raise
        return

    connection = sqlite3.connect(db_path or settings.DB_PATH, timeout=30)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA busy_timeout = 30000")
    connection.execute("PRAGMA journal_mode = WAL")
    connection.execute("PRAGMA synchronous = NORMAL")
    try:
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def close_pool() -> None:
    global _pool
    with _pool_lock:
        pool, _pool = _pool, None
    if pool is not None:
        pool.close()
