"""Timestamp helpers. Formats are load-bearing: they are compared as strings in SQL."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def iso_z(moment: datetime | None = None) -> str:
    """Second-precision UTC like ``2026-10-06T12:00:00Z`` (shown to users)."""
    moment = moment or utc_now()
    return moment.replace(microsecond=0).isoformat().replace("+00:00", "Z")


def stamp(offset_seconds: float = 0) -> str:
    """Microsecond UTC used by job leases and the notification ledger."""
    return (utc_now() + timedelta(seconds=offset_seconds)).isoformat(timespec="microseconds")


def parse_iso(value: object) -> datetime | None:
    """Parse ``iso_z``/``stamp`` output; None when empty or malformed."""
    try:
        return datetime.fromisoformat(str(value or "").replace("Z", "+00:00"))
    except ValueError:
        return None
