"""Account CRUD and the NodeSeek session factory used by background tasks."""
from __future__ import annotations

import copy
import secrets

from nsapp.domain import accounts as rules
from nsapp.errors import AppError
from nsapp.integrations.nodeseek import NodeSeek
from nsapp.repositories import records
from nsapp.services import proxies
from nsapp.settings import decrypt_secret, encrypt_secret
from nsapp.timeutil import iso_z


def _valid_cookie(cookie: str) -> bool:
    return bool(cookie) and "=" in cookie


_EXPIRED_STATUSES = {"nodeseek_auth_expired", "nodeseek_cookie_expired", "expired"}
_EXPIRED_MESSAGES = {"NODESEEK_AUTH_EXPIRED", "NODESEEK_COOKIE_EXPIRED"}
_RESULT_FIELDS = (
    ("last_status", "last_message"),
    ("last_monitor_status", "last_monitor_message"),
    ("last_message_monitor_status", "last_message_monitor_message"),
    ("last_offline_status", "last_offline_message"),
)


def _forget_expiry(record: dict) -> dict:
    """Results that blamed the old cookie no longer apply once it is replaced."""
    cleared: dict = {}
    for status_key, message_key in _RESULT_FIELDS:
        status = str(record.get(status_key) or "").lower()
        message = str(record.get(message_key) or "").upper()
        notified = status_key == "last_offline_status" and status == "notified"
        if status in _EXPIRED_STATUSES or message in _EXPIRED_MESSAGES or notified:
            cleared[status_key] = None
            cleared[message_key] = None
    return cleared


def list_accounts() -> dict:
    items = [rules.public_view(aid, record) for aid, record in records.accounts.all().items()]
    items.sort(key=lambda item: (str(item["name"]).casefold(), item["id"]))
    return {"items": items, "total": len(items)}


def create(payload: dict) -> dict:
    config = rules.normalize(payload, proxy_exists=proxies.exists)
    cookie = str(payload.get("cookie") or "").strip()
    if not _valid_cookie(cookie):
        raise AppError("NODESEEK_COOKIE_REQUIRED")
    if records.accounts.name_taken(config["name"]):
        raise AppError("NODESEEK_NAME_CONFLICT")
    account_id = secrets.token_hex(16)
    now = iso_z()
    record = {
        **config, "cookie": encrypt_secret(cookie), **copy.deepcopy(rules.RUNTIME_DEFAULTS),
        "created_at": now, "updated_at": now,
    }
    records.accounts.patch(account_id, record, create=True)
    return rules.public_view(account_id, record)


def update(account_id: str, payload: dict) -> dict:
    current = records.accounts.get(account_id)
    if current is None:
        raise AppError("NODESEEK_ACCOUNT_NOT_FOUND")
    config = rules.normalize(payload, current, proxy_exists=proxies.exists)
    new_cookie = str(payload.get("cookie") or "").strip()
    if not _valid_cookie(new_cookie or decrypt_secret(current.get("cookie", ""))):
        raise AppError("NODESEEK_COOKIE_REQUIRED")
    if records.accounts.name_taken(config["name"], excluding=account_id):
        raise AppError("NODESEEK_NAME_CONFLICT")
    # Only changed fields are written, so a Worker result landing at the same
    # moment (different fields) is never overwritten.
    fields = {key: value for key, value in config.items() if current.get(key) != value}
    fields["updated_at"] = iso_z()
    if new_cookie:
        fields["cookie"] = encrypt_secret(new_cookie)
        fields["cookie_offline_notified"] = False
        fields.update(_forget_expiry(current))
    if not records.accounts.patch(account_id, fields):
        raise AppError("NODESEEK_ACCOUNT_NOT_FOUND")
    return rules.public_view(account_id, records.accounts.get(account_id) or {**current, **fields})


def delete(account_id: str) -> dict:
    if not records.accounts.delete(account_id):
        raise AppError("NODESEEK_ACCOUNT_NOT_FOUND")
    return {"success": True, "account_id": account_id}


def nodeseek_for(record: dict) -> NodeSeek:
    """A NodeSeek client carrying this account's cookie, user agent and proxy."""
    return NodeSeek(
        cookie=decrypt_secret(record.get("cookie", "")),
        user_agent=record.get("user_agent") or rules.DEFAULT_USER_AGENT,
        proxy_url=proxies.url_for(record.get("proxy_id")),
    )
