import os
import sys
import tempfile
from pathlib import Path

import httpx
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)
DATA = tempfile.TemporaryDirectory(prefix="ns-tests-")
WEB = Path(DATA.name) / "web"
(WEB / "assets").mkdir(parents=True)
(WEB / "index.html").write_text("<!doctype html><title>shell</title>")
(WEB / "assets" / "app-abc123.js").write_text("console.log(1)")
(Path(DATA.name) / "secret.txt").write_text("outside the web root")
os.environ.update(
    NS_DATA_DIR=DATA.name, NS_ADMIN_PASSWORD="test-password-only", NS_SCHEDULER_ENABLED="0", NS_WEB_DIR=str(WEB),
)

from nsapp import cli  # noqa: E402

cli.migrate()

from nsapp.db import engine  # noqa: E402
from nsapp.repositories import users  # noqa: E402
from nsapp.schema import metadata  # noqa: E402

users.ensure_tables()


@pytest.fixture(autouse=True)
def isolation(monkeypatch):
    """Empty database per test and no way to reach the real network."""

    async def no_network(*_args, **_kwargs):
        raise AssertionError("REAL_NETWORK_DISABLED_IN_TESTS")

    monkeypatch.setattr(httpx.AsyncClient, "send", no_network)
    with engine.begin() as conn:
        for table in reversed(metadata.sorted_tables):
            conn.execute(table.delete())


@pytest.fixture
def account():
    from nsapp.services import accounts

    def add(name="Account", **fields):
        return accounts.create({"name": name, "cookie": "session=test-only", **fields})

    return add


@pytest.fixture
def bot():
    from nsapp.services import bots

    return bots.save("Mock Bot", "123:synthetic", "mock-chat")["id"]
