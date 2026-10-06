"""Decide which background jobs an account needs right now.

Pure functions of ``(accounts, now)`` so the rules can be tested with a fixed
clock. The Worker calls ``plan_jobs`` every ten seconds and enqueues the result;
the ``cycle_key`` makes enqueueing idempotent (same key => same job).
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from nsapp.settings import TIMEZONE
from nsapp.timeutil import parse_iso

MONITOR_INTERVAL = 15
MESSAGE_INTERVAL = 60
OFFLINE_INTERVAL = 300
_MINUTES_PER_DAY = 1440


@dataclass(frozen=True)
class JobRequest:
    account_id: str
    kind: str       # sign | monitor | message | offline
    cycle_key: str


def local_now() -> datetime:
    return datetime.now(ZoneInfo(TIMEZONE))


def _minutes(clock: str) -> int:
    return int(clock[:2]) * 60 + int(clock[3:])


def _window(account: dict) -> tuple[int, int]:
    """(start, end) minutes of a range schedule, falling back to the fixed time."""
    fixed = str(account.get("schedule_time") or "08:20")
    start = str(account.get("schedule_start") or fixed)
    end = str(account.get("schedule_end") or fixed)
    return _minutes(start), _minutes(end)


def _crosses_midnight(start: int, end: int) -> bool:
    return end <= start


def _cycle_date(account: dict, current: datetime):
    """Calendar day a check-in belongs to; a window past midnight still counts for yesterday."""
    day = current.date()
    if str(account.get("schedule_mode") or "fixed") == "range":
        start, end = _window(account)
        if _crosses_midnight(start, end) and current.hour * 60 + current.minute <= end:
            day -= timedelta(days=1)
    return day


def due_time(account_id: str, account: dict, current: datetime) -> datetime:
    """Moment today's (or the open window's) check-in becomes due.

    A range schedule picks a deterministic pseudo-random minute inside the window,
    seeded by the cycle's date and account id, so every poll agrees on it.
    """
    fixed = str(account.get("schedule_time") or "08:20")
    if str(account.get("schedule_mode") or "fixed") != "range":
        hour, minute = (int(part) for part in fixed.split(":"))
        return current.replace(hour=hour, minute=minute, second=0, microsecond=0)

    start = _minutes(str(account.get("schedule_start") or fixed))
    end = _minutes(str(account.get("schedule_end") or fixed))
    duration = (end - start) % _MINUTES_PER_DAY
    crosses = _crosses_midnight(start, end)
    base_date = current.date()
    if crosses and current.hour * 60 + current.minute <= end:
        base_date -= timedelta(days=1)
    seed = f"{base_date.isoformat()}:{account_id}"
    offset = int.from_bytes(hashlib.sha256(seed.encode()).digest()[:4], "big") % max(duration, 1)
    minute = (start + offset) % _MINUTES_PER_DAY
    due_date = base_date
    if crosses and minute < start:
        due_date += timedelta(days=1)
    return current.replace(
        year=due_date.year, month=due_date.month, day=due_date.day,
        hour=minute // 60, minute=minute % 60, second=0, microsecond=0,
    )


def _already_signed_in_cycle(account: dict, current: datetime, cycle_date) -> bool:
    last_run = parse_iso(account.get("last_run_at"))
    if last_run is None or last_run.tzinfo is None:
        return False
    last_local = last_run.astimezone(ZoneInfo(TIMEZONE))
    last_cycle = last_local.date()
    if str(account.get("schedule_mode") or "fixed") == "range":
        start, end = _window(account)
        if _crosses_midnight(start, end) and last_local.hour * 60 + last_local.minute <= end:
            last_cycle -= timedelta(days=1)
    scheduled = str(account.get("last_source") or "") in {"schedule", "scheduled"}
    return last_cycle == cycle_date and scheduled


def _stale(last_at: object, current: datetime, interval: int) -> bool:
    last = parse_iso(last_at)
    if last is None or last.tzinfo is None:
        return True
    return (current - last).total_seconds() >= interval


def plan_jobs(accounts: dict[str, dict], current: datetime) -> list[JobRequest]:
    requests: list[JobRequest] = []
    epoch = int(current.timestamp())
    for account_id, account in accounts.items():
        if not isinstance(account, dict):
            continue
        aid = str(account_id)
        if account.get("enabled"):
            cycle = _cycle_date(account, current)
            if current >= due_time(aid, account, current) and not _already_signed_in_cycle(account, current, cycle):
                requests.append(JobRequest(aid, "sign", cycle.isoformat()))
            if account.get("keyword_monitor_enabled") and _stale(account.get("last_monitor_at"), current, MONITOR_INTERVAL):
                requests.append(JobRequest(aid, "monitor", str(epoch // MONITOR_INTERVAL)))
            if account.get("message_monitor_enabled") and _stale(account.get("last_message_monitor_at"), current, MESSAGE_INTERVAL):
                requests.append(JobRequest(aid, "message", str(epoch // MESSAGE_INTERVAL)))
        # Cookie health is watched even while check-ins are paused.
        if account.get("offline_notify_enabled") and _stale(account.get("last_offline_at"), current, OFFLINE_INTERVAL):
            requests.append(JobRequest(aid, "offline", str(epoch // OFFLINE_INTERVAL)))
    return requests
