import pytest
from fastapi.testclient import TestClient

from nsapp.api import routes
from nsapp.api.app import app
from nsapp.repositories import jobs


@pytest.fixture
def client():
    routes._throttle = routes.auth.LoginThrottle()
    with TestClient(app) as c:
        reply = c.post("/api/auth/login", json={"username": "admin", "password": "test-password-only"})
        assert reply.status_code == 200
        c.headers["Authorization"] = "Bearer " + reply.json()["access_token"]
        yield c


def test_login_me_and_logout(client):
    assert client.get("/api/auth/me").json() == {"username": "admin"}
    assert client.get("/api/auth/me", headers={"Authorization": ""}).status_code == 401
    assert client.post("/api/auth/login", json={"username": "admin", "password": "wrong"}).json() == {"detail": "INVALID_USERNAME_OR_PASSWORD"}
    assert client.post("/api/auth/logout").json() == {"success": True}
    assert client.get("/api/auth/me").status_code == 401  # the server-side session is gone


def test_login_is_throttled_after_repeated_failures(client):
    for _ in range(5):
        assert client.post("/api/auth/login", json={"username": "admin", "password": "wrong"}).status_code == 401
    blocked = client.post("/api/auth/login", json={"username": "admin", "password": "test-password-only"})
    assert blocked.status_code == 429 and blocked.json() == {"detail": "RATE_LIMITED"}


def test_throttle_is_per_client_address_so_one_attacker_cannot_lock_out_others(client):
    attacker = {"X-Real-IP": "203.0.113.9"}
    for _ in range(5):
        assert client.post("/api/auth/login", json={"username": "admin", "password": "wrong"}, headers=attacker).status_code == 401
    assert client.post("/api/auth/login", json={"username": "admin", "password": "test-password-only"}, headers=attacker).status_code == 429
    owner = client.post("/api/auth/login", json={"username": "admin", "password": "test-password-only"}, headers={"X-Real-IP": "198.51.100.7"})
    assert owner.status_code == 200


def test_account_crud_contract(client):
    created = client.post("/api/accounts", json={"name": "One", "cookie": "session=test"})
    assert created.status_code == 201
    account = created.json()["account"]
    assert account["cookie_set"] and "cookie" not in account
    assert client.get("/api/accounts").json()["total"] == 1
    assert client.patch("/api/accounts/" + account["id"], json={"name": "Two"}).json()["account"]["name"] == "Two"
    assert client.post("/api/accounts", json={"name": "Two", "cookie": "session=test"}).status_code == 409
    assert client.delete("/api/accounts/" + account["id"]).json()["success"]
    assert client.get("/api/accounts").json()["total"] == 0
    assert client.delete("/api/accounts/" + account["id"]).status_code == 404


def test_partial_update_changes_only_what_was_sent(client):
    account = client.post("/api/accounts", json={"name": "One", "cookie": "session=test", "keywords": ["a"]}).json()["account"]
    updated = client.patch("/api/accounts/" + account["id"], json={"enabled": False}).json()["account"]
    assert updated["enabled"] is False and updated["keywords"] == ["a"] and updated["name"] == "One"


def test_validation_errors_have_stable_shape(client):
    blank = client.post("/api/accounts", json={"name": "", "cookie": "x"})
    assert blank.status_code == 422 and blank.json()["detail"] == "VALIDATION_FAILED" and blank.json()["fields"] == ["name"]
    assert client.post("/api/accounts", json={"name": "X", "cookie": "session=x", "schedule_time": "25:00"}).json() == {"detail": "NODESEEK_SCHEDULE_INVALID"}
    assert client.post("/api/accounts", json={"name": "X", "cookie": "nocookie"}).json() == {"detail": "NODESEEK_COOKIE_REQUIRED"}
    assert client.post("/api/accounts", json={"name": "X", "cookie": "a=b", "schedule_mode": "weekly"}).status_code == 422


def test_proxy_and_bot_contract(client):
    proxy = client.post("/api/proxies", json={"name": "Proxy", "proxy_url": "socks5://user:password@localhost:1080"})
    assert proxy.status_code == 201
    p = proxy.json()["proxy"]
    assert "proxy_url" not in p and "password" not in str(p) and p["protocol"] == "socks5"
    assert client.patch("/api/proxies/" + p["id"], json={"remark": "Changed"}).status_code == 200
    bot = client.post("/api/bots", json={"name": "Bot", "token": "123:synthetic", "chat_id": "test"})
    assert bot.status_code == 201
    b = bot.json()["bot"]
    assert "token" not in b and client.get("/api/bots").json()["items"][0]["id"] == b["id"]
    assert client.delete("/api/bots/" + b["id"]).status_code == 200
    assert client.delete("/api/proxies/" + p["id"]).status_code == 200


