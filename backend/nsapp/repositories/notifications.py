"""Telegram delivery ledger: one row per event key, giving at-most-once sends.

``prepare`` stores the message (encrypted); ``claim`` moves it to ``sending``;
``finish`` records the outcome. A crash while ``sending`` becomes ``uncertain``
because Telegram may already have accepted it, and uncertain events are never
re-sent automatically.
"""
from __future__ import annotations

import json

from sqlalchemy import text

from nsapp.db import engine, write_transaction
from nsapp.errors import AppError
from nsapp.repositories import jobs
from nsapp.settings import decrypt_secret, encrypt_secret
from nsapp.timeutil import stamp

MAX_ATTEMPTS = 3


def prepare(event_key: str, account_id: str, job_id: int | None, bot_id: str, chat_id: str, body: str) -> None:
    payload = encrypt_secret(json.dumps({"bot_id": bot_id, "chat_id": chat_id, "body": body}, ensure_ascii=False))
    with write_transaction() as conn:
        jobs.assert_lease(conn)
        conn.execute(
            text(
                "INSERT INTO notifications(event_key,account_id,job_id,status,attempts,payload,available_at,updated_at) "
                "VALUES(:key,:aid,:job,'pending',0,:p,:n,:n) ON CONFLICT(event_key) DO NOTHING"
            ),
            {"key": event_key, "aid": account_id, "job": job_id, "p": payload, "n": stamp()},
        )


def claim(event_key: str) -> dict | None:
    """Reserve the event for sending; None when it was already delivered."""
    with write_transaction() as conn:
        jobs.assert_lease(conn)
        row = conn.execute(
            text("SELECT * FROM notifications WHERE event_key=:key"), {"key": event_key}
        ).mappings().one()
        if row["status"] == "sent":
            return None
        if row["status"] in {"uncertain", "sending"}:
            raise AppError("TELEGRAM_RESULT_UNCERTAIN")
        if row["status"] == "failed" or row["attempts"] >= MAX_ATTEMPTS:
            raise AppError(row["error_code"] or "TELEGRAM_RETRY_EXHAUSTED")
        if row["available_at"] > stamp():
            raise AppError("TELEGRAM_RETRY_WAIT")
        conn.execute(
            text("UPDATE notifications SET status='sending',attempts=attempts+1,updated_at=:n WHERE event_key=:key"),
            {"n": stamp(), "key": event_key},
        )
        return dict(row) | {"attempts": row["attempts"] + 1, "decoded": json.loads(decrypt_secret(row["payload"]))}


def finish(event_key: str, status: str, error: str | None = None, message_id: object = None, attempts: int = 1) -> None:
    with write_transaction() as conn:
        jobs.assert_lease(conn)
        conn.execute(
            text(
                "UPDATE notifications SET status=:s,error_code=:e,message_id=:mid,available_at=:due,updated_at=:n "
                "WHERE event_key=:key"
            ),
            {
                "s": status, "e": error, "mid": str(message_id) if message_id is not None else None,
                "due": stamp(5 * 2 ** (attempts - 1)), "n": stamp(), "key": event_key,
            },
        )


def due() -> list[tuple[str, str, int]]:
    """Events waiting for a retry: (event_key, account_id, attempts)."""
    with engine.connect() as conn:
        rows = conn.execute(
            text(
                "SELECT event_key,account_id,attempts FROM notifications "
                "WHERE status='retry_wait' AND available_at<=:n AND attempts<:max"
            ),
            {"n": stamp(), "max": MAX_ATTEMPTS},
        ).all()
    return [tuple(row) for row in rows]


def recover_sending() -> None:
    """After a Worker restart an in-flight send cannot be proven undelivered."""
    with write_transaction() as conn:
        conn.exec_driver_sql(
            "UPDATE notifications SET status='uncertain',error_code='TELEGRAM_RESULT_UNCERTAIN' WHERE status='sending'"
        )
