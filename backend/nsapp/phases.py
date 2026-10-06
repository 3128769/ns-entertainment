"""Mark where a job is relative to an external write.

``external_write`` means "a request that may change the outside world (a check-in,
a Telegram message) is about to be sent". If the Worker dies in that phase the job
is settled as ``uncertain`` instead of being re-run.
"""
from __future__ import annotations

from nsapp.context import current_job
from nsapp.repositories import jobs


def enter_external_write() -> None:
    job = current_job.get()
    if job:
        jobs.set_phase(job, "external_write")


def leave_external_write() -> None:
    job = current_job.get()
    if job:
        jobs.set_phase(job, "reading")
