"""Admin users and login sessions (tokens are stored only as SHA-256 hashes)."""
from __future__ import annotations

import hashlib
from datetime import datetime, timedelta

from sqlalchemy import text

from nsapp.db import engine, write_transaction
from nsapp.schema import sessions, users
from nsapp.timeutil import iso_z, parse_iso, utc_now

SESSION_TTL = timedelta(hours=24)


def ensure_tables() -> None:
    """``users``/``sessions`` predate Alembic; create them idempotently."""
    users.create(engine, checkfirst=True)
    sessions.create(engine, checkfirst=True)


def password_hash(username: str) -> str | None:
    with engine.connect() as conn:
        row = conn.execute(text("SELECT password_hash FROM users WHERE username=:u"), {"u": username}).first()
    return row[0] if row else None


def exists(username: str) -> bool:
    with engine.connect() as conn:
        return conn.execute(text("SELECT id FROM users WHERE username=:u"), {"u": username}).first() is not None


def create(username: str, hashed: str) -> None:
    with write_transaction() as conn:
        conn.execute(
            text("INSERT INTO users(username,password_hash,created_at) VALUES(:u,:h,:c)"),
            {"u": username, "h": hashed, "c": iso_z()},
        )


def _digest(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def open_session(username: str, token: str) -> None:
    with write_transaction() as conn:
        conn.execute(text("DELETE FROM sessions WHERE expires_at<:now"), {"now": utc_now().isoformat()})
        conn.execute(
            text("INSERT INTO sessions(token_hash,username,expires_at,created_at) VALUES(:t,:u,:e,:c)"),
            {"t": _digest(token), "u": username, "e": (utc_now() + SESSION_TTL).isoformat(), "c": iso_z()},
        )


def session_user(token: str) -> str | None:
    with engine.connect() as conn:
        row = conn.execute(
            text("SELECT username,expires_at FROM sessions WHERE token_hash=:t"), {"t": _digest(token)}
        ).first()
    if not row:
        return None
    expires: datetime | None = parse_iso(row[1])
    if expires is None or expires <= utc_now():
        return None
    return str(row[0])


def close_session(token: str) -> None:
    with write_transaction() as conn:
        conn.execute(text("DELETE FROM sessions WHERE token_hash=:t"), {"t": _digest(token)})


def set_password_hash(username: str, hashed: str) -> bool:
    """Replace the user's password hash, creating the user if missing. True when it already existed."""
    with write_transaction() as conn:
        updated = conn.execute(
            text("UPDATE users SET password_hash=:h WHERE username=:u"), {"h": hashed, "u": username}
        ).rowcount
        if not updated:
            conn.execute(
                text("INSERT INTO users(username,password_hash,created_at) VALUES(:u,:h,:c)"),
                {"u": username, "h": hashed, "c": iso_z()},
            )
    return bool(updated)


def close_user_sessions(username: str) -> int:
    with write_transaction() as conn:
        return conn.execute(text("DELETE FROM sessions WHERE username=:u"), {"u": username}).rowcount
