"""Private-message monitoring through NodeSeek's notification API."""
from __future__ import annotations

from nsapp.domain.text import clean
from nsapp.errors import AppError
from nsapp.integrations import nodeseek
from nsapp.services import accounts
from nsapp.services.outbox import send_message
from nsapp.tasks import cookie_state
from nsapp.tasks.state import AccountState
from nsapp.timeutil import iso_z

MAX_SEEN = 500
MAX_PER_NOTICE = 10
INBOX_URL = f"{nodeseek.BASE}/notification#/message?mode=list"


async def _fetch(record: dict) -> list[dict]:
    response = await accounts.nodeseek_for(record).private_messages()
    nodeseek.raise_for_access(response)
    if response.status_code != 200:
        raise AppError("NODESEEK_MESSAGE_FAILED")
    data = response.json()
    items = data.get("msgArray") if isinstance(data, dict) and data.get("success") else None
    if not isinstance(items, list):
        raise AppError("NODESEEK_MESSAGE_FAILED")
    return items


def incoming(items: list[dict], my_name: str, seen: set[str]) -> list[dict]:
    """Messages addressed to this account that have not been reported yet."""
    mine: set = set()
    for item in items:
        if str(item.get("sender_name") or "") == my_name:
            mine.add(item.get("sender_id"))
        if str(item.get("receiver_name") or "") == my_name:
            mine.add(item.get("receiver_id"))
    fresh = []
    for item in items:
        message_id = str(item.get("max_id") or "")
        if message_id and message_id not in seen and item.get("receiver_id") in mine and item.get("sender_id") not in mine:
            fresh.append(item)
    return fresh


async def run(account_id: str, source: str = "manual") -> dict:
    state = AccountState.load(account_id)
    record = state.record
    if not record.get("message_monitor_enabled"):
        raise AppError("NODESEEK_MESSAGE_DISABLED")
    started = iso_z()
    seen = {str(x) for x in record.get("message_seen_max_ids") or record.get("keyword_seen_message_ids") or []}

    async def finish(success, status, message, *, checked=0, new_messages=0, notified=False, mark_seen=None):
        return await _record(state, source, started, success, status, message, checked, new_messages, notified, mark_seen)

    try:
        items = await _fetch(record)
    except ValueError as exc:
        code = str(exc) if str(exc).startswith("NODESEEK_") else "NODESEEK_MESSAGE_FAILED"
        return await finish(False, "failed", code)
    except Exception:
        return await finish(False, "failed", "NODESEEK_MESSAGE_FAILED")

    all_ids = [str(item.get("max_id")) for item in items if item.get("max_id") is not None]
    if not record.get("message_baseline_initialized", bool(seen)):  # first run: do not report history
        return await finish(True, "baseline", "NODESEEK_MESSAGE_BASELINE_SAVED", checked=len(items), mark_seen=all_ids)

    name = str(record.get("name") or "")
    fresh = incoming(items, name, seen)
    if not fresh:
        return await finish(True, "no_match", "NODESEEK_MESSAGE_NO_MATCH", checked=len(items), mark_seen=all_ids)

    shown = fresh[:MAX_PER_NOTICE]
    lines = [
        f"👤 私信用户：{clean(item.get('sender_name'), 32) or '未知用户'}\n"
        f"💬 私信内容：{clean(item.get('content'), 120) or '（无文本）'}"
        for item in shown
    ]
    text = "📩 NodeSeek 私信 · " + name + "\n\n" + "\n\n".join(lines) + "\n\n🔗 " + INBOX_URL
    try:
        await send_message(
            str(record.get("message_bot_id") or ""), str(record.get("message_chat_id") or ""), text,
            event_key="message:" + ":".join(sorted(str(item["max_id"]) for item in shown)),
        )
    except Exception as exc:
        code = str(exc) if str(exc).startswith("TELEGRAM_") else "NODESEEK_MESSAGE_NOTIFY_FAILED_WILL_RETRY"
        # mark_seen stays None so the same messages are reported again next run.
        return await finish(False, "notify_failed", code, checked=len(items), new_messages=len(fresh))
    return await finish(True, "notified", "NODESEEK_MESSAGE_NOTIFIED", checked=len(items), new_messages=len(fresh),
                        notified=True, mark_seen=all_ids)


async def _record(state, source, ran_at, success, status, message, checked, new_messages, notified, mark_seen) -> dict:
    record = state.record
    record.update(last_message_monitor_status=status, last_message_monitor_message=message, last_message_monitor_at=ran_at)
    if mark_seen is not None:
        previous = [str(x) for x in record.get("message_seen_max_ids") or record.get("keyword_seen_message_ids") or []]
        record["message_seen_max_ids"] = list(dict.fromkeys(previous + mark_seen))[-MAX_SEEN:]
        record["message_baseline_initialized"] = True
    if message in cookie_state.EXPIRED_CODES:
        await cookie_state.sync(record, True)
    elif success:
        await cookie_state.sync(record, False)
    result = {
        "success": success, "status": status, "message": message,
        "account_id": state.id, "account_name": record.get("name"), "source": source,
        "checked": checked, "new_messages": new_messages, "notified": notified, "ran_at": ran_at,
    }
    if status != "no_match":
        state.add_history("message", result)
    state.commit()
    return result
