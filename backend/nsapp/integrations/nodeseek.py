"""NodeSeek HTTP access and interpretation of its responses."""
from __future__ import annotations

import asyncio
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass

import httpx

from nsapp.errors import AppError

BASE = "https://www.nodeseek.com"
RSS_URL = "https://rss.nodeseek.com/"
_JSON_HEADERS = "application/json, text/plain, */*"

_AUTH_MARKERS = (
    "user not found", "unauthorized", "not logged", "login required",
    "未登录", "请先登录", "请登录", "登录失效", "登录已失效", "身份已过期",
)
_CHALLENGE_MARKERS = (
    "just a moment", "challenge-platform", "cf-chl", "cf-mitigated",
    "attention required", "/cdn-cgi/challenge-platform",
)


def json_body(response: httpx.Response) -> dict | None:
    """The JSON object in the response, or None for HTML, arrays and malformed bodies."""
    raw = response.text or ""
    content_type = (response.headers.get("content-type") or "").lower()
    if "json" not in content_type and not raw.lstrip().startswith(("{", "[")):
        return None
    try:
        data = response.json()
    except Exception:
        return None
    return data if isinstance(data, dict) else None


def auth_expired(response: httpx.Response) -> bool:
    """True when NodeSeek says the cookie is no longer logged in."""
    if response.status_code == 401:
        return True
    data = json_body(response)
    if data is None:
        return False
    message = str(data.get("message") or data.get("msg") or "").casefold()
    try:
        inner = int(data.get("status"))
    except (TypeError, ValueError):
        inner = None
    mentions_login = any(marker in message for marker in _AUTH_MARKERS)
    if mentions_login and (data.get("success") is False or response.status_code >= 400 or inner in {401, 403, 404}):
        return True
    return data.get("success") is False and inner == 401


def access_blocked(response: httpx.Response) -> bool:
    """True for a Cloudflare challenge or a bare 403: the cookie state is unknowable."""
    if auth_expired(response):
        return False
    body = (response.text or "").casefold()
    if any(marker in body for marker in _CHALLENGE_MARKERS) and response.status_code in {403, 503}:
        return True
    return response.status_code == 403 and json_body(response) is None


def raise_for_access(response: httpx.Response) -> None:
    if auth_expired(response):
        raise AppError("NODESEEK_AUTH_EXPIRED")
    if access_blocked(response):
        raise AppError("NODESEEK_CLOUDFLARE_BLOCKED")


@dataclass(frozen=True)
class Post:
    id: str
    title: str
    url: str
    published: str

    def as_dict(self) -> dict:
        return {"id": self.id, "title": self.title, "url": self.url, "pubDate": self.published}


def parse_rss(content: bytes) -> list[Post]:
    posts: list[Post] = []
    for node in ET.fromstring(content).iter("item"):
        def field(tag: str) -> str:
            child = node.find(tag)
            return (child.text or "").strip() if child is not None and child.text else ""

        match = re.search(r"(\d+)", field("guid"))
        title = field("title")
        if not match or not title:
            continue
        post_id = match.group(1)
        posts.append(Post(post_id, title, field("link") or f"{BASE}/post-{post_id}-1", field("pubDate")))
    return posts


class NodeSeek:
    """One account's view of NodeSeek: its cookie, user agent and optional proxy."""

    def __init__(self, *, cookie: str, user_agent: str, proxy_url: str | None) -> None:
        self._cookie = cookie
        self._user_agent = user_agent
        self._proxy_url = proxy_url

    def _client(self) -> httpx.AsyncClient:
        options: dict = {
            "headers": {"User-Agent": self._user_agent},
            "timeout": httpx.Timeout(60, connect=15),
            "follow_redirects": True,
        }
        if self._proxy_url:
            options["proxy"] = self._proxy_url
        return httpx.AsyncClient(**options)

    async def checkin(self, *, random_reward: bool) -> httpx.Response:
        """POST the daily attendance. The caller must mark the external-write phase first."""
        async with self._client() as client:
            return await client.post(
                f"{BASE}/api/attendance",
                params={"random": str(random_reward).lower()},
                headers={
                    "Accept": _JSON_HEADERS, "Content-Type": "application/json",
                    "Origin": BASE, "Referer": f"{BASE}/board", "Cookie": self._cookie,
                },
            )

    async def private_messages(self) -> httpx.Response:
        async with self._client() as client:
            return await asyncio.wait_for(
                client.get(
                    f"{BASE}/api/notification/message/list",
                    headers={"Accept": _JSON_HEADERS, "Cookie": self._cookie, "Referer": f"{BASE}/notification"},
                ),
                30,
            )

    async def latest_posts(self) -> list[Post]:
        """Public RSS feed, oldest first."""
        async with self._client() as client:
            response = await client.get(
                RSS_URL, headers={"Accept": "application/xml,text/xml,application/rss+xml;q=0.9,*/*;q=0.8"}
            )
        if response.status_code != 200:
            raise AppError("NODESEEK_FEED_INVALID")
        return sorted(parse_rss(response.content), key=lambda post: int(post.id))
