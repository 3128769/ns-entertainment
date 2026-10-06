"""Table definitions mirroring migration 0001.

Accounts, proxies and bots keep their business fields as one JSON document per
row (``record_json``) next to a few indexed columns. That keeps field additions
migration-free while ids, unique names and revisions stay enforceable in SQL.
Alembic owns creation; ``users``/``sessions`` predate it and are created
idempotently at start-up (see ``repositories.users``).
"""
from __future__ import annotations

from sqlalchemy import (
    CheckConstraint, Column, Index, Integer, MetaData, String, Table, Text,
)

metadata = MetaData()


def _record_table(name: str, *extra) -> Table:
    return Table(
        name, metadata,
        Column("id", String, primary_key=True),
        Column("name", String, nullable=False),
        Column("name_key", String, nullable=False, unique=True),
        Column("record_json", Text, nullable=False),
        Column("revision", Integer, nullable=False, default=0),
        Column("created_at", String, nullable=False),
        Column("updated_at", String, nullable=False),
        *extra,
    )


accounts = _record_table("accounts", CheckConstraint("length(name) > 0", name="account_name_nonempty"))
Index("accounts_name_lookup", accounts.c.name_key)
proxies = _record_table("proxies")
bots = Table(
    "bots", metadata,
    Column("id", String, primary_key=True),
    Column("name", String, nullable=False),
    Column("name_key", String, nullable=False),  # not unique: bots may share a name
    Column("record_json", Text, nullable=False),
    Column("revision", Integer, nullable=False, default=0),
    Column("created_at", String, nullable=False),
    Column("updated_at", String, nullable=False),
)

history = Table(
    "task_history", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("kind", String, nullable=False),
    Column("account_id", String),
    Column("status", String),
    Column("ran_at", String),
    Column("payload_json", Text, nullable=False),
)
Index("history_kind_time", history.c.kind, history.c.ran_at, history.c.id)
Index("history_account_time", history.c.account_id, history.c.ran_at)

jobs = Table(
    "jobs", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("account_id", String, nullable=False),
    Column("job_type", String, nullable=False),
    Column("cycle_key", String, nullable=False),
    Column("status", String, nullable=False),
    Column("attempts", Integer, nullable=False, default=0),
    Column("next_run_at", String, nullable=False),
    Column("lease_until", String),
    Column("run_token", String),
    Column("source", String, nullable=False, default="scheduled"),
    Column("phase", String, nullable=False, default="queued"),
    Column("started_at", String),
    Column("finished_at", String),
    Column("correlation_id", String),
    Column("last_error", String),
    Column("result_json", Text, nullable=False, default="{}"),
    Column("created_at", String, nullable=False),
    Column("updated_at", String, nullable=False),
)
Index("jobs_cycle_unique", jobs.c.account_id, jobs.c.job_type, jobs.c.cycle_key, unique=True)
Index("jobs_due", jobs.c.status, jobs.c.next_run_at)
Index("jobs_account_status", jobs.c.account_id, jobs.c.status)
Index("jobs_running_account", jobs.c.account_id, unique=True, sqlite_where=jobs.c.status == "running")
Index(
    "jobs_one_pending", jobs.c.account_id, jobs.c.job_type, unique=True,
    sqlite_where=jobs.c.status.in_(["queued", "retry_wait"]),
)

worker_state = Table(
    "worker_state", metadata,
    Column("id", Integer, primary_key=True),
    Column("instance_id", String, nullable=False),
    Column("heartbeat_at", String, nullable=False),
    Column("started_at", String, nullable=False),
    Column("concurrency", Integer, nullable=False),
)

notifications = Table(
    "notifications", metadata,
    Column("event_key", String, primary_key=True),
    Column("account_id", String, nullable=False),
    Column("job_id", Integer),
    Column("status", String, nullable=False),
    Column("attempts", Integer, nullable=False, default=0),
    Column("error_code", String),
    Column("message_id", String),
    Column("payload", Text),
    Column("available_at", String),
    Column("updated_at", String, nullable=False),
)

# Not in migration 0001: created idempotently by ``repositories.users.ensure_tables``.
users = Table(
    "users", metadata,
    Column("id", Integer, primary_key=True),
    Column("username", String, nullable=False, unique=True),
    Column("password_hash", String, nullable=False),
    Column("created_at", String, nullable=False),
    info={"managed_outside_alembic": True},
)
sessions = Table(
    "sessions", metadata,
    Column("token_hash", String, primary_key=True),
    Column("username", String, nullable=False),
    Column("expires_at", String, nullable=False),
    Column("created_at", String, nullable=False),
    info={"managed_outside_alembic": True},
)
