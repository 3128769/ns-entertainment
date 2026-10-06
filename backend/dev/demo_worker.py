"""The real Worker with NodeSeek and Telegram replaced by canned responses."""
from __future__ import annotations

import asyncio

import httpx

from dev.guard import require_demo_dir

require_demo_dir()

from nsapp.integrations import telegram  # noqa: E402
from nsapp.integrations.nodeseek import NodeSeek, Post  # noqa: E402
from nsapp.worker import main as worker  # noqa: E402

_counter = {"posts": 200}


async def checkin(self, *, random_reward):
    await asyncio.sleep(1.2)
    return httpx.Response(200, json={"success": True, "message": "今天的签到收益是6个鸡腿"})


async def private_messages(self):
    await asyncio.sleep(0.6)
    return httpx.Response(200, json={"success": True, "msgArray": []})


async def latest_posts(self):
    await asyncio.sleep(0.6)
    _counter["posts"] += 1
    return [Post(str(_counter["posts"]), "出一台 VPS 圈钱", f"https://www.nodeseek.com/post-{_counter['posts']}-1", "")]


async def send(token, chat_id, body):
    print(f"[fake telegram -> {chat_id}] {body[:60]!r}")
    return 1


NodeSeek.checkin = checkin
NodeSeek.private_messages = private_messages
NodeSeek.latest_posts = latest_posts
telegram.send = send

if __name__ == "__main__":
    asyncio.run(worker.main())
