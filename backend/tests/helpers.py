"""Fakes for NodeSeek and Telegram used by task tests."""
import httpx

from nsapp.integrations import nodeseek, telegram
from nsapp.integrations.nodeseek import NodeSeek, Post


def json_response(status=200, **body):
    return httpx.Response(status, json=body)


class Telegram:
    """Records sends; set ``fail`` to an exception to simulate an outage."""

    def __init__(self, monkeypatch):
        self.sent = []
        self.fail = None
        monkeypatch.setattr(telegram, "send", self._send)

    async def _send(self, token, chat_id, body):
        if self.fail:
            raise self.fail
        self.sent.append({"chat_id": chat_id, "body": body})
        return len(self.sent)


def fake_checkin(monkeypatch, handler):
    async def checkin(self, *, random_reward):
        return await handler()

    monkeypatch.setattr(NodeSeek, "checkin", checkin)


def fake_messages(monkeypatch, handler):
    async def private_messages(self):
        return await handler()

    monkeypatch.setattr(NodeSeek, "private_messages", private_messages)


def fake_posts(monkeypatch, handler):
    async def latest_posts(self):
        return await handler()

    monkeypatch.setattr(NodeSeek, "latest_posts", latest_posts)


def post(post_id, title):
    return Post(str(post_id), title, f"https://www.nodeseek.com/post-{post_id}-1", "")


__all__ = ["Telegram", "fake_checkin", "fake_messages", "fake_posts", "json_response", "nodeseek", "post"]
