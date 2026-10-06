"""Send Telegram notifications through the delivery ledger (at-most-once).

``send_message`` stores the message under a deterministic event key, then
``deliver`` claims and sends it. Re-running the same event never sends twice; an
ambiguous outcome (timeout, malformed reply) is recorded as ``uncertain`` and is
not retried automatically.
"""
from __future__ import annotations

import hashlib

import httpx

from nsapp import phases
from nsapp.context import current_job
from nsapp.errors import AppError
from nsapp.integrations import telegram
from nsapp.repositories import notifications, records
from nsapp.settings import decrypt_secret

_TEMPORARY = {"TELEGRAM_RATE_LIMITED", "TELEGRAM_SEND_FAILED"}


async def send_message(bot_id: str, chat_id: str, text: str, event_key: str | None = None) -> int | None:
    bot = records.bots.get(bot_id)
    if bot is None:
        raise AppError("BOT_NOT_FOUND")
    target = str(chat_id or bot.get("chat_id") or "").strip()
    if not bot.get("token") or not target:
        raise AppError("BOT_CONFIG_INVALID")
    job = current_job.get() or {}
    identity = "|".join([str(job.get("account_id", "")), bot_id, target, str(event_key or text), str(bot.get("token"))])
    key = hashlib.sha256(identity.encode()).hexdigest()
    notifications.prepare(key, str(job.get("account_id", "")), job.get("id"), bot_id, target, text)
    return await deliver(key)


async def deliver(key: str) -> int | None:
    record = notifications.claim(key)
    if record is None:  # already sent
        return None
    payload = record["decoded"]
    bot = records.bots.get(payload["bot_id"])
    if not bot:
        notifications.finish(key, "failed", "BOT_NOT_FOUND")
        raise AppError("BOT_NOT_FOUND")
    attempts = record["attempts"]
    try:
        phases.enter_external_write()
        message_id = await telegram.send(decrypt_secret(bot["token"]), payload["chat_id"], payload["body"])
    except httpx.ConnectError:
        code = "TELEGRAM_NETWORK_FAILED"
        notifications.finish(key, "retry_wait" if attempts < notifications.MAX_ATTEMPTS else "failed", code, attempts=attempts)
        raise AppError(code) from None
    except (httpx.TimeoutException, httpx.RequestError):
        notifications.finish(key, "uncertain", "TELEGRAM_RESULT_UNCERTAIN")
        raise AppError("TELEGRAM_RESULT_UNCERTAIN") from None
    except ValueError as exc:
        code = str(exc)
        if code in _TEMPORARY and attempts < notifications.MAX_ATTEMPTS:
            status = "retry_wait"
        elif code == "TELEGRAM_RESPONSE_INVALID":
            status = "uncertain"
        else:
            status = "failed"
        notifications.finish(key, status, code, attempts=attempts)
        raise
    else:
        notifications.finish(key, "sent", message_id=message_id)
        return message_id
    finally:
        job = current_job.get()
        # A check-in keeps its write phase until its own result is stored.
        if job and job["job_type"] != "sign":
            phases.leave_external_write()
