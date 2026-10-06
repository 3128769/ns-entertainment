import asyncio
import json
import time

import pytest

import nsapp.worker.main as worker
from nsapp.repositories import jobs, records
from nsapp.tasks import HANDLERS
from nsapp.worker.main import execute


async def drain(concurrency=4):
    while batch := [job for _ in range(concurrency) if (job := jobs.claim())]:
        await asyncio.gather(*(execute(job) for job in batch))


def test_slow_account_does_not_block_others(account, monkeypatch):
    from tests.helpers import fake_checkin, json_response
    from nsapp.tasks import checkin
    from nsapp.services import accounts

    async def case():
        slow, fast = account("Slow")["id"], account("Fast")["id"]
        started, release = asyncio.Event(), asyncio.Event()

        async def respond():
            return json_response(success=True, message="今天的签到收益是4个鸡腿")

        async def checkin_request(self, *, random_reward):
            if self._cookie == "session=slow":
                started.set()
                await release.wait()
            return await respond()

        from nsapp.integrations.nodeseek import NodeSeek
        monkeypatch.setattr(NodeSeek, "checkin", checkin_request)
        accounts.update(slow, {"cookie": "session=slow"})
        task = asyncio.create_task(checkin.run(slow))
        await started.wait()
        assert (await asyncio.wait_for(checkin.run(fast), 0.5))["success"]
        accounts.update(slow, {"name": "User edit"})  # editing is not blocked by the running task
        release.set()
        await task
        assert records.accounts.get(slow)["name"] == "User edit"
        assert records.accounts.get(slow)["last_status"] == "success"

    asyncio.run(case())


def test_concurrency_never_exceeds_the_limit(monkeypatch):
    async def case():
        current = peak = 0

        async def handler(account_id, source):
            nonlocal current, peak
            current += 1
            peak = max(peak, current)
            await asyncio.sleep(0.02)
            current -= 1
            return {"success": True, "status": "success"}

        monkeypatch.setitem(HANDLERS, "sign", handler)
        for i in range(12):
            jobs.enqueue(str(i), "sign", "1", "manual")
        await drain()
        assert peak == 4 and jobs.state()["counts"]["succeeded"] == 12

    asyncio.run(case())


def test_the_worker_loop_runs_and_stops_cleanly(monkeypatch):
    async def case():
        active = peak = done = 0
        stops = []

        async def handler(account_id, source):
            nonlocal active, peak, done
            active += 1
            peak = max(peak, active)
            await asyncio.sleep(0.1)
            active -= 1
            done += 1
            if done == 12:
                stops[0]()
            return {"success": True, "status": "success"}

        monkeypatch.setitem(HANDLERS, "sign", handler)
        monkeypatch.setattr(asyncio.get_running_loop(), "add_signal_handler", lambda sig, callback: stops.append(callback))
        for i in range(12):
            jobs.enqueue(str(i), "sign", "cycle", "manual")
        await asyncio.wait_for(worker.main(), 5)
        assert done == 12 and peak == 4 and jobs.state()["counts"] == {"succeeded": 12}

    asyncio.run(case())


def test_transient_read_failures_are_retried_then_reported(monkeypatch):
    async def handler(account_id, source):
        return {"success": False, "status": "failed", "message": "NODESEEK_FEED_INVALID"}

    monkeypatch.setitem(HANDLERS, "monitor", handler)
    job_id = jobs.enqueue("a", "monitor", "1", "manual")
    asyncio.run(execute(jobs.claim()))
    assert jobs.get(job_id)["status"] == "retry_wait"


def test_an_error_inside_a_write_is_uncertain_not_failed(monkeypatch):
    async def handler(account_id, source):
        from nsapp import phases
        phases.enter_external_write()
        raise RuntimeError("boom")

    monkeypatch.setitem(HANDLERS, "sign", handler)
    job_id = jobs.enqueue("a", "sign", "1", "manual")
    asyncio.run(execute(jobs.claim()))
    job = jobs.get(job_id)
    assert job["status"] == "uncertain" and job["last_error"] == "TASK_EXECUTION_FAILED"
    assert json.loads(job["result_json"])["status"] == "uncertain"


def test_scheduled_jobs_for_disabled_accounts_are_skipped(account):
    a = account(enabled=False)["id"]
    job_id = jobs.enqueue(a, "sign", "1")
    asyncio.run(execute(jobs.claim()))
    assert jobs.get(job_id)["last_error"] == "TASK_DISABLED"


def test_capacity_100_accounts_400_tasks(monkeypatch):
    """100 accounts x 4 cycles with a 50 ms fake request: bounded concurrency, nothing lost."""
    async def case():
        active = peak = done = 0

        async def handler(account_id, source):
            nonlocal active, peak, done
            active += 1
            peak = max(peak, active)
            await asyncio.sleep(0.05)
            records.accounts.patch(account_id, {"last_status": "success"})
            active -= 1
            done += 1
            return {"success": True, "status": "success"}

        for i in range(100):
            records.accounts.patch(str(i), {"name": str(i), "created_at": "t", "updated_at": "t"}, create=True)
        monkeypatch.setitem(HANDLERS, "sign", handler)
        started = time.monotonic()
        for cycle in range(4):
            for i in range(100):
                jobs.enqueue(str(i), "sign", str(cycle), "manual")
            await drain()
        assert done == 400 and peak == 4 and jobs.state()["counts"] == {"succeeded": 400}
        assert time.monotonic() - started < 60

    asyncio.run(case())
