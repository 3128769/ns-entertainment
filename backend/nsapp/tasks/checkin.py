"""Daily NodeSeek attendance."""
from __future__ import annotations

import re

import httpx

from nsapp import phases
from nsapp.context import current_job
from nsapp.domain.text import clean
from nsapp.errors import AppError
from nsapp.integrations import nodeseek
from nsapp.services import accounts
from nsapp.services.outbox import send_message
from nsapp.tasks import cookie_state
from nsapp.tasks.state import AccountState
from nsapp.timeutil import iso_z

_ALREADY = ("已完成签到", "已经签到", "今日已签到")
_GAINED = (re.compile(r"(\d+)\s*个?鸡腿"), re.compile(r"(?:获得|获取|增加|收益(?:是|为)?)\D{0,8}(\d+)"))


def _outcome(success: bool, status: str, message: str, gained: int | None = None) -> dict:
    return {"success": success, "status": status, "message": message, "gained": gained}


def interpret(data: dict) -> dict:
    """Turn NodeSeek's attendance JSON into a result."""
    message = clean(data.get("message") or data.get("msg") or "NodeSeek 返回了无法识别的响应")
    already = any(text in message for text in _ALREADY)
    success = bool(data.get("success")) or already or ("鸡腿" in message and "失败" not in message)
    match = next((m for m in (pattern.search(message) for pattern in _GAINED) if m), None)
    status = "already" if already else ("success" if success else "failed")
    return _outcome(success, status, message, int(match.group(1)) if match else None)


async def _attempt(record: dict) -> dict:
    try:
        client = accounts.nodeseek_for(record)
        phases.enter_external_write()
        response = await client.checkin(random_reward=bool(record.get("random_checkin", True)))
        nodeseek.raise_for_access(response)
        return interpret(response.json())
    except AppError as exc:
        if exc.code.startswith("NODESEEK_"):
            return _outcome(False, exc.code.lower(), exc.code)
        return _outcome(False, "uncertain", "NODESEEK_RESULT_UNCERTAIN")
    except httpx.ConnectError:
        # Nothing reached NodeSeek, so it is safe to say it failed rather than "uncertain".
        return _outcome(False, "failed", "NODESEEK_CONNECT_FAILED")
    except Exception:
        # Timeouts and unreadable replies: the check-in may or may not have happened.
        return _outcome(False, "uncertain", "NODESEEK_RESULT_UNCERTAIN")


async def run(account_id: str, source: str = "manual") -> dict:
    state = AccountState.load(account_id)
    record = state.record
    item = {
        **await _attempt(record),
        "account_id": account_id, "account_name": record.get("name"), "source": source, "ran_at": iso_z(),
    }
    record.update(last_status=item["status"], last_message=item["message"], last_run_at=item["ran_at"], last_source=source)
    if item["message"] in cookie_state.EXPIRED_CODES:
        await cookie_state.sync(record, True)
    elif item["success"]:
        await cookie_state.sync(record, False)
    if item["status"] == "success" and source == "scheduled":
        await _announce_success(record, item)
    state.add_history("checkin", item)
    state.commit()
    return item


async def _announce_success(record: dict, item: dict) -> None:
    """Scheduled check-ins report their reward through the account's alert bot."""
    bot, chat = str(record.get("offline_bot_id") or ""), str(record.get("offline_chat_id") or "")
    if not (bot and chat):
        return
    gained = item.get("gained")
    detail = f"🪙 今日收益：{gained} 个鸡腿" if gained is not None else f"💬 {item.get('message')}"
    job = current_job.get()
    cycle = job.get("cycle_key") if job else item["ran_at"]
    try:
        await send_message(bot, chat, "✅ NodeSeek 签到成功 · " + str(record.get("name")) + "\n\n" + detail, event_key="sign:" + str(cycle))
    except Exception:
        pass  # the check-in itself succeeded; a failed courtesy notice must not change its result
