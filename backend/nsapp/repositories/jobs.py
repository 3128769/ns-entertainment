"""Durable job queue with leases.

Life cycle: ``queued`` -> ``running`` (leased, ``run_token`` identifies the
claimant) -> ``succeeded | failed | uncertain | canceled``; ``retry_wait`` is a
queued job with a back-off. A job whose Worker dies is recovered when its lease
expires: ``uncertain`` if it was inside an external write (the request may have
gone through), otherwise it is simply re-queued.
"""
from __future__ import annotations

import json
import re
import secrets

from sqlalchemy import Connection, text

from nsapp.context import current_job
from nsapp.db import engine, write_transaction
from nsapp.errors import AppError
from nsapp.timeutil import stamp

TERMINAL = {"succeeded", "failed", "uncertain", "canceled"}
PENDING = ("queued", "retry_wait")
MAX_QUEUED = 1000
MAX_ATTEMPTS = 3
LEASE_SECONDS = 90
HEARTBEAT_TTL = 20
RETENTION_SECONDS = 7 * 86400
_SAFE_CODE = re.compile(r"[A-Z][A-Z0-9_]{1,100}")


def assert_lease(conn: Connection) -> None:
    """Raise TASK_LEASE_LOST unless the current job still owns a live lease."""
    job = current_job.get()
    if not job:
        return
    owned = conn.execute(
        text("SELECT id FROM jobs WHERE id=:id AND status='running' AND run_token=:token AND lease_until>:now"),
        {"id": job["id"], "token": job["run_token"], "now": stamp()},
    ).first()
    if not owned:
        raise AppError("TASK_LEASE_LOST")


def enqueue(account_id: str, kind: str, cycle: str, source: str = "scheduled", correlation_id: str | None = None) -> int:
    """Queue a job; returns the existing id when the cycle or an equal pending job exists."""
    now = stamp()
    with write_transaction() as conn:
        same_cycle = conn.execute(
            text("SELECT id FROM jobs WHERE account_id=:a AND job_type=:k AND cycle_key=:c"),
            {"a": account_id, "k": kind, "c": cycle},
        ).first()
        if same_cycle:
            return same_cycle[0]
        pending = conn.execute(
            text("SELECT id FROM jobs WHERE account_id=:a AND job_type=:k AND status IN ('queued','retry_wait')"),
            {"a": account_id, "k": kind},
        ).first()
        if pending:
            return pending[0]
        queued = conn.exec_driver_sql("SELECT count(*) FROM jobs WHERE status IN ('queued','retry_wait')").scalar_one()
        if queued >= MAX_QUEUED:
            raise AppError("TASK_QUEUE_FULL")
        conn.execute(
            text(
                "INSERT INTO jobs(account_id,job_type,cycle_key,source,status,phase,attempts,next_run_at,"
                "result_json,created_at,updated_at,correlation_id) "
                "VALUES(:a,:k,:c,:s,'queued','queued',0,:n,'{}',:n,:n,:cid)"
            ),
            {"a": account_id, "k": kind, "c": cycle, "s": source, "n": now, "cid": correlation_id or secrets.token_hex(12)},
        )
        return conn.exec_driver_sql("SELECT last_insert_rowid()").scalar_one()


def get(job_id: int) -> dict | None:
    with engine.connect() as conn:
        row = conn.execute(text("SELECT * FROM jobs WHERE id=:id"), {"id": job_id}).mappings().first()
    return dict(row) if row else None


def claim() -> dict | None:
    """Lease the next runnable job: manual first, then check-ins, one running job per account."""
    now = stamp()
    token = secrets.token_hex(16)
    with write_transaction() as conn:
        row = conn.execute(
            text(
                """SELECT * FROM jobs AS j
                   WHERE j.status IN ('queued','retry_wait') AND j.next_run_at<=:now
                     AND NOT EXISTS (SELECT 1 FROM jobs AS active
                                     WHERE active.account_id=j.account_id AND active.status='running')
                   ORDER BY CASE WHEN source='manual' THEN 0 WHEN job_type='sign' THEN 1 ELSE 2 END,
                            next_run_at, id
                   LIMIT 1"""
            ),
            {"now": now},
        ).mappings().first()
        if not row:
            return None
        conn.execute(
            text(
                "UPDATE jobs SET status='running',phase='reading',attempts=attempts+1,lease_until=:lease,"
                "run_token=:token,started_at=:now,updated_at=:now WHERE id=:id"
            ),
            {"lease": stamp(LEASE_SECONDS), "token": token, "now": now, "id": row["id"]},
        )
        claimed = dict(row)
        claimed.update(attempts=row["attempts"] + 1, run_token=token, status="running")
        return claimed


def set_phase(job: dict, phase: str) -> None:
    """Mark ``reading`` or ``external_write``; fails if the lease was lost."""
    with write_transaction() as conn:
        updated = conn.execute(
            text(
                "UPDATE jobs SET phase=:phase,updated_at=:now "
                "WHERE id=:id AND status='running' AND run_token=:token AND lease_until>:now"
            ),
            {"phase": phase, "now": stamp(), "id": job["id"], "token": job["run_token"]},
        ).rowcount
        if updated != 1:
            raise AppError("TASK_LEASE_LOST")


def renew(job: dict) -> bool:
    with write_transaction() as conn:
        return conn.execute(
            text("UPDATE jobs SET lease_until=:lease WHERE id=:id AND status='running' AND run_token=:token"),
            {"lease": stamp(LEASE_SECONDS), "id": job["id"], "token": job["run_token"]},
        ).rowcount == 1


