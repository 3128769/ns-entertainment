"""Fill a scratch instance with believable fake data."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from dev.guard import require_demo_dir

require_demo_dir(creating=True)

from nsapp import cli  # noqa: E402
from nsapp.repositories import history, records  # noqa: E402
from nsapp.services import accounts, auth, bots, proxies  # noqa: E402
from nsapp.timeutil import iso_z  # noqa: E402


def ago(**delta) -> str:
    return iso_z(datetime.now(timezone.utc) - timedelta(**delta))


def main() -> None:
    cli.migrate()
    auth.init()
    bot = bots.save("NS 通知", "123456:demo-token-not-real", "100200300")["id"]
    ops = bots.save("运维告警", "654321:demo-token-not-real", "-1001234567890")["id"]
    hk = proxies.create("香港出口", "CN2 线路", "socks5://demo:demo@127.0.0.1:1080")["id"]
    jp = proxies.create("东京备用", "", "http://127.0.0.1:3128")["id"]

    def make(name, **extra):
        return accounts.create({"name": name, "cookie": f"session=demo-{name}", **extra})["id"]

    main_account = make("主号", proxy_id=hk, schedule_time="08:20", keyword_monitor_enabled=True,
                  keywords=["vps", "cn2", "补货", "鸡腿"], keyword_bot_id=bot, keyword_chat_id="100200300",
                  message_monitor_enabled=True, message_bot_id=bot, message_chat_id="100200300",
                  offline_notify_enabled=True, offline_bot_id=ops, offline_chat_id="-1001234567890")
    second = make("副号", schedule_mode="range", schedule_start="07:30", schedule_end="09:00",
                 message_monitor_enabled=True, message_bot_id=bot, message_chat_id="100200300")
    spare = make("备用号", proxy_id=jp, schedule_time="21:10", random_checkin=False,
                 offline_notify_enabled=True, offline_bot_id=ops, offline_chat_id="-1001234567890")
    make("测试号", enabled=False, schedule_time="09:00")
    steady = make("稳定号", schedule_time="08:05", keyword_monitor_enabled=True, keywords=["aff", "gia"],
                        keyword_bot_id=bot, keyword_chat_id="100200300")

    runtime = {
        main_account: dict(last_status="success", last_message="今天的签到收益是7个鸡腿", last_run_at=ago(hours=11, minutes=40), last_source="scheduled",
                     last_monitor_status="no_match", last_monitor_message="NODESEEK_MONITOR_NO_MATCH", last_monitor_at=ago(seconds=12),
                     last_match_at=ago(hours=2, minutes=9),
                     last_message_monitor_status="no_match", last_message_monitor_message="NODESEEK_MESSAGE_NO_MATCH", last_message_monitor_at=ago(seconds=41),
                     last_offline_status="ok", last_offline_message="NODESEEK_COOKIE_OK", last_offline_at=ago(minutes=3)),
        second: dict(last_status="already", last_message="您已完成签到", last_run_at=ago(hours=10, minutes=5), last_source="manual",
                    last_message_monitor_status="notified", last_message_monitor_message="NODESEEK_MESSAGE_NOTIFIED", last_message_monitor_at=ago(minutes=26)),
        spare: dict(last_status="nodeseek_auth_expired", last_message="NODESEEK_AUTH_EXPIRED", last_run_at=ago(hours=22), last_source="scheduled",
                    last_offline_status="notified", last_offline_message="NODESEEK_OFFLINE_NOTIFIED", last_offline_at=ago(minutes=4), cookie_offline_notified=True),
        steady: dict(last_status="uncertain", last_message="NODESEEK_RESULT_UNCERTAIN", last_run_at=ago(hours=11, minutes=55), last_source="scheduled",
                           last_monitor_status="notify_failed", last_monitor_message="TELEGRAM_CHAT_FORBIDDEN", last_monitor_at=ago(seconds=20)),
    }
    for account_id, fields in runtime.items():
        records.accounts.patch(account_id, fields)

    names = {main_account: "主号", second: "副号", spare: "备用号", steady: "稳定号"}
    for day in range(1, 9):
        for account_id, name in names.items():
            status = "success" if (day + len(name)) % 5 else "already"
            if account_id == spare and day == 1:
                status = "nodeseek_auth_expired"
            history.append("checkin", {
                "success": status in {"success", "already"}, "status": status, "account_id": account_id, "account_name": name,
                "message": "NODESEEK_AUTH_EXPIRED" if status.startswith("nodeseek") else ("今天的签到收益是%d个鸡腿" % (3 + day) if status == "success" else "您已完成签到"),
                "gained": 3 + day if status == "success" else None, "source": "scheduled" if day % 3 else "manual",
                "ran_at": ago(days=day, hours=10, minutes=day * 7),
            })
    for i, (title_kw, status) in enumerate([("vps", "notified"), ("cn2", "notified"), ("补货", "notify_failed"), ("vps", "notified"), ("鸡腿", "baseline")]):
        history.append("monitor", {
            "success": status != "notify_failed", "status": status, "account_id": main_account, "account_name": "主号",
            "message": {"notified": "NODESEEK_MONITOR_NOTIFIED", "notify_failed": "TELEGRAM_CHAT_FORBIDDEN", "baseline": "NODESEEK_MONITOR_BASELINE_SAVED"}[status],
            "source": "scheduled", "checked": 40, "new_posts": 3 + i, "matched": 1 if status != "baseline" else 0,
            "notified": status == "notified", "ran_at": ago(hours=2 + i * 5, minutes=9 + i),
        })
    for i, status in enumerate(["notified", "notified", "baseline", "failed", "notified"]):
        history.append("message", {
            "success": status != "failed", "status": status, "account_id": second, "account_name": "副号",
            "message": {"notified": "NODESEEK_MESSAGE_NOTIFIED", "baseline": "NODESEEK_MESSAGE_BASELINE_SAVED", "failed": "NODESEEK_MESSAGE_FAILED"}[status],
            "source": "scheduled", "checked": 20, "new_messages": 1 if status == "notified" else 0,
            "notified": status == "notified", "ran_at": ago(hours=1 + i * 6, minutes=26 + i),
        })
    print("demo data ready; admin password is the NS_ADMIN_PASSWORD you exported")


if __name__ == "__main__":
    main()
