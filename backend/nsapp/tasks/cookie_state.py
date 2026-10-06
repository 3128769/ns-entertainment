"""Cookie health bookkeeping shared by the tasks that exercise the cookie."""
from __future__ import annotations

import hashlib

from nsapp.services.outbox import send_message
from nsapp.timeutil import iso_z

EXPIRED_CODES = {"NODESEEK_AUTH_EXPIRED", "NODESEEK_COOKIE_EXPIRED"}


async def sync(record: dict, expired: bool) -> None:
    """Update the cookie status fields; notify once when a cookie turns expired.

    Does nothing unless the account opted into expiry notifications.
    """
    if not record.get("offline_notify_enabled"):
        return
    record["last_offline_at"] = iso_z()
    if not expired:
        record.update(last_offline_status="ok", last_offline_message="NODESEEK_COOKIE_OK", cookie_offline_notified=False)
        return
    record.update(last_offline_status="expired", last_offline_message="NODESEEK_AUTH_EXPIRED")
    if record.get("cookie_offline_notified"):
        return
    bot, chat = str(record.get("offline_bot_id") or ""), str(record.get("offline_chat_id") or "")
    if not bot or not chat:
        return
    # One alert per distinct cookie: the event key is derived from the cookie ciphertext.
    event_key = "offline:" + hashlib.sha256(str(record.get("cookie")).encode()).hexdigest()
    try:
        await send_message(
            bot, chat, "⚠️ NodeSeek 账号掉线 · " + str(record.get("name") or "") + "\n\n🍪 Cookie 已过期，请重新更新。",
            event_key=event_key,
        )
        record.update(cookie_offline_notified=True, last_offline_status="notified", last_offline_message="NODESEEK_OFFLINE_NOTIFIED")
    except Exception:
        record.update(last_offline_status="notify_failed", last_offline_message="NODESEEK_OFFLINE_NOTIFY_FAILED")
