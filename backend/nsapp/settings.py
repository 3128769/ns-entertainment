"""Process settings, instance secret and field-level encryption.

Everything here is derived from environment variables and the instance data
directory, so Web and Worker agree on paths and on the encryption key.
"""
from __future__ import annotations

import base64
import hashlib
import os
import secrets
from functools import lru_cache
from pathlib import Path

from cryptography.fernet import Fernet

BASE_DIR = Path(os.getenv("NS_DATA_DIR", "/data"))
WORK_DIR = BASE_DIR / "app"
DB_PATH = WORK_DIR / "app.sqlite"
TIMEZONE = "Asia/Shanghai"

_ENCRYPTED_PREFIX = "fernet:"


def ensure_dirs() -> None:
    WORK_DIR.mkdir(parents=True, exist_ok=True)
    (BASE_DIR / "backups").mkdir(parents=True, exist_ok=True)


def env_flag(name: str, default: str = "0") -> bool:
    return os.getenv(name, default).strip() == "1"


def job_concurrency() -> int:
    value = int(os.getenv("NS_JOB_CONCURRENCY", "4"))
    if not 1 <= value <= 16:
        raise RuntimeError("INVALID_CONCURRENCY")
    return value


def secret_key() -> str:
    """Return the instance key: NS_SECRET_KEY, else the key file (created on first use)."""
    ensure_dirs()
    from_env = os.getenv("NS_SECRET_KEY", "").strip()
    if from_env:
        return from_env
    path = BASE_DIR / ".secret_key"
    try:
        stored = path.read_text(encoding="utf-8").strip()
    except OSError:
        stored = ""
    if stored:
        return stored
    generated = secrets.token_urlsafe(48)
    path.write_text(generated, encoding="utf-8")
    os.chmod(path, 0o600)
    return generated


@lru_cache(maxsize=1)
def _fernet() -> Fernet:
    digest = hashlib.sha256(secret_key().encode("utf-8")).digest()
    return Fernet(base64.urlsafe_b64encode(digest))


def encrypt_secret(value: str) -> str:
    """Encrypt ``value``; an already valid ciphertext is returned unchanged."""
    if value.startswith(_ENCRYPTED_PREFIX):
        try:
            _fernet().decrypt(value[len(_ENCRYPTED_PREFIX):].encode("ascii"))
            return value
        except Exception:
            pass
    return _ENCRYPTED_PREFIX + _fernet().encrypt(value.encode("utf-8")).decode("ascii")


def decrypt_secret(value: str) -> str:
    if not value.startswith(_ENCRYPTED_PREFIX):
        return value
    return _fernet().decrypt(value[len(_ENCRYPTED_PREFIX):].encode("ascii")).decode("utf-8")
