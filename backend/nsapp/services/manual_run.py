"""Run a task now from the UI: enqueue a manual job and wait for the Worker's result."""
from __future__ import annotations

import asyncio
import json
import secrets

from nsapp.errors import AppError
from nsapp.logging import correlation_id
from nsapp.repositories import jobs, records

WAIT_SECONDS = 170
_POLL_SECONDS = 0.2
_FLAG_BY_KIND = {"monitor": ("keyword_monitor_enabled", "NODESEEK_MONITOR_DISABLED"),
                 "message": ("message_monitor_enabled", "NODESEEK_MESSAGE_DISABLED")}


async def run_now(account_id: str, kind: str) -> dict:
    account = records.accounts.get(account_id)
    if account is None:
        raise AppError("NODESEEK_ACCOUNT_NOT_FOUND")
    flag = _FLAG_BY_KIND.get(kind)
    if flag and not account.get(flag[0]):
        raise AppError(flag[1])
    if not jobs.state()["ready"]:
        raise AppError("WORKER_UNAVAILABLE")
    job_id = jobs.enqueue(account_id, kind, "manual:" + secrets.token_hex(12), "manual", correlation_id.get())
    loop = asyncio.get_running_loop()
    deadline = loop.time() + WAIT_SECONDS
    while loop.time() < deadline:
        job = jobs.get(job_id)
        if job["status"] in jobs.TERMINAL:
            result = json.loads(job["result_json"])
            if result:
                return result
            return {
                "success": False, "status": job["status"], "message": job["last_error"] or "TASK_FAILED",
                "account_id": account_id, "account_name": account.get("name"), "source": "manual",
                "ran_at": job["updated_at"],
            }
        await asyncio.sleep(_POLL_SECONDS)
    raise AppError("NODESEEK_ACCOUNT_BUSY")
