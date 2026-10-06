import pytest
from sqlalchemy import text

from nsapp.context import current_job
from nsapp.db import engine, write_transaction
from nsapp.errors import AppError
from nsapp.repositories import history, jobs, notifications, records
from nsapp.services import accounts
from nsapp.tasks.state import AccountState


def test_user_edit_and_task_result_both_survive(account):
    a = account()["id"]
    state = AccountState.load(a)
    accounts.update(a, {"name": "Edited"})
    state.record["last_status"] = "success"
    state.commit()
    final = records.accounts.get(a)
    assert final["name"] == "Edited" and final["last_status"] == "success"


def test_result_for_deleted_account_does_not_resurrect_it(account):
    a = account()["id"]
    state = AccountState.load(a)
    accounts.delete(a)
    state.record["last_status"] = "success"
    state.commit()
    assert records.accounts.get(a) is None


def test_result_obtained_with_replaced_cookie_is_dropped(account):
    a = account()["id"]
    state = AccountState.load(a)
    accounts.update(a, {"cookie": "session=replacement"})
    state.record["last_status"] = "nodeseek_auth_expired"
    state.commit()
    assert records.accounts.get(a)["last_status"] is None


def test_unrelated_fields_written_by_two_tasks_do_not_clobber(account):
    a = account()["id"]
    x, y = AccountState.load(a), AccountState.load(a)
    x.record["last_status"] = "success"
    y.record["last_monitor_status"] = "no_match"
    x.commit()
    y.commit()
    final = records.accounts.get(a)
    assert final["last_status"] == "success" and final["last_monitor_status"] == "no_match"


def test_runtime_commit_does_not_touch_updated_at(account):
    a = account()
    state = AccountState.load(a["id"])
    state.record.update(last_status="success", updated_at="tampered")
    state.commit()
    assert records.accounts.get(a["id"])["updated_at"] == a["updated_at"]


def test_replacing_the_cookie_forgets_expiry_but_keeps_other_results(account):
    a = account()["id"]
    records.accounts.patch(a, {
        "last_status": "nodeseek_auth_expired", "last_message": "NODESEEK_AUTH_EXPIRED",
        "last_monitor_status": "notified", "last_monitor_message": "NODESEEK_MONITOR_NOTIFIED",
        "last_offline_status": "notified", "last_offline_message": "NODESEEK_OFFLINE_NOTIFIED",
        "cookie_offline_notified": True,
    })
    accounts.update(a, {"name": "Renamed"})  # not a cookie change: nothing is forgotten
    assert records.accounts.get(a)["last_status"] == "nodeseek_auth_expired"
    accounts.update(a, {"cookie": "session=fresh"})
    record = records.accounts.get(a)
    assert record["last_status"] is None and record["last_message"] is None
    assert record["last_offline_status"] is None and record["cookie_offline_notified"] is False
    assert record["last_monitor_status"] == "notified"


def test_names_are_unique_case_insensitively(account):
    account("Case")
    with pytest.raises(AppError) as caught:
        account("case")
    assert caught.value.code == "NODESEEK_NAME_CONFLICT"


def test_rename_keeps_cookie_ciphertext(account):
    a = account()["id"]
    cipher = records.accounts.get(a)["cookie"]
    accounts.update(a, {"name": "Changed"})
    assert records.accounts.get(a)["cookie"] == cipher


def test_history_pagination_is_newest_first_and_hides_idle_checks():
    for i in range(125):
        history.append("checkin", {"account_id": "a", "status": "success", "ran_at": str(i), "sequence": i})
    page = history.page("checkin", 20, 100)
    assert page["total"] == 125 and len(page["items"]) == 20 and page["items"][0]["sequence"] == 24
    history.append("monitor", {"account_id": "a", "status": "no_match", "ran_at": "x"})
    history.append("monitor", {"account_id": "a", "status": "notified", "ran_at": "y"})
    assert history.page("monitor")["total"] == 1


# --- jobs ----------------------------------------------------------------------------------

def test_cycle_is_idempotent():
    assert jobs.enqueue("a", "sign", "2026-10-04") == jobs.enqueue("a", "sign", "2026-10-04")


def test_pending_monitor_jobs_coalesce():
    jobs.enqueue("a", "monitor", "1")
    jobs.claim()
    for i in range(2, 502):
        jobs.enqueue("a", "monitor", str(i))
    assert jobs.state()["counts"] == {"queued": 1, "running": 1}


def test_one_running_job_per_account():
    jobs.enqueue("a", "sign", "1")
    jobs.enqueue("a", "monitor", "2")
    jobs.enqueue("b", "sign", "1")
    one, two = jobs.claim(), jobs.claim()
    assert one["account_id"] != two["account_id"] and jobs.claim() is None


