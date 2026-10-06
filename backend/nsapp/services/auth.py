"""Admin authentication: password hashing, sessions and login throttling."""
from __future__ import annotations

import hashlib
import hmac
import os
import secrets
import time
from pathlib import Path

import bcrypt

from nsapp.errors import AppError
from nsapp.repositories import users
from nsapp.settings import BASE_DIR

_SCRYPT = {"n": 16384, "r": 8, "p": 1}
_FAILURE_WINDOW = 300
_FAILURE_LIMIT = 5


def _hash_password(password: str, salt: str | None = None) -> str:
    salt = salt or secrets.token_hex(16)
    digest = hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt), **_SCRYPT)
    return f"scrypt${salt}${digest.hex()}"


def _verify_password(password: str, encoded: str) -> bool:
    try:
        if encoded.startswith(("$2a$", "$2b$", "$2y$")):  # legacy bcrypt hashes
            return bool(bcrypt.checkpw(password.encode(), encoded.encode("ascii")))
        _, salt, expected = encoded.split("$", 2)
        return hmac.compare_digest(_hash_password(password, salt).split("$", 2)[2], expected)
    except (ValueError, TypeError):
        return False


def init() -> None:
    users.ensure_tables()
    ensure_admin()


def ensure_admin() -> None:
    """Create the admin on first start; the password comes from env, a file, or is generated."""
    username = os.getenv("NS_ADMIN_USER", "admin").strip() or "admin"
    if users.exists(username):
        return
    password = os.getenv("NS_ADMIN_PASSWORD", "").strip()
    if not password:
        password_file = os.getenv("NS_ADMIN_PASSWORD_FILE", "").strip()
        if password_file:
            try:
                password = Path(password_file).read_text(encoding="utf-8").strip()
            except OSError:
                password = ""
    if not password:
        password = secrets.token_urlsafe(18)
        path = BASE_DIR / ".admin_password"
        path.write_text(password, encoding="utf-8")
        os.chmod(path, 0o600)
        print("NS generated admin password; read /data/.admin_password")  # never print the secret itself
    users.create(username, _hash_password(password))


MIN_PASSWORD_LENGTH = 8


def set_password(username: str, password: str) -> dict:
    """Set (or create) a user's password and sign them out everywhere."""
    if len(password) < MIN_PASSWORD_LENGTH:
        raise AppError("PASSWORD_TOO_SHORT")
    users.ensure_tables()
    existed = users.set_password_hash(username, _hash_password(password))
    return {"username": username, "created": not existed, "sessions_closed": users.close_user_sessions(username)}


def authenticate(username: str, password: str) -> str | None:
    """Return a new session token, or None for wrong credentials."""
    username = username.strip()
    stored = users.password_hash(username)
    if not stored or not _verify_password(password, stored):
        return None
    token = secrets.token_urlsafe(32)
    users.open_session(username, token)
    return token


def current_user(token: str | None) -> str | None:
    return users.session_user(token) if token else None


def logout(token: str | None) -> None:
    if token:
        users.close_session(token)


class LoginThrottle:
    """Refuse a client after too many recent failures (in memory, per process)."""

    def __init__(self, limit: int = _FAILURE_LIMIT, window: float = _FAILURE_WINDOW) -> None:
        self.limit, self.window = limit, window
        self._failures: dict[str, list[float]] = {}

    def _recent(self, key: str) -> list[float]:
        now = time.monotonic()
        recent = [stamp for stamp in self._failures.get(key, []) if now - stamp < self.window]
        if recent:
            self._failures[key] = recent
        else:
            self._failures.pop(key, None)
        return recent

    def check(self, key: str) -> None:
        if len(self._recent(key)) >= self.limit:
            raise AppError("RATE_LIMITED")

    def record_failure(self, key: str) -> None:
        self._recent(key)
        self._failures.setdefault(key, []).append(time.monotonic())

    def clear(self, key: str) -> None:
        self._failures.pop(key, None)
