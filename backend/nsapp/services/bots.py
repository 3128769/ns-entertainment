"""Telegram bots that notifications are sent through."""
from __future__ import annotations

import secrets

import httpx

from nsapp.errors import AppError
from nsapp.integrations import telegram
from nsapp.repositories import records
from nsapp.settings import decrypt_secret, encrypt_secret
from nsapp.timeutil import iso_z


def list_bots() -> list[dict]:
    items = [
        {
            "id": bot_id,
            "username": record.get("username", ""),
            "name": record.get("name", ""),
            "enabled": bool(record.get("enabled", True)),
            "chat_id": record.get("chat_id"),
        }
        for bot_id, record in records.bots.all().items()
    ]
    return sorted(items, key=lambda item: item["name"].casefold())


def save(name: str, token: str, chat_id: str, bot_id: str | None = None) -> dict:
    """Create a bot, or update ``bot_id``; a blank token keeps the stored one."""
    name, token, chat_id = name.strip(), token.strip(), chat_id.strip()
    existing = records.bots.get(bot_id) if bot_id else None
    if not token and existing:
        encrypted = existing["token"]
    elif token and ":" in token:
        encrypted = encrypt_secret(token)
    else:
        raise AppError("BOT_FIELDS_INVALID")
    if not name or not chat_id:
        raise AppError("BOT_FIELDS_INVALID")
    now = iso_z()
    record = {
        "name": name[:64], "token": encrypted, "chat_id": chat_id[:64], "enabled": True,
        "created_at": (existing or {}).get("created_at") or now, "updated_at": now,
    }
    bot_id = bot_id or "bot_" + secrets.token_hex(6)
    records.bots.patch(bot_id, record, create=True)
    return {"id": bot_id, "name": record["name"], "chat_id": record["chat_id"], "enabled": True}


def delete(bot_id: str) -> dict:
    if not records.bots.delete(bot_id):
        raise AppError("BOT_NOT_FOUND")
    return {"success": True, "bot_id": bot_id}


async def test(bot_id: str) -> dict:
    """Validate the token and default chat without sending a message."""
    record = records.bots.get(bot_id)
    if record is None:
        raise AppError("BOT_NOT_FOUND")
    try:
        await telegram.verify(decrypt_secret(str(record.get("token") or "")), record.get("chat_id"))
    except httpx.TimeoutException:
        return {"success": False, "message": "TELEGRAM_TIMEOUT"}
    except httpx.RequestError:
        return {"success": False, "message": "TELEGRAM_NETWORK_FAILED"}
    except AppError as exc:
        return {"success": False, "message": exc.code}
    return {"success": True, "message": "Bot Token 和默认接收人校验通过（未发送消息）"}
