"""SQLite engine and short write transactions.

Network I/O never happens inside ``write_transaction``; it takes SQLite's write
lock up front (``BEGIN IMMEDIATE``) so Web and Worker queue instead of failing.
"""
from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import Connection, create_engine, event

from nsapp.settings import DB_PATH, ensure_dirs

SCHEMA_VERSION = "0001"

engine = create_engine(
    f"sqlite:///{DB_PATH}",
    connect_args={"check_same_thread": False, "timeout": 30},
    pool_pre_ping=True,
)


@event.listens_for(engine, "connect")
def _connection_settings(connection, _record) -> None:
    connection.execute("PRAGMA foreign_keys=ON")
    connection.execute("PRAGMA busy_timeout=30000")


@contextmanager
def write_transaction() -> Iterator[Connection]:
    ensure_dirs()
    with engine.connect() as conn:
        conn.exec_driver_sql("BEGIN IMMEDIATE")
        try:
            yield conn
            conn.commit()
        except BaseException:
            conn.rollback()
            raise


def assert_schema() -> None:
    """Refuse to run against a database that has not been migrated explicitly."""
    with engine.connect() as conn:
        version = conn.exec_driver_sql("SELECT version_num FROM alembic_version").scalar_one()
    if version != SCHEMA_VERSION:
        raise RuntimeError("DATABASE_MIGRATION_REQUIRED")
