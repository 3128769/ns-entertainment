from __future__ import annotations

from nsapp.repositories import history

_KIND_BY_NAME = {"checkin": "checkin", "monitor": "monitor", "message": "message"}


def page(kind: str, limit: int = 100, offset: int = 0, account_id: str | None = None, status: str | None = None) -> dict:
    return history.page(_KIND_BY_NAME[kind], min(max(limit, 1), 100), max(offset, 0), account_id, status)
