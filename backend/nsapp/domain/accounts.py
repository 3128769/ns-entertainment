"""Account configuration rules and the shapes stored / exposed for an account."""
from __future__ import annotations

import re
from collections.abc import Callable
from typing import Any

from nsapp.domain.text import clean, folded
from nsapp.errors import AppError

DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/142.0.0.0 Safari/537.36"
)
MAX_KEYWORDS = 20
_CLOCK = re.compile(r"^(?:[01]\d|2[0-3]):[0-5]\d$")

# Fields a user edits. A write touching any of them is a "configuration" write;
# everything else on the record is runtime state owned by the Worker.
CONFIG_FIELDS = (
    "name", "enabled", "random_checkin",
    "schedule_time", "schedule_mode", "schedule_start", "schedule_end",
    "proxy_id", "user_agent",
    "keyword_monitor_enabled", "keywords", "keyword_bot_id", "keyword_chat_id",
    "message_monitor_enabled", "message_bot_id", "message_chat_id",
    "offline_notify_enabled", "offline_bot_id", "offline_chat_id",
)

RUNTIME_DEFAULTS: dict[str, Any] = {
    "keyword_seen_post_ids": [],
    "message_seen_max_ids": [],
    "last_status": None, "last_message": None, "last_run_at": None,
    "last_monitor_status": None, "last_monitor_message": None, "last_monitor_at": None,
    "last_match_at": None,
    "last_message_monitor_status": None, "last_message_monitor_message": None,
    "last_message_monitor_at": None,
    "last_offline_status": None, "last_offline_message": None, "last_offline_at": None,
    "cookie_offline_notified": False,
}

PUBLIC_FIELDS = (
    "name", "enabled", "random_checkin", "schedule_time", "schedule_mode", "schedule_start",
    "schedule_end", "proxy_id", "user_agent", "keyword_monitor_enabled", "keywords",
    "keyword_bot_id", "keyword_chat_id", "message_monitor_enabled", "message_bot_id",
    "message_chat_id", "offline_notify_enabled", "offline_bot_id", "offline_chat_id",
    "last_status", "last_message", "last_run_at", "last_monitor_status", "last_monitor_message",
    "last_monitor_at", "last_match_at", "last_message_monitor_status",
    "last_message_monitor_message", "last_message_monitor_at", "last_offline_status",
    "last_offline_message", "last_offline_at", "created_at", "updated_at",
)


def public_view(account_id: str, record: dict) -> dict:
    """What the API returns: no cookie, only whether one is set."""
    view = {key: record.get(key) for key in PUBLIC_FIELDS}
    view["id"] = account_id
    view["cookie_set"] = bool(record.get("cookie"))
    return view


def _next_hour(clock: str) -> str:
    try:
        hour, minute = clock.split(":")
        return f"{(int(hour) + 1) % 24:02d}:{minute}"
    except ValueError:
        return clock


def _pick(payload: dict, current: dict, key: str, default: Any = None) -> Any:
    return payload.get(key, current.get(key, default))


def _text_id(value: Any) -> str | None:
    return str(value or "") or None


def normalize(
    payload: dict,
    current: dict | None = None,
    *,
    proxy_exists: Callable[[str], bool],
) -> dict:
    """Merge ``payload`` over ``current`` and validate. Returns the config fields only."""
    current = current or {}

    name = clean(_pick(payload, current, "name"), 64)
    if not name:
        raise AppError("NODESEEK_NAME_REQUIRED")

    mode = str(_pick(payload, current, "schedule_mode", "fixed")).strip()
    fixed = str(_pick(payload, current, "schedule_time", "08:20")).strip()
    start = str(payload.get("schedule_start", current.get("schedule_start", fixed))).strip()
    end = str(payload.get("schedule_end", current.get("schedule_end", _next_hour(start)))).strip()
    if mode not in {"fixed", "range"} or not all(_CLOCK.fullmatch(v) for v in (fixed, start, end)):
        raise AppError("NODESEEK_SCHEDULE_INVALID")
    if mode == "range" and start == end:
        raise AppError("NODESEEK_SCHEDULE_RANGE_INVALID")

    proxy_id = _pick(payload, current, "proxy_id") or None
    if proxy_id and not proxy_exists(str(proxy_id)):
        raise AppError("PROXY_NOT_FOUND")

    keywords: list[str] = []
    seen: set[str] = set()
    for raw in _pick(payload, current, "keywords", []) or []:
        word = clean(raw, 64)
        if word and folded(word) not in seen:
            keywords.append(word)
            seen.add(folded(word))
    if len(keywords) > MAX_KEYWORDS:
        raise AppError("NODESEEK_KEYWORDS_INVALID")

    keyword_enabled = bool(_pick(payload, current, "keyword_monitor_enabled", False))
    keyword_bot = _pick(payload, current, "keyword_bot_id") or None
    keyword_chat = _text_id(_pick(payload, current, "keyword_chat_id"))
    if keyword_enabled and (not keywords or not keyword_bot or not keyword_chat):
        raise AppError("NODESEEK_MONITOR_CONFIG_REQUIRED")

    message_enabled = bool(_pick(payload, current, "message_monitor_enabled", False))
    message_bot = _pick(payload, current, "message_bot_id") or None
    message_chat = _text_id(_pick(payload, current, "message_chat_id"))
    if message_enabled and (not message_bot or not message_chat):
        raise AppError("NODESEEK_MESSAGE_CONFIG_REQUIRED")

    offline_enabled = bool(_pick(payload, current, "offline_notify_enabled", False))
    offline_bot = _pick(payload, current, "offline_bot_id") or None
    offline_chat = _text_id(_pick(payload, current, "offline_chat_id"))
    if offline_enabled and (not offline_bot or not offline_chat):
        raise AppError("NODESEEK_OFFLINE_CONFIG_REQUIRED")

    return {
        "name": name,
        "enabled": bool(_pick(payload, current, "enabled", True)),
        "random_checkin": bool(_pick(payload, current, "random_checkin", True)),
        "schedule_time": fixed,
        "schedule_mode": mode,
        "schedule_start": start,
        "schedule_end": end,
        "proxy_id": proxy_id,
        "user_agent": clean(_pick(payload, current, "user_agent") or DEFAULT_USER_AGENT, 512),
        "keyword_monitor_enabled": keyword_enabled,
        "keywords": keywords,
        "keyword_bot_id": keyword_bot,
        "keyword_chat_id": keyword_chat,
        "message_monitor_enabled": message_enabled,
        "message_bot_id": message_bot,
        "message_chat_id": message_chat,
        "offline_notify_enabled": offline_enabled,
        "offline_bot_id": offline_bot,
        "offline_chat_id": offline_chat,
    }
