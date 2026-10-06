import json
import os
import sqlite3
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_backup_restore_roundtrip_keeps_data_keys_and_login(tmp_path):
    data, backup = tmp_path / "instance", tmp_path / "backup"
    env = dict(os.environ, NS_DATA_DIR=str(data), NS_ADMIN_PASSWORD="restore-test-password")

    def run(*args):
        result = subprocess.run([sys.executable, *args], env=env, text=True, capture_output=True, cwd=ROOT)
        assert result.returncode == 0, result.stderr
        return result.stdout

    run("-c", (
        "from nsapp import cli; cli.migrate();"
        "from nsapp.services import auth, accounts; auth.init();"
        "accounts.create({'name': 'Restore', 'cookie': 'session=restore'})"
    ))
    original_key = (data / ".secret_key").read_bytes()
    run("scripts/backup.py", str(backup))
    run("-c", "from nsapp.services import accounts; a = accounts.list_accounts()['items'][0]['id']; accounts.update(a, {'name': 'Changed'})")
    restored = json.loads(run("scripts/restore.py", str(backup)))
    assert restored["integrity"] == "ok" and (Path(restored["displaced"]) / "app" / "app.sqlite").exists()
    assert (data / ".secret_key").read_bytes() == original_key

    def dump(path):
        with sqlite3.connect(path) as conn:
            assert conn.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
            return list(conn.iterdump())

    assert dump(data / "app" / "app.sqlite") == dump(backup / "app" / "app.sqlite")
    run("-c", (
        "from nsapp.services import auth, accounts;"
        "assert auth.current_user(auth.authenticate('admin', 'restore-test-password')) == 'admin';"
        "from nsapp.repositories import records; from nsapp.settings import decrypt_secret;"
        "a = list(records.accounts.all().values())[0]; assert a['name'] == 'Restore';"
        "assert decrypt_secret(a['cookie']) == 'session=restore'"
    ))