def finish(job: dict, result: dict, status: str | None = None, error: str | None = None) -> None:
    status = status or ("succeeded" if result.get("success") else "failed")
    with write_transaction() as conn:
        conn.execute(
            text(
                "UPDATE jobs SET status=:status,finished_at=:now,updated_at=:now,lease_until=NULL,"
                "result_json=:result,last_error=:error WHERE id=:id AND status='running' AND run_token=:token"
            ),
            {
                "status": status, "now": stamp(), "result": json.dumps(result, ensure_ascii=False),
                "error": error or (None if result.get("success") else result.get("message")),
                "id": job["id"], "token": job["run_token"],
            },
        )


def retry(job: dict, error: str) -> None:
    """Back off (5s, 10s, ...) and re-queue, up to MAX_ATTEMPTS total attempts.

    Only handlers whose requests are safe to repeat (reads) use this path.
    """
    with write_transaction() as conn:
        superseded = conn.execute(
            text("SELECT id FROM jobs WHERE account_id=:a AND job_type=:k AND status IN ('queued','retry_wait')"),
            {"a": job["account_id"], "k": job["job_type"]},
        ).first()
        status = "failed" if superseded or job["attempts"] >= MAX_ATTEMPTS else "retry_wait"
        conn.execute(
            text(
                "UPDATE jobs SET status=:s,phase='queued',lease_until=NULL,next_run_at=:due,last_error=:error,"
                "updated_at=:now WHERE id=:id AND run_token=:token"
            ),
            {"s": status, "due": stamp(5 * 2 ** (job["attempts"] - 1)), "error": error, "now": stamp(),
             "id": job["id"], "token": job["run_token"]},
        )


def recover() -> int:
    """Settle jobs whose lease expired (their Worker died). Returns how many were touched."""
    now = stamp()
    with write_transaction() as conn:
        expired = conn.execute(
            text("SELECT * FROM jobs WHERE status='running' AND lease_until<:now"), {"now": now}
        ).mappings().all()
        for row in expired:
            if row["phase"] == "external_write":
                status = "uncertain"
            elif row["attempts"] >= MAX_ATTEMPTS:
                status = "failed"
            else:
                status = "queued"
            superseded = conn.execute(
                text("SELECT id FROM jobs WHERE account_id=:a AND job_type=:k AND status IN ('queued','retry_wait')"),
                {"a": row["account_id"], "k": row["job_type"]},
            ).first()
            if superseded and status == "queued":
                status = "canceled"
            conn.execute(
                text(
                    "UPDATE jobs SET status=:s,run_token=NULL,lease_until=NULL,last_error='WORKER_INTERRUPTED',"
                    "updated_at=:now,next_run_at=:now WHERE id=:id"
                ),
                {"s": status, "now": now, "id": row["id"]},
            )
    return len(expired)


def prune() -> int:
    """Drop old finished jobs (never queued, running or uncertain ones), at most 1000 per call."""
    with write_transaction() as conn:
        return conn.execute(
            text(
                "DELETE FROM jobs WHERE id IN (SELECT id FROM jobs "
                "WHERE status IN ('succeeded','failed','canceled') AND updated_at<:cutoff ORDER BY id LIMIT 1000)"
            ),
            {"cutoff": stamp(-RETENTION_SECONDS)},
        ).rowcount


def heartbeat(instance: str, started: str, concurrency: int) -> None:
    """Record liveness; refuses while a different Worker instance is still alive."""
    with write_transaction() as conn:
        row = conn.exec_driver_sql("SELECT instance_id,heartbeat_at FROM worker_state WHERE id=1").first()
        if row and row[0] != instance and row[1] > stamp(-HEARTBEAT_TTL):
            raise RuntimeError("ANOTHER_WORKER_ACTIVE")
        conn.execute(
            text(
                "INSERT INTO worker_state(id,instance_id,heartbeat_at,started_at,concurrency) "
                "VALUES(1,:i,:h,:s,:c) ON CONFLICT(id) DO UPDATE SET instance_id=excluded.instance_id,"
                "heartbeat_at=excluded.heartbeat_at,started_at=excluded.started_at,concurrency=excluded.concurrency"
            ),
            {"i": instance, "h": stamp(), "s": started, "c": concurrency},
        )


def _public_error(value: object) -> object:
    """Only stable codes leave this module; free text is replaced."""
    if not value or _SAFE_CODE.fullmatch(str(value)):
        return value
    return "BUSINESS_REQUEST_FAILED"


def state() -> dict:
    """Queue and Worker health for readiness checks and the admin UI."""
    with engine.connect() as conn:
        worker = conn.exec_driver_sql("SELECT heartbeat_at,concurrency FROM worker_state WHERE id=1").first()
        counts = dict(conn.exec_driver_sql("SELECT status,count(*) FROM jobs GROUP BY status").all())
        recent = conn.exec_driver_sql(
            "SELECT id,account_id,job_type,status,attempts,started_at,finished_at,last_error,correlation_id "
            "FROM jobs ORDER BY id DESC LIMIT 20"
        ).mappings().all()
        oldest = conn.exec_driver_sql(
            "SELECT min(created_at) FROM jobs WHERE status IN ('queued','retry_wait')"
        ).scalar()
    return {
        "ready": bool(worker and worker[0] > stamp(-HEARTBEAT_TTL)),
        "heartbeat_at": worker[0] if worker else None,
        "concurrency": worker[1] if worker else None,
        "counts": counts,
        "oldest_queued_at": oldest,
        "recent_jobs": [
            {key: (_public_error(value) if key == "last_error" else value) for key, value in dict(row).items()}
            for row in recent
        ],
    }
