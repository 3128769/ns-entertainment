"""All JSON endpoints. Handlers are thin: parse, call a service, return its result.

Business failures are ``AppError``s and become ``{"detail": CODE}`` in ``app.py``.
Handlers that touch SQLite are plain ``def`` so FastAPI runs them in its thread
pool and the event loop stays free.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Header, Request

from nsapp import VERSION
from nsapp.api.deps import bearer_token, require_user
from nsapp.api.schemas import (
    AccountBody, AccountUpdateBody, BotBody, LoginBody, ProxyBody, ProxyUpdateBody,
)
from nsapp.errors import AppError
from nsapp.repositories import jobs
from nsapp.services import accounts, auth, bots, history, manual_run, proxies

router = APIRouter(prefix="/api")
protected = APIRouter(prefix="/api", dependencies=[Depends(require_user)])
_throttle = auth.LoginThrottle()


def client_address(request: Request) -> str:
    """The caller's address for rate limiting.

    The API only listens on the loopback interface behind nginx, which overwrites
    ``X-Real-IP`` with the real peer address, so the header cannot be spoofed by clients.
    """
    forwarded = request.headers.get("x-real-ip", "").strip()
    return forwarded or (request.client.host if request.client else "unknown")


# --- authentication -------------------------------------------------------------------

@router.post("/auth/login")
def login(body: LoginBody, request: Request) -> dict:
    key = f"{client_address(request)}:{body.username.strip().casefold()}"
    _throttle.check(key)
    token = auth.authenticate(body.username, body.password)
    if not token:
        _throttle.record_failure(key)
        raise AppError("INVALID_USERNAME_OR_PASSWORD")
    _throttle.clear(key)
    return {"access_token": token, "token_type": "bearer"}


@router.get("/auth/me")
def me(user: str = Depends(require_user)) -> dict:
    return {"username": user}


@router.post("/auth/logout")
def logout(authorization: str | None = Header(default=None), _user: str = Depends(require_user)) -> dict:
    auth.logout(bearer_token(authorization))
    return {"success": True}


# --- accounts --------------------------------------------------------------------------

@protected.get("/accounts")
def list_accounts() -> dict:
    return accounts.list_accounts()


@protected.post("/accounts", status_code=201)
def create_account(body: AccountBody) -> dict:
    return {"account": accounts.create(body.model_dump())}


@protected.patch("/accounts/{account_id}")
def update_account(account_id: str, body: AccountUpdateBody) -> dict:
    return {"account": accounts.update(account_id, body.model_dump(exclude_unset=True))}


@protected.delete("/accounts/{account_id}")
def delete_account(account_id: str) -> dict:
    return accounts.delete(account_id)


@protected.post("/accounts/{account_id}/run")
async def run_checkin(account_id: str) -> dict:
    return await manual_run.run_now(account_id, "sign")


@protected.post("/accounts/{account_id}/monitor/run")
async def run_keyword_check(account_id: str) -> dict:
    return await manual_run.run_now(account_id, "monitor")


@protected.post("/accounts/{account_id}/messages/run")
async def run_message_check(account_id: str) -> dict:
    return await manual_run.run_now(account_id, "message")


# --- proxies ---------------------------------------------------------------------------

@protected.get("/proxies")
def list_proxies() -> dict:
    return proxies.list_proxies()


@protected.post("/proxies", status_code=201)
def create_proxy(body: ProxyBody) -> dict:
    return {"proxy": proxies.create(body.name, body.remark, body.proxy_url)}


@protected.patch("/proxies/{proxy_id}")
def update_proxy(proxy_id: str, body: ProxyUpdateBody) -> dict:
    return {"proxy": proxies.update(proxy_id, body.name, body.remark, body.proxy_url)}


@protected.delete("/proxies/{proxy_id}")
def delete_proxy(proxy_id: str) -> dict:
    return proxies.delete(proxy_id)


@protected.post("/proxies/{proxy_id}/test")
async def test_proxy(proxy_id: str) -> dict:
    return await proxies.test(proxy_id)


# --- notification bots -------------------------------------------------------------------

@protected.get("/bots")
def list_bots() -> dict:
    return {"items": bots.list_bots()}


@protected.post("/bots", status_code=201)
def save_bot(body: BotBody) -> dict:
    return {"bot": bots.save(body.name, body.token, body.chat_id, body.bot_id)}


@protected.delete("/bots/{bot_id}")
def delete_bot(bot_id: str) -> dict:
    return bots.delete(bot_id)


@protected.post("/bots/{bot_id}/test")
async def test_bot(bot_id: str) -> dict:
    return await bots.test(bot_id)


# --- history and system -------------------------------------------------------------------

def _history_route(path: str, kind: str) -> None:
    def handler(limit: int = 100, offset: int = 0, account_id: str | None = None, status: str | None = None) -> dict:
        return history.page(kind, limit, offset, account_id, status)

    handler.__name__ = f"{kind}_history"
    protected.get(path)(handler)


_history_route("/history", "checkin")
_history_route("/monitor-history", "monitor")
_history_route("/message-history", "message")


@protected.get("/system/tasks")
def system_tasks() -> dict:
    return {**jobs.state(), "version": VERSION}
