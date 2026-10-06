"""Working copy of one account for the length of a task.

A task reads the account, does slow network work with no database transaction
open, mutates ``record`` and finally ``commit``s: only fields that changed are
written, so a user edit made meanwhile is preserved, and the write is dropped if
the cookie was replaced meanwhile (the result belongs to the old cookie).
"""
from __future__ import annotations

import copy

from nsapp.errors import AppError
from nsapp.repositories import history, records


class AccountState:
    def __init__(self, account_id: str, record: dict) -> None:
        self.id = account_id
        self.record = record
        self._loaded = copy.deepcopy(record)
        self._history: list[tuple[str, dict]] = []

    @classmethod
    def load(cls, account_id: str) -> AccountState:
        record = records.accounts.get(account_id)
        if record is None:
            raise AppError("NODESEEK_ACCOUNT_NOT_FOUND")
        return cls(account_id, record)

    def add_history(self, kind: str, item: dict) -> None:
        self._history.append((kind, item))

    def commit(self) -> None:
        changed = {key: value for key, value in self.record.items() if self._loaded.get(key) != value}
        changed.pop("updated_at", None)  # updated_at tracks configuration edits only
        if changed:
            records.accounts.patch(self.id, changed, expect_cookie=self._loaded.get("cookie"))
        for kind, item in self._history:
            history.append(kind, item)
