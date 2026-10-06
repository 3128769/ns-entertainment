"""Keyword monitoring of NodeSeek's public RSS feed."""
from __future__ import annotations

import asyncio

from nsapp.domain.text import folded
from nsapp.errors import AppError
from nsapp.services import accounts
from nsapp.services.outbox import send_message
from nsapp.tasks.state import AccountState
from nsapp.timeutil import iso_z

FEED_TIMEOUT = 90
BATCH_SIZE = 15
TELEGRAM_TEXT_LIMIT = 4000


def match_keyword(keywords: list[str], title: str) -> str | None:
    """First configured keyword contained in the title (case/width-insensitive)."""
    haystack = folded(title)
    return next((word for word in keywords if folded(word) in haystack), None)


def _digest(heading: str, matches: list[dict]) -> tuple[str, list[dict]]:
    """Compose one Telegram message from as many matches as fit."""
    blocks: list[str] = []
    batch: list[dict] = []
    for post in matches[:BATCH_SIZE]:
        block = f"🔑 关键词：{post['keyword']}\n📝 标题：{post['title']}\n🔗 原帖地址：{post['url']}"
        if blocks and len(heading + "\n\n".join([*blocks, block])) > TELEGRAM_TEXT_LIMIT:
            break
        blocks.append(block)
        batch.append(post)
    return heading + "\n\n".join(blocks), batch


async def run(account_id: str, source: str = "manual") -> dict:
    state = AccountState.load(account_id)
    record = state.record
    if not record.get("keyword_monitor_enabled"):
        raise AppError("NODESEEK_MONITOR_DISABLED")
    watermark = int(record.get("keyword_post_watermark") or 0)
    started = iso_z()

    def finish(success, status, message, *, checked=0, new_posts=0, matched=0, notified=False, advance=None, matched_now=False):
        return _record(state, source, started, success, status, message, checked, new_posts, matched, notified, advance, matched_now)

    try:
        posts = await asyncio.wait_for(accounts.nodeseek_for(record).latest_posts(), FEED_TIMEOUT)
    except Exception as exc:
        code = exc.code if isinstance(exc, AppError) and exc.code.startswith("NODESEEK_") else "NODESEEK_MONITOR_FAILED"
        return finish(False, "failed", code)

    latest = max((int(post.id) for post in posts), default=watermark)
    if not watermark:  # first run: remember where the feed is, never replay old posts
        return finish(True, "baseline", "NODESEEK_MONITOR_BASELINE_SAVED", checked=len(posts), advance=latest)

    fresh = [post for post in posts if int(post.id) > watermark]
    matches = list(record.get("keyword_pending_posts") or [])  # unsent matches from earlier runs
    queued = {post["id"] for post in matches}
    for post in fresh:
        keyword = match_keyword(record.get("keywords", []), post.title)
        if keyword and post.id not in queued:
            matches.append({**post.as_dict(), "keyword": keyword})
            queued.add(post.id)
    if not matches:
        return finish(True, "no_match", "NODESEEK_MONITOR_NO_MATCH", checked=len(posts), new_posts=len(fresh), advance=latest)

    text, batch = _digest("🔔 NodeSeek 关键词监听 · " + str(record.get("name")) + "\n\n", matches)
    record["keyword_pending_posts"] = matches  # kept until the send succeeds
    try:
        await send_message(
            str(record.get("keyword_bot_id") or ""), str(record.get("keyword_chat_id") or ""), text,
            event_key="keyword:" + ":".join(sorted(post["id"] for post in batch)),
        )
    except Exception as exc:
        code = str(exc) if str(exc).startswith("TELEGRAM_") else "NODESEEK_MONITOR_NOTIFY_FAILED_WILL_RETRY"
        # Do not advance the watermark: the same posts are retried next run.
        return finish(False, "notify_failed", code, checked=len(posts), new_posts=len(fresh), matched=len(batch), matched_now=True)
    sent = {post["id"] for post in batch}
    record["keyword_pending_posts"] = [post for post in matches if post["id"] not in sent]
    return finish(True, "notified", "NODESEEK_MONITOR_NOTIFIED", checked=len(posts), new_posts=len(fresh),
                  matched=len(batch), notified=True, advance=latest, matched_now=True)


def _record(state, source, ran_at, success, status, message, checked, new_posts, matched, notified, advance, matched_now) -> dict:
    record = state.record
    record.update(last_monitor_status=status, last_monitor_message=message, last_monitor_at=ran_at)
    if matched_now:
        record["last_match_at"] = ran_at
    if advance:
        record["keyword_post_watermark"] = advance
    result = {
        "success": success, "status": status, "message": message,
        "account_id": state.id, "account_name": record.get("name"), "source": source,
        "checked": checked, "new_posts": new_posts, "matched": matched, "notified": notified, "ran_at": ran_at,
    }
    if status != "no_match":
        state.add_history("monitor", result)
    state.commit()
    return result
