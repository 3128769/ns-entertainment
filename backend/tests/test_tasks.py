"""Behaviour of the four task handlers against faked NodeSeek / Telegram."""
import asyncio

import httpx
import pytest

from nsapp.errors import AppError
from nsapp.integrations import nodeseek
from nsapp.repositories import history, records
from nsapp.tasks import checkin, cookie_check, keywords, messages
from tests.helpers import Telegram, fake_checkin, fake_messages, fake_posts, json_response, post

run = asyncio.run


@pytest.fixture
def telegram(monkeypatch):
    return Telegram(monkeypatch)


def alerting(account, bot, **extra):
    return account(offline_notify_enabled=True, offline_bot_id=bot, offline_chat_id="alerts", **extra)


# --- check-in ------------------------------------------------------------------------------

@pytest.mark.parametrize("message,status,gained", [
    ("今天的签到收益是4个鸡腿", "success", 4),
    ("鸡腿 +5", "success", None),
    ("您已完成签到，请勿重复操作", "already", None),
    ("签到失败，请稍后再试", "failed", None),
])
def test_checkin_interprets_nodeseek_replies(monkeypatch, account, message, status, gained):
    async def reply():
        return json_response(success=status in {"success", "already"}, message=message)

    fake_checkin(monkeypatch, reply)
    a = account()["id"]
    result = run(checkin.run(a, "manual"))
    assert (result["status"], result["gained"]) == (status, gained)
    record = records.accounts.get(a)
    assert record["last_status"] == status and record["last_source"] == "manual"
    assert history.page("checkin")["items"][0]["status"] == status


@pytest.mark.parametrize("response,status,message", [
    (httpx.Response(401, json={"success": False}), "nodeseek_auth_expired", "NODESEEK_AUTH_EXPIRED"),
    (httpx.Response(403, text="<title>Just a moment...</title>"), "nodeseek_cloudflare_blocked", "NODESEEK_CLOUDFLARE_BLOCKED"),
    (httpx.Response(200, text="<html>not json</html>"), "uncertain", "NODESEEK_RESULT_UNCERTAIN"),
])
def test_checkin_classifies_failures(monkeypatch, account, response, status, message):
    async def reply():
        return response

    fake_checkin(monkeypatch, reply)
    result = run(checkin.run(account()["id"]))
    assert (result["status"], result["message"]) == (status, message)


@pytest.mark.parametrize("error,status,message", [
    (httpx.ReadTimeout("t"), "uncertain", "NODESEEK_RESULT_UNCERTAIN"),  # may have gone through
    (httpx.ConnectError("c"), "failed", "NODESEEK_CONNECT_FAILED"),      # certainly did not
])
def test_checkin_timeouts_are_uncertain_but_connect_errors_are_not(monkeypatch, account, error, status, message):
    async def reply():
        raise error

    fake_checkin(monkeypatch, reply)
    result = run(checkin.run(account()["id"]))
    assert (result["status"], result["message"]) == (status, message)


def test_scheduled_checkin_announces_the_reward_once(monkeypatch, account, bot, telegram):
    async def reply():
        return json_response(success=True, message="今天的签到收益是7个鸡腿")

    fake_checkin(monkeypatch, reply)
    a = alerting(account, bot)["id"]
    run(checkin.run(a, "manual"))
    assert telegram.sent == []  # manual runs are not announced
    run(checkin.run(a, "scheduled"))
    assert len(telegram.sent) == 1 and "7 个鸡腿" in telegram.sent[0]["body"] and telegram.sent[0]["chat_id"] == "alerts"


def test_a_failed_courtesy_notice_does_not_change_the_checkin_result(monkeypatch, account, bot, telegram):
    async def reply():
        return json_response(success=True, message="今天的签到收益是7个鸡腿")

    fake_checkin(monkeypatch, reply)
    telegram.fail = httpx.ConnectError("down")
    result = run(checkin.run(alerting(account, bot)["id"], "scheduled"))
    assert result["success"] and result["status"] == "success"


def test_expired_cookie_alerts_once_and_recovery_rearms(monkeypatch, account, bot, telegram):
    state = {"expired": True}

    async def reply():
        if state["expired"]:
            return httpx.Response(401, json={"success": False})
        return json_response(success=True, message="鸡腿 +1")

    fake_checkin(monkeypatch, reply)
    a = alerting(account, bot)["id"]
    run(checkin.run(a))
    run(checkin.run(a))
    assert len(telegram.sent) == 1 and "Cookie 已过期" in telegram.sent[0]["body"]
    assert records.accounts.get(a)["last_offline_status"] in {"notified", "expired"}  # both read as expired
    state["expired"] = False
    run(checkin.run(a))
    assert records.accounts.get(a)["last_offline_status"] == "ok" and not records.accounts.get(a)["cookie_offline_notified"]


