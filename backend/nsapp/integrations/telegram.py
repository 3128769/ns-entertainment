"""Telegram Bot API calls."""
from __future__ import annotations

import httpx

from nsapp.errors import AppError

_API = "https://api.telegram.org"


def check_response(response: httpx.Response) -> dict:
    """Translate a Bot API reply into the payload or a stable error code."""
    try:
        payload = response.json()
    except ValueError:
        raise AppError("TELEGRAM_RESPONSE_INVALID") from None
    if not isinstance(payload, dict):
        raise AppError("TELEGRAM_RESPONSE_INVALID")
    description = str(payload.get("description") or "").lower()
    if response.status_code in {401, 404}:
        raise AppError("TELEGRAM_TOKEN_INVALID")
    if "chat not found" in description:
        raise AppError("TELEGRAM_CHAT_UNAVAILABLE")
    if "blocked" in description or "forbidden" in description or response.status_code == 403:
        raise AppError("TELEGRAM_CHAT_FORBIDDEN")
    if response.status_code == 429:
        raise AppError("TELEGRAM_RATE_LIMITED")
    if response.status_code >= 400 or not payload.get("ok"):
        raise AppError("TELEGRAM_SEND_FAILED")
    return payload


async def send(token: str, chat_id: str, body: str) -> int | None:
    """Send a plain message; returns Telegram's message id."""
    async with httpx.AsyncClient(timeout=20, follow_redirects=True) as client:
        response = await client.post(
            f"{_API}/bot{token}/sendMessage",
            json={"chat_id": chat_id, "text": body, "disable_web_page_preview": True},
        )
    return (check_response(response).get("result") or {}).get("message_id")


async def verify(token: str, chat_id: str | None) -> None:
    """Check the token and that the chat is reachable, without sending anything."""
    async with httpx.AsyncClient(timeout=15) as client:
        check_response(await client.get(f"{_API}/bot{token}/getMe"))
        response = await client.get(f"{_API}/bot{token}/getChat", params={"chat_id": chat_id})
        if response.status_code == 400:
            raise AppError("TELEGRAM_CHAT_UNAVAILABLE")
        check_response(response)
