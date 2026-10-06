"""Enqueue whatever is due. Runs inside the Worker every few seconds."""
from __future__ import annotations

from nsapp.domain import schedule
from nsapp.repositories import jobs, records


def enqueue_due(now=None) -> int:
    requests = schedule.plan_jobs(records.accounts.all(), now or schedule.local_now())
    for request in requests:
        jobs.enqueue(request.account_id, request.kind, request.cycle_key)
    return len(requests)