# --- keyword monitor --------------------------------------------------------------------------

def keyword_account(account, bot, **extra):
    return account(keyword_monitor_enabled=True, keywords=["VPS", "cn2"], keyword_bot_id=bot, keyword_chat_id="kw", **extra)["id"]


def feed(monkeypatch, *posts):
    async def latest():
        return list(posts)

    fake_posts(monkeypatch, latest)


@pytest.mark.parametrize("keywords_,title,expected", [
    (["vps"], "出一台 ＶＰＳ", "vps"),
    (["CN2", "gia"], "全新 cn2 GIA 线路", "CN2"),
    (["abc"], "nothing here", None),
])
def test_keyword_matching_ignores_case_and_width(keywords_, title, expected):
    assert keywords.match_keyword(keywords_, title) == expected


def test_first_run_only_records_a_baseline(monkeypatch, account, bot, telegram):
    feed(monkeypatch, post(100, "VPS old"), post(101, "other"))
    a = keyword_account(account, bot)
    result = run(keywords.run(a))
    assert result["status"] == "baseline" and telegram.sent == []
    assert records.accounts.get(a)["keyword_post_watermark"] == 101


def test_new_matching_posts_are_notified_once(monkeypatch, account, bot, telegram):
    a = keyword_account(account, bot)
    feed(monkeypatch, post(100, "old"))
    run(keywords.run(a))
    feed(monkeypatch, post(100, "old"), post(101, "出 VPS 一台"), post(102, "闲聊"), post(103, "CN2 线路"))
    result = run(keywords.run(a))
    assert result["status"] == "notified" and result["matched"] == 2 and result["new_posts"] == 3
    assert len(telegram.sent) == 1 and "VPS" in telegram.sent[0]["body"] and "post-103-1" in telegram.sent[0]["body"]
    record = records.accounts.get(a)
    assert record["keyword_post_watermark"] == 103 and record["keyword_pending_posts"] == [] and record["last_match_at"]
    assert history.page("monitor")["items"][0]["status"] == "notified"
    again = run(keywords.run(a))
    assert again["status"] == "no_match" and len(telegram.sent) == 1
    assert [h["status"] for h in history.page("monitor")["items"]] == ["notified", "baseline"]  # idle checks are not logged


def test_failed_notification_keeps_the_posts_for_the_next_run(monkeypatch, account, bot, telegram):
    a = keyword_account(account, bot)
    feed(monkeypatch, post(100, "old"))
    run(keywords.run(a))
    feed(monkeypatch, post(100, "old"), post(101, "VPS sale"))
    telegram.fail = httpx.ConnectError("down")
    result = run(keywords.run(a))
    assert result["status"] == "notify_failed" and result["notified"] is False
    record = records.accounts.get(a)
    assert record["keyword_post_watermark"] == 100 and [p["id"] for p in record["keyword_pending_posts"]] == ["101"]
    telegram.fail = None
    # The ledger allows a limited number of automatic attempts per event; a later cycle sends it.
    from sqlalchemy import text
    from nsapp.db import write_transaction
    from nsapp.repositories import jobs
    with write_transaction() as conn:
        conn.execute(text("UPDATE notifications SET status='pending',available_at=:n"), {"n": jobs.stamp(-1)})
    assert run(keywords.run(a))["status"] == "notified" and len(telegram.sent) == 1
    assert records.accounts.get(a)["keyword_pending_posts"] == [] and records.accounts.get(a)["keyword_post_watermark"] == 101


def test_feed_errors_are_reported_without_changing_the_watermark(monkeypatch, account, bot):
    a = keyword_account(account, bot)

    async def broken():
        raise AppError("NODESEEK_FEED_INVALID")

    fake_posts(monkeypatch, broken)
    result = run(keywords.run(a))
    assert (result["status"], result["message"]) == ("failed", "NODESEEK_FEED_INVALID")
    assert "keyword_post_watermark" not in records.accounts.get(a)


def test_disabled_monitor_refuses_to_run(account):
    with pytest.raises(AppError, match="MONITOR_DISABLED"):
        run(keywords.run(account()["id"]))


def test_keyword_checks_do_not_touch_cookie_state(monkeypatch, account, bot):
    """The feed is public: a successful read says nothing about the cookie."""
    a = keyword_account(account, bot, offline_notify_enabled=True, offline_bot_id=bot, offline_chat_id="alerts")
    records.accounts.patch(a, {"last_offline_status": "expired"})
    feed(monkeypatch, post(100, "x"))
    run(keywords.run(a))
    assert records.accounts.get(a)["last_offline_status"] == "expired"


