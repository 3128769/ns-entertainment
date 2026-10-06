"""Append-only result history for check-ins, keyword checks and message checks."""
from __future__ import annotations

import json

from sqlalchemy import text

from nsapp.db import engine, write_transaction
from nsapp.repositories import jobs

KINDS = ("checkin", "monitor", "message")


def append(kind: str, item: dict) -> None:
    with write_transaction() as conn:
        jobs.assert_lease(conn)
        conn.execute(
            text(
                "INSERT INTO task_history(kind,account_id,status,ran_at,payload_json) "
                "VALUES(:kind,:aid,:status,:ran,:payload)"
            ),
            {
                "kind": kind, "aid": item.get("account_id"), "status": item.get("status"),
                "ran": item.get("ran_at"), "payload": json.dumps(item, ensure_ascii=False),
            },
        )


def page(kind: str, limit: int = 100, offset: int = 0, account_id: str | None = None, status: str | None = None) -> dict:
    """Newest first. Keyword/message "nothing new" rows are never shown."""
    clauses = ["kind=:kind"]
    params: dict = {"kind": kind, "limit": limit, "offset": offset}
    if kind != "checkin":
        clauses.append("status <> 'no_match'")
    if account_id:
        clauses.append("account_id=:account")
        params["account"] = account_id
    if status:
        clauses.append("status=:status")
        params["status"] = status
    where = " AND ".join(clauses)
    with engine.connect() as conn:
        total = conn.execute(text(f"SELECT count(*) FROM task_history WHERE {where}"), params).scalar_one()
        rows = conn.execute(
            text(f"SELECT payload_json FROM task_history WHERE {where} ORDER BY id DESC LIMIT :limit OFFSET :offset"),
            params,
        ).fetchall()
    return {"items": [json.loads(row[0]) for row in rows], "total": total}
