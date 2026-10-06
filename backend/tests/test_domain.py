from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from nsapp.domain import accounts as rules
from nsapp.domain import schedule
from nsapp.errors import AppError

SH = ZoneInfo("Asia/Shanghai")


def at(day, hour, minute=0, second=0):
    return datetime(2026, 10, day, hour, minute, second, tzinfo=SH)


def test_fixed_schedule_is_due_after_the_time_once_per_day():
    account = {"enabled": True, "schedule_mode": "fixed", "schedule_time": "08:20"}
    assert schedule.plan_jobs({"a": account}, at(6, 8, 19)) == []
    assert schedule.plan_jobs({"a": account}, at(6, 8, 21)) == [schedule.JobRequest("a", "sign", "2026-10-06")]
    done = {**account, "last_run_at": "2026-10-06T00:30:00Z", "last_source": "scheduled"}  # 08:30 Shanghai
    assert schedule.plan_jobs({"a": done}, at(6, 9)) == []
    manual = {**account, "last_run_at": "2026-10-06T00:30:00Z", "last_source": "manual"}
    assert [j.kind for j in schedule.plan_jobs({"a": manual}, at(6, 9))] == ["sign"]


def test_range_schedule_is_stable_inside_the_window():
    account = {"enabled": True, "schedule_mode": "range", "schedule_start": "08:00", "schedule_end": "10:00"}
    first = schedule.due_time("a", account, at(6, 7))
    assert first == schedule.due_time("a", account, at(6, 23))
    assert at(6, 8) <= first < at(6, 10)
    assert schedule.due_time("b", account, at(6, 7)) != first or schedule.due_time("c", account, at(6, 7)) != first


def test_range_across_midnight_belongs_to_the_day_it_started():
    account = {"enabled": True, "schedule_mode": "range", "schedule_start": "23:30", "schedule_end": "00:30"}
    early = at(7, 0, 10)  # still the 6th's window
    due = schedule.due_time("a", account, early)
    assert at(6, 23, 30) <= due < at(7, 0, 30)
    assert schedule._cycle_date(account, early).isoformat() == "2026-10-06"
    assert schedule._cycle_date(account, at(7, 12)).isoformat() == "2026-10-07"


def test_monitors_poll_at_their_intervals_and_offline_ignores_pause():
    now = at(6, 12)
    account = {"enabled": True, "schedule_time": "23:59", "keyword_monitor_enabled": True, "message_monitor_enabled": True}
    kinds = [j.kind for j in schedule.plan_jobs({"a": account}, now)]
    assert kinds == ["monitor", "message"]
    recent = {**account, "last_monitor_at": "2026-10-06T04:00:00Z", "last_message_monitor_at": "2026-10-06T03:59:30Z"}  # 12:00:00 / 11:59:30
    assert schedule.plan_jobs({"a": recent}, at(6, 12, 0, 0)) == []
    assert [j.kind for j in schedule.plan_jobs({"a": recent}, at(6, 12, 0, 20))] == ["monitor"]
    assert [j.kind for j in schedule.plan_jobs({"a": recent}, at(6, 12, 1, 0))] == ["monitor", "message"]
    paused = {"enabled": False, "offline_notify_enabled": True, "keyword_monitor_enabled": True}
    assert [j.kind for j in schedule.plan_jobs({"a": paused}, now)] == ["offline"]


def normalize(payload, current=None, proxies=()):
    return rules.normalize(payload, current, proxy_exists=lambda pid: pid in proxies)


def test_normalize_defaults_and_keyword_cleanup():
    config = normalize({"name": "  Foo  Bar ", "keywords": ["VPS", "vps", " ＶＰＳ ", "cn2", ""]})
    assert config["name"] == "Foo Bar" and config["keywords"] == ["VPS", "cn2"]
    assert config["schedule_mode"] == "fixed" and config["schedule_time"] == "08:20" and config["enabled"] is True


@pytest.mark.parametrize("payload,code", [
    ({"name": ""}, "NODESEEK_NAME_REQUIRED"),
    ({"name": "x", "schedule_time": "25:00"}, "NODESEEK_SCHEDULE_INVALID"),
    ({"name": "x", "schedule_mode": "range", "schedule_start": "09:00", "schedule_end": "09:00"}, "NODESEEK_SCHEDULE_RANGE_INVALID"),
    ({"name": "x", "proxy_id": "missing"}, "PROXY_NOT_FOUND"),
    ({"name": "x", "keywords": [str(i) for i in range(21)]}, "NODESEEK_KEYWORDS_INVALID"),
    ({"name": "x", "keyword_monitor_enabled": True}, "NODESEEK_MONITOR_CONFIG_REQUIRED"),
    ({"name": "x", "message_monitor_enabled": True, "message_bot_id": "b"}, "NODESEEK_MESSAGE_CONFIG_REQUIRED"),
    ({"name": "x", "offline_notify_enabled": True, "offline_chat_id": "1"}, "NODESEEK_OFFLINE_CONFIG_REQUIRED"),
])
def test_normalize_rejects_incomplete_config(payload, code):
    with pytest.raises(AppError) as caught:
        normalize(payload)
    assert caught.value.code == code


def test_partial_update_keeps_other_settings():
    current = normalize({"name": "A", "keywords": ["x"], "keyword_monitor_enabled": True,
                         "keyword_bot_id": "b", "keyword_chat_id": "1"})
    changed = normalize({"enabled": False}, current)
    assert changed["keywords"] == ["x"] and changed["keyword_monitor_enabled"] and changed["enabled"] is False


def test_public_view_never_exposes_the_cookie():
    view = rules.public_view("id", {"name": "A", "cookie": "fernet:secret", "enabled": True})
    assert view["cookie_set"] is True and "cookie" not in view and view["id"] == "id"