# --- private messages ----------------------------------------------------------------------------

def message(mid, sender, body="hi"):
    return {"max_id": mid, "sender_id": 1 if sender == "me" else 2, "sender_name": "Me" if sender == "me" else "Alice",
            "receiver_id": 2 if sender == "me" else 1, "receiver_name": "Alice" if sender == "me" else "Me", "content": body}


def inbox(monkeypatch, *items, status=200, success=True):
    async def reply():
        return httpx.Response(status, json={"success": success, "msgArray": list(items)})

    fake_messages(monkeypatch, reply)


def message_account(account, bot, **extra):
    return account("Me", message_monitor_enabled=True, message_bot_id=bot, message_chat_id="dm", **extra)["id"]


def test_only_incoming_unseen_messages_are_reported():
    items = [message(1, "alice"), message(2, "me"), message(3, "alice")]
    assert [m["max_id"] for m in messages.incoming(items, "Me", {"1"})] == [3]


def test_first_message_check_is_a_baseline(monkeypatch, account, bot, telegram):
    inbox(monkeypatch, message(1, "alice"))
    a = message_account(account, bot)
    assert run(messages.run(a))["status"] == "baseline" and telegram.sent == []
    assert records.accounts.get(a)["message_seen_max_ids"] == ["1"]


def test_new_private_message_is_notified_and_not_repeated(monkeypatch, account, bot, telegram):
    a = message_account(account, bot)
    inbox(monkeypatch, message(1, "alice"))
    run(messages.run(a))
    inbox(monkeypatch, message(1, "alice"), message(2, "alice", "你好"), message(3, "me", "reply"))
    result = run(messages.run(a))
    assert result["status"] == "notified" and result["new_messages"] == 1
    assert "Alice" in telegram.sent[0]["body"] and "你好" in telegram.sent[0]["body"]
    assert run(messages.run(a))["status"] == "no_match" and len(telegram.sent) == 1


def test_failed_message_notification_is_retried(monkeypatch, account, bot, telegram):
    a = message_account(account, bot)
    inbox(monkeypatch, message(1, "alice"))
    run(messages.run(a))
    inbox(monkeypatch, message(1, "alice"), message(2, "alice"))
    telegram.fail = httpx.ConnectError("down")
    assert run(messages.run(a))["status"] == "notify_failed"
    assert "2" not in records.accounts.get(a)["message_seen_max_ids"]


def test_expired_cookie_is_reported_by_the_message_check(monkeypatch, account, bot, telegram):
    inbox(monkeypatch, status=401, success=False)
    a = message_account(account, bot, offline_notify_enabled=True, offline_bot_id=bot, offline_chat_id="alerts")
    result = run(messages.run(a))
    assert (result["status"], result["message"]) == ("failed", "NODESEEK_AUTH_EXPIRED")
    assert records.accounts.get(a)["last_offline_status"] == "notified" and len(telegram.sent) == 1


# --- cookie check -----------------------------------------------------------------------------

def test_cookie_check_reports_valid_expired_and_unknown(monkeypatch, account, bot, telegram):
    a = alerting(account, bot)["id"]
    inbox(monkeypatch)
    assert run(cookie_check.run(a))["success"] and records.accounts.get(a)["last_offline_status"] == "ok"
    inbox(monkeypatch, status=401, success=False)
    expired = run(cookie_check.run(a))
    assert not expired["success"] and expired["status"] == "notified" and len(telegram.sent) == 1
    run(cookie_check.run(a))
    assert len(telegram.sent) == 1

    async def blocked():
        return httpx.Response(403, text="Just a moment...")

    fake_messages(monkeypatch, blocked)
    unknown = run(cookie_check.run(a))
    assert (unknown["status"], unknown["message"]) == ("failed", "NODESEEK_CLOUDFLARE_BLOCKED")


def test_cookie_check_needs_the_opt_in(account):
    with pytest.raises(AppError, match="OFFLINE_DISABLED"):
        run(cookie_check.run(account()["id"]))


def test_response_classification_matches_nodeseek_behaviour():
    assert nodeseek.auth_expired(httpx.Response(401))
    assert nodeseek.auth_expired(httpx.Response(200, json={"success": False, "message": "未登录"}))
    assert not nodeseek.auth_expired(httpx.Response(200, json={"success": True}))
    assert nodeseek.access_blocked(httpx.Response(403, text="Just a moment"))
    assert not nodeseek.access_blocked(httpx.Response(200, json={}))
