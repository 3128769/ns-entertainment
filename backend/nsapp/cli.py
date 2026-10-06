"""Operator commands: ``python -m nsapp.cli migrate`` and ``... set-admin-password``."""
from __future__ import annotations

import argparse
import getpass
import json
import os
import sys
from pathlib import Path

from alembic import command
from alembic.config import Config

from nsapp import VERSION
from nsapp.settings import secret_key

_ALEMBIC_INI = Path(__file__).resolve().parents[1] / "alembic.ini"


def migrate() -> dict:
    """Create/upgrade the schema and make sure the instance key exists. Safe to repeat."""
    secret_key()
    command.upgrade(Config(str(_ALEMBIC_INI)), "head")
    return {"status": "ok", "version": VERSION}


def set_admin_password() -> dict:
    """Change the admin password. Reads NS_NEW_PASSWORD, otherwise asks twice on the terminal."""
    from nsapp.errors import AppError
    from nsapp.services import auth

    password = os.getenv("NS_NEW_PASSWORD", "")
    if not password:
        if not sys.stdin.isatty():
            raise SystemExit("no terminal: pass the password in NS_NEW_PASSWORD or run with -it")
        password = getpass.getpass("新密码（至少 8 位）: ")
        if password != getpass.getpass("再输入一次: "):
            raise SystemExit("两次输入不一致，未修改")
    try:
        return auth.set_password(os.getenv("NS_ADMIN_USER", "admin").strip() or "admin", password)
    except AppError as exc:
        raise SystemExit(f"未修改：{exc.code}") from None


def main() -> None:
    parser = argparse.ArgumentParser(prog="nsapp.cli")
    parser.add_argument("command", choices=["migrate", "set-admin-password"])
    args = parser.parse_args()
    result = migrate() if args.command == "migrate" else set_admin_password()
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
