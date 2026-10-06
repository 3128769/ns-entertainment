"""Periodic cookie health check (and expiry alert) for accounts that opted in."""
from __future__ import annotations

from nsapp.errors import AppError
from nsapp.integrations import nodeseek
from nsapp.services import accounts
from nsapp.tasks import cookie_state
from nsapp.tasks.state import AccountState
from nsapp.timeutil import iso_z


async def _is_expired(record: dict) -> bool:
    response = await accounts.nodeseek_for(record).private_messages()
    if nodeseek.auth_expired(response):
        return True
    if nodeseek.access_blocked(response):
        raise AppError("NODESEEK_CLOUDFLARE_BLOCKED")
    if response.status_code != 200:
        raise AppError("NODESEEK_OFFLINE_FAILED")
    try:
        data = response.json()
    except Exception:
        raise AppError("NODESEEK_OFFLINE_FAILED") from None
    if not isinstance(data, dict) or data.get("success") is not True:
        raise AppError("NODESEEK_OFFLINE_FAILED")
    return False


async def run(account_id: str, source: str = "scheduled") -> dict:
    state = AccountState.load(account_id)
    record = state.record
    if not record.get("offline_notify_enabled"):
        raise AppError("NODESEEK_OFFLINE_DISABLED")
    ran_at = iso_z()
    common = {"account_id": account_id, "account_name": record.get("name"), "source": source, "ran_at": ran_at}
    try:
        expired = await _is_expired(record)
    except Exception as exc:
        code = exc.code if isinstance(exc, AppError) else "NODESEEK_OFFLINE_FAILED"
        record.update(last_offline_status="failed", last_offline_message=code, last_offline_at=ran_at)
        state.commit()
        return {"success": False, "status": "failed", "message": code, **common}
    await cookie_state.sync(record, expired)
    state.commit()
    return {"success": not expired, "status": record.get("last_offline_status"), "message": record.get("last_offline_message"), **common}
