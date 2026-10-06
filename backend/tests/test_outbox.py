import asyncio

import httpx
import pytest
from sqlalchemy import text

from nsapp.db import engine, write_transaction
from nsapp.errors import AppError
from nsapp.integrations import telegram
from nsapp.repositories import jobs, notifications
from nsapp.services import outbox
from nsapp.worker.main import execute


def row(key):
    with engine.connect() as conn:
        return dict(conn.execute(text("SELECT * FROM notifications WHERE event_key=:key"), {"key": key}).mappings().one())


@pytest.fixture
def event(bot):
    notifications.prepare("event", "account", None, bot, "mock-chat", "Synthetic body")


@pytest.mark.parametrize("succeed_at", [None, 3])
def test_automatic_retries_are_limited_to_three_attempts(monkeypatch, event, succeed_at):
    calls = []

    async def fake(*args):
        calls.append(args)
        if len(calls) == succeed_at:
            return 42
        raise httpx.ConnectError("synthetic")

    monkeypatch.setattr(telegram, "send", fake)
    with pytest.raises(AppError, match="NETWORK_FAILED"):
        asyncio.run(outbox.deliver("event"))
    assert row("event")["attempts"] == 1
    job_ids = []
    for attempt in (1, 2):
        with write_transaction() as conn:
            conn.execute(text("UPDATE notifications SET available_at=:n"), {"n": jobs.stamp(-1)})
        key, account_id, attempts = notifications.due()[0]
        assert attempts == attempt
        job_ids.append(jobs.enqueue(account_id, "notify", f"{key}:{attempts}"))
        asyncio.run(execute(jobs.claim()))
        assert row("event")["attempts"] == attempt + 1
    assert len(set(job_ids)) == 2 and len(calls) == 3
    assert row("event")["status"] == ("sent" if succeed_at else "failed")
    assert notifications.due() == []
    if succeed_at:
        asyncio.run(outbox.deliver("event"))  # already sent: no fourth call
    else:
        with pytest.raises(AppError, match="NETWORK_FAILED"):
            asyncio.run(outbox.deliver("event"))
    assert len(calls) == 3


@pytest.mark.parametrize("failure", [httpx.ReadTimeout("synthetic"), AppError("TELEGRAM_RESPONSE_INVALID")])
def test_ambiguous_outcomes_are_never_retried(monkeypatch, event, failure):
    calls = []

    async def fake(*args):
        calls.append(1)
        raise failure

    monkeypatch.setattr(telegram, "send", fake)
    with pytest.raises(ValueError):
        asyncio.run(outbox.deliver("event"))
    assert row("event")["status"] == "uncertain" and notifications.due() == []
    with pytest.raises(AppError, match="UNCERTAIN"):
        asyncio.run(outbox.deliver("event"))
    assert len(calls) == 1


def test_worker_marks_a_timed_out_notification_uncertain(monkeypatch, event):
    async def fake(*args):
        raise httpx.ReadTimeout("synthetic")

    monkeypatch.setattr(telegram, "send", fake)
    job_id = jobs.enqueue("account", "notify", "event:0")
    asyncio.run(execute(jobs.claim()))
    assert jobs.get(job_id)["status"] == "uncertain"
    assert row("event")["status"] == "uncertain" and notifications.due() == []


def test_same_event_key_sends_once(monkeypatch, bot):
    sent = []

    async def fake(token, chat, body):
        sent.append(body)
        return 1

    monkeypatch.setattr(telegram, "send", fake)

    async def twice():
        await outbox.send_message(bot, "chat", "hello", event_key="same")
        await outbox.send_message(bot, "chat", "hello again", event_key="same")

    asyncio.run(twice())
    assert sent == ["hello"]


def test_unknown_bot_is_reported(monkeypatch):
    with pytest.raises(AppError, match="BOT_NOT_FOUND"):
        asyncio.run(outbox.send_message("missing", "chat", "x"))