def test_bot_token_can_be_left_blank_when_editing(client):
    bot = client.post("/api/bots", json={"name": "Bot", "token": "123:synthetic", "chat_id": "1"}).json()["bot"]
    edited = client.post("/api/bots", json={"name": "Renamed", "token": "", "chat_id": "2", "bot_id": bot["id"]})
    assert edited.status_code == 201 and edited.json()["bot"]["name"] == "Renamed"
    assert client.post("/api/bots", json={"name": "New", "token": "", "chat_id": "2"}).json() == {"detail": "BOT_FIELDS_INVALID"}


def test_proxy_in_use_cannot_be_deleted_and_reports_its_users(client):
    pid = client.post("/api/proxies", json={"name": "P", "proxy_url": "http://localhost:3128"}).json()["proxy"]["id"]
    client.post("/api/accounts", json={"name": "A", "cookie": "session=x", "proxy_id": pid})
    assert client.delete("/api/proxies/" + pid).status_code == 409
    assert client.get("/api/proxies").json()["items"][0]["assigned_count"] == 1


@pytest.mark.parametrize("path", ["/api/history", "/api/monitor-history", "/api/message-history"])
def test_history_shape(client, path):
    assert client.get(path).json() == {"items": [], "total": 0}
    assert client.get(path + "?limit=0&offset=-5").status_code == 200  # clamped, not rejected


def test_liveness_and_readiness(client):
    assert client.get("/healthz").status_code == 200
    assert client.get("/readyz").status_code == 503
    jobs.heartbeat("test", jobs.stamp(), 4)
    assert client.get("/readyz").json() == {"status": "ok", "ready": True}
    tasks = client.get("/api/system/tasks").json()
    assert tasks["ready"] and tasks["version"]


def test_manual_runs_go_through_the_job_queue(client, monkeypatch, account):
    from nsapp.services import manual_run

    expected = {"success": True, "status": "success", "message": "synthetic", "gained": 4, "source": "manual"}

    async def fake(account_id, kind):
        assert kind in {"sign", "monitor", "message"}
        return expected

    monkeypatch.setattr(routes.manual_run, "run_now", fake)
    for suffix in ("run", "monitor/run", "messages/run"):
        assert client.post(f"/api/accounts/a/{suffix}").json() == expected
    monkeypatch.undo()
    assert client.post("/api/accounts/missing/run").status_code == 404
    a = account()["id"]
    assert client.post(f"/api/accounts/{a}/monitor/run").json() == {"detail": "NODESEEK_MONITOR_DISABLED"}
    assert client.post(f"/api/accounts/{a}/run").json() == {"detail": "WORKER_UNAVAILABLE"}


def test_the_web_process_never_schedules(client):
    assert jobs.state()["counts"] == {}


def test_single_page_app_serving(client):
    shell = client.get("/accounts/deep/link")
    assert shell.status_code == 200 and "shell" in shell.text and shell.headers["Cache-Control"] == "no-cache"
    asset = client.get("/assets/app-abc123.js")
    assert asset.status_code == 200 and "immutable" in asset.headers["Cache-Control"]
    assert client.get("/assets/missing.js").status_code == 404


def test_head_requests_work_for_uptime_checks(client):
    assert client.head("/").status_code == 200 and client.head("/accounts").status_code == 200


def test_a_stale_2_0_shell_reloads_itself_instead_of_rendering_blank(client):
    script = client.get("/assets/main.js?v=2.0.2")
    assert script.status_code == 200 and "location.reload" in script.text and script.headers["Cache-Control"] == "no-store"
    assert "javascript" in script.headers["content-type"]
    css = client.get("/assets/styles.css?v=2.0.2")
    assert css.status_code == 200 and css.text == "" and "css" in css.headers["content-type"]


def test_paths_cannot_escape_the_web_root(client):
    for attempt in ("/../secret.txt", "/%2e%2e/secret.txt", "/assets/../../secret.txt"):
        reply = client.get(attempt)
        assert "outside the web root" not in reply.text


def test_unknown_api_paths_are_json_404s(client):
    reply = client.get("/api/nope")
    assert reply.status_code == 404 and reply.json() == {"detail": "NOT_FOUND"}


def test_request_id_is_echoed_and_responses_are_not_cached(client, capsys):
    reply = client.get("/api/accounts", headers={"X-Request-ID": "request-test"})
    assert reply.headers["X-Request-ID"] == "request-test" and reply.headers["Cache-Control"] == "no-store"
    assert "password" not in capsys.readouterr().err.lower()


def test_generated_admin_password_never_reaches_the_logs(monkeypatch, capsys):
    from nsapp.repositories import users
    from nsapp.services import auth
    from nsapp.settings import BASE_DIR

    monkeypatch.delenv("NS_ADMIN_PASSWORD")
    monkeypatch.setenv("NS_ADMIN_USER", "fresh-admin")
    users.ensure_tables()
    auth.ensure_admin()
    secret = (BASE_DIR / ".admin_password").read_text()
    assert secret not in capsys.readouterr().out
