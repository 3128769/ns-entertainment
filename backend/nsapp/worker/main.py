"""Worker process: ``python -m nsapp.worker.main``.

Exactly one Worker runs per instance. It claims jobs under a lease, runs up to
``NS_JOB_CONCURRENCY`` of them concurrently (never two for one account), renews
leases while they run, and settles everything that was interrupted.
"""
from __future__ import annotations

import asyncio
import secrets
import signal
import time

from nsapp import VERSION
from nsapp.context import current_job
from nsapp.db import assert_schema
from nsapp.errors import AppError
from nsapp.logging import correlation_id, event
from nsapp.repositories import jobs, notifications, records
from nsapp.services.outbox import deliver
from nsapp.settings import env_flag, job_concurrency
from nsapp.tasks import HANDLERS
from nsapp.worker.scheduler import enqueue_due

JOB_TIMEOUT = 150
# Failures of read-only requests that are safe to repeat.
RETRYABLE = {
    "NODESEEK_CONNECT_FAILED", "NODESEEK_MONITOR_FAILED", "NODESEEK_FEED_INVALID",
    "NODESEEK_MESSAGE_FAILED", "NODESEEK_OFFLINE_FAILED",
}
_REPORTABLE = ("TASK_", "NODESEEK_", "TELEGRAM_", "BOT_")


async def _run_job(job: dict) -> dict:
    if job["job_type"] == "notify":
        event_key = job["cycle_key"].rsplit(":", 1)[0]
        await asyncio.wait_for(deliver(event_key), JOB_TIMEOUT)
        return {"success": True, "status": "notified", "message": "TELEGRAM_SENT"}
    if job["source"] == "scheduled":
        record = records.accounts.get(job["account_id"]) or {}
        enabled = record.get("offline_notify_enabled") if job["job_type"] == "offline" else record.get("enabled")
        if not enabled:
            raise AppError("TASK_DISABLED")
    handler = HANDLERS[job["job_type"]]
    return await asyncio.wait_for(handler(job["account_id"], job["source"]), JOB_TIMEOUT)


async def execute(job: dict) -> None:
    """Run one claimed job and settle it (succeeded, failed, uncertain or re-queued)."""
    job_token = current_job.set(job)
    cid_token = correlation_id.set(job["correlation_id"])
    started = time.monotonic()
    event("task_started", job_id=job["id"], account_id=job["account_id"], kind=job["job_type"], attempts=job["attempts"])
    try:
        result = await _run_job(job)
        if result.get("message") in RETRYABLE and job["attempts"] < jobs.MAX_ATTEMPTS:
            jobs.retry(job, result["message"])
        else:
            ambiguous = result.get("status") == "uncertain" or result.get("message") == "TELEGRAM_RESULT_UNCERTAIN"
            jobs.finish(job, result, "uncertain" if ambiguous else None)
    except asyncio.CancelledError:
        row = jobs.get(job["id"])
        if row["phase"] == "external_write":
            jobs.finish(job, {"success": False, "status": "uncertain", "message": "WORKER_INTERRUPTED"}, "uncertain")
        else:
            jobs.retry(job, "WORKER_INTERRUPTED")
        raise
    except Exception as exc:
        code = exc.code if isinstance(exc, AppError) and exc.code.startswith(_REPORTABLE) else "TASK_EXECUTION_FAILED"
        row = jobs.get(job["id"])
        in_write = bool(row and row["phase"] == "external_write")
        status = "uncertain" if code == "TELEGRAM_RESULT_UNCERTAIN" or in_write else "failed"
        jobs.finish(job, {"success": False, "status": status, "message": code}, status, code)
    finally:
        row = jobs.get(job["id"])
        event(
            "task_finished", job_id=job["id"], account_id=job["account_id"], kind=job["job_type"],
            status=row["status"], elapsed_ms=int((time.monotonic() - started) * 1000), error_code=row["last_error"],
        )
        current_job.reset(job_token)
        correlation_id.reset(cid_token)


async def main() -> None:
    assert_schema()
    concurrency = job_concurrency()
    instance, started, stop = secrets.token_hex(16), jobs.stamp(), asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, stop.set)

    # A replacement Worker waits out the previous one's heartbeat instead of stealing live work.
    for _ in range(25):
        try:
            jobs.heartbeat(instance, started, concurrency)
            break
        except RuntimeError:
            await asyncio.sleep(1)
    else:
        raise RuntimeError("ANOTHER_WORKER_ACTIVE")
    jobs.recover()
    notifications.recover_sending()
    event("worker_started", concurrency=concurrency, version=VERSION)

    active: dict[int, tuple[dict, asyncio.Task]] = {}
    next_schedule = next_heartbeat = next_prune = 0.0
    while not stop.is_set():
        now = time.monotonic()
        if now >= next_prune:
            jobs.prune()
            next_prune = now + 60
        if now >= next_heartbeat:
            jobs.heartbeat(instance, started, concurrency)
            for running, _task in active.values():
                jobs.renew(running)
            jobs.recover()
            next_heartbeat = now + 5
        if env_flag("NS_SCHEDULER_ENABLED", "1") and now >= next_schedule:
            try:
                enqueue_due()
                for key, account_id, attempts in notifications.due():
                    jobs.enqueue(account_id, "notify", f"{key}:{attempts}")
            except Exception:
                event("scheduler_error", error_code="SCHEDULER_FAILED")
            next_schedule = now + 10
        active = {job_id: pair for job_id, pair in active.items() if not pair[1].done()}
        while len(active) < concurrency:
            job = jobs.claim()
            if job is None:
                break
            active[job["id"]] = (job, asyncio.create_task(execute(job)))
        try:
            await asyncio.wait_for(stop.wait(), timeout=0.25)
        except asyncio.TimeoutError:
            pass

    # Stop claiming; give running work 30s, then mark anything mid-write as uncertain.
    pending = [task for _job, task in active.values()]
    if pending:
        _done, unfinished = await asyncio.wait(pending, timeout=30)
        for task in unfinished:
            task.cancel()
        await asyncio.gather(*pending, return_exceptions=True)
    event("worker_stopped")


if __name__ == "__main__":
    asyncio.run(main())