def test_manual_jobs_run_before_scheduled_ones():
    jobs.enqueue("a", "monitor", "1")
    jobs.enqueue("b", "sign", "1")
    jobs.enqueue("c", "message", "1", source="manual")
    assert [jobs.claim()["account_id"] for _ in range(3)] == ["c", "b", "a"]


@pytest.mark.parametrize("phase,status", [("reading", "queued"), ("external_write", "uncertain")])
def test_expired_lease_is_recovered_by_phase(phase, status):
    jobs.enqueue("a", "sign", "1")
    job = jobs.claim()
    jobs.set_phase(job, phase)
    with write_transaction() as conn:
        conn.execute(text("UPDATE jobs SET lease_until=:old"), {"old": jobs.stamp(-100)})
    assert jobs.recover() == 1 and jobs.get(job["id"])["status"] == status
    with pytest.raises(AppError) as lost:
        jobs.set_phase(job, "external_write")
    assert lost.value.code == "TASK_LEASE_LOST"


def test_retry_gives_up_after_three_attempts():
    job_id = jobs.enqueue("a", "monitor", "1")
    for _ in range(3):
        jobs.retry(jobs.claim(), "TEMPORARY")
        with write_transaction() as conn:
            conn.execute(text("UPDATE jobs SET next_run_at=:n"), {"n": jobs.stamp(-1)})
    assert jobs.get(job_id)["status"] == "failed" and jobs.get(job_id)["attempts"] == 3


def test_queue_capacity_is_enforced():
    for i in range(1000):
        jobs.enqueue(str(i), "monitor", "cycle")
    with pytest.raises(AppError) as full:
        jobs.enqueue("overflow", "monitor", "cycle")
    assert full.value.code == "TASK_QUEUE_FULL" and jobs.state()["counts"] == {"queued": 1000}


def test_pruning_keeps_uncertain_and_pending_jobs():
    old = jobs.enqueue("old", "monitor", "1")
    jobs.finish(jobs.claim(), {"success": True})
    uncertain = jobs.enqueue("verify", "sign", "1")
    jobs.finish(jobs.claim(), {"success": False}, "uncertain")
    pending = jobs.enqueue("pending", "monitor", "1")
    with write_transaction() as conn:
        conn.execute(text("UPDATE jobs SET updated_at=:n"), {"n": jobs.stamp(-8 * 86400)})
    assert jobs.prune() == 1 and jobs.get(old) is None
    assert jobs.get(uncertain)["status"] == "uncertain" and jobs.get(pending)["status"] == "queued"


def test_stale_worker_cannot_write_after_losing_its_lease(account):
    a = account()["id"]
    before = records.accounts.get(a)
    jobs.enqueue(a, "monitor", "cycle")
    old = jobs.claim()
    with write_transaction() as conn:
        conn.execute(text("UPDATE jobs SET lease_until=:n"), {"n": jobs.stamp(-100)})
    jobs.recover()
    new = jobs.claim()
    assert new["run_token"] != old["run_token"]
    token = current_job.set(old)
    try:
        with pytest.raises(AppError) as lost:
            records.accounts.patch(a, {"last_status": "stale"})
        assert lost.value.code == "TASK_LEASE_LOST"
        with pytest.raises(AppError):
            history.append("checkin", {"account_id": a, "status": "stale"})
    finally:
        current_job.reset(token)
    assert records.accounts.get(a) == before and history.page("checkin")["total"] == 0
    jobs.finish(old, {"success": True})
    assert jobs.get(new["id"])["status"] == "running"  # the stale finish touched nothing


def test_worker_heartbeat_excludes_a_second_instance():
    jobs.heartbeat("one", jobs.stamp(), 4)
    with pytest.raises(RuntimeError):
        jobs.heartbeat("two", jobs.stamp(), 4)
    assert jobs.state()["ready"]


# --- notification ledger -----------------------------------------------------------------------

def test_crash_while_sending_becomes_uncertain():
    notifications.prepare("event", "a", 1, "bot", "chat", "body")
    notifications.claim("event")
    notifications.recover_sending()
    with pytest.raises(AppError) as caught:
        notifications.claim("event")
    assert caught.value.code == "TELEGRAM_RESULT_UNCERTAIN"


def test_delivered_event_is_never_claimed_again():
    notifications.prepare("event", "a", 1, "bot", "chat", "body")
    notifications.claim("event")
    notifications.finish("event", "sent", message_id="42")
    assert notifications.claim("event") is None


def test_preparing_the_same_event_twice_keeps_one_row():
    for _ in range(2):
        notifications.prepare("event", "a", 1, "bot", "chat", "body")
    with engine.connect() as conn:
        assert conn.execute(text("SELECT count(*) FROM notifications")).scalar_one() == 1
