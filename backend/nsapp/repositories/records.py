"""JSON-document tables: accounts, proxies, bots.

One row per record: ``record_json`` holds the business fields; ``name`` /
``name_key`` / ``revision`` are real columns. ``patch`` merges a partial update
so concurrent writers of *different* fields (a user edit and a Worker result)
never overwrite each other.
"""
from __future__ import annotations

import json

from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from nsapp.db import engine, write_transaction
from nsapp.errors import AppError
from nsapp.repositories import jobs


class RecordStore:
    table: str

    def __init__(self, table: str, name_conflict_code: str | None = None) -> None:
        self.table = table
        self.name_conflict_code = name_conflict_code

    def all(self) -> dict[str, dict]:
        with engine.connect() as conn:
            rows = conn.execute(text(f"SELECT id,record_json FROM {self.table} ORDER BY id")).fetchall()
        return {row[0]: json.loads(row[1]) for row in rows}

    def get(self, record_id: str) -> dict | None:
        with engine.connect() as conn:
            row = conn.execute(
                text(f"SELECT record_json FROM {self.table} WHERE id=:id"), {"id": record_id}
            ).first()
        return json.loads(row[0]) if row else None

    def patch(
        self,
        record_id: str,
        fields: dict,
        *,
        create: bool = False,
        expect_cookie: str | None = None,
        drop: tuple[str, ...] = (),
    ) -> bool:
        """Merge ``fields`` into the record (and remove the ``drop`` keys).

        Returns False (and writes nothing) when the record is missing and
        ``create`` is off, or when ``expect_cookie`` is given and the stored
        cookie differs: a result obtained with a replaced cookie is stale.
        """
        try:
            return self._patch(record_id, fields, create, expect_cookie, drop)
        except IntegrityError as exc:
            if self.name_conflict_code and "name_key" in str(exc.orig):
                raise AppError(self.name_conflict_code) from exc
            raise

    def _patch(self, record_id: str, fields: dict, create: bool, expect_cookie: str | None, drop: tuple[str, ...]) -> bool:
        with write_transaction() as conn:
            jobs.assert_lease(conn)
            row = conn.execute(
                text(f"SELECT record_json FROM {self.table} WHERE id=:id"), {"id": record_id}
            ).first()
            if row is None and not create:
                return False
            record = json.loads(row[0]) if row else {}
            if expect_cookie is not None and record.get("cookie") != expect_cookie:
                return False
            self._validate(conn, fields)
            record.update(fields)
            for key in drop:
                record.pop(key, None)
            values = {
                "id": record_id,
                "name": record["name"],
                "name_key": record["name"].casefold(),
                "record": json.dumps(record, ensure_ascii=False),
                "created": record.get("created_at") or "",
                "updated": record.get("updated_at") or "",
            }
            if row:
                conn.execute(
                    text(
                        f"UPDATE {self.table} SET name=:name,name_key=:name_key,record_json=:record,"
                        "revision=revision+1,updated_at=:updated WHERE id=:id"
                    ),
                    values,
                )
            else:
                conn.execute(
                    text(
                        f"INSERT INTO {self.table}(id,name,name_key,record_json,created_at,updated_at,revision) "
                        "VALUES(:id,:name,:name_key,:record,:created,:updated,1)"
                    ),
                    values,
                )
        return True

    def delete(self, record_id: str) -> bool:
        with write_transaction() as conn:
            self._before_delete(conn, record_id)
            removed = conn.execute(
                text(f"DELETE FROM {self.table} WHERE id=:id"), {"id": record_id}
            ).rowcount
            if removed:
                self._after_delete(conn, record_id)
        return bool(removed)

    # Hooks for tables with referential rules.
    def _validate(self, conn, fields: dict) -> None: ...
    def _before_delete(self, conn, record_id: str) -> None: ...
    def _after_delete(self, conn, record_id: str) -> None: ...


class AccountStore(RecordStore):
    def _validate(self, conn, fields: dict) -> None:
        proxy_id = fields.get("proxy_id")
        if proxy_id and conn.execute(text("SELECT id FROM proxies WHERE id=:id"), {"id": proxy_id}).first() is None:
            raise AppError("PROXY_NOT_FOUND")

    def _after_delete(self, conn, record_id: str) -> None:
        conn.execute(
            text("UPDATE jobs SET status='canceled',last_error='ACCOUNT_DELETED' "
                 "WHERE account_id=:id AND status IN ('queued','retry_wait')"),
            {"id": record_id},
        )

    def name_taken(self, name: str, *, excluding: str | None = None) -> bool:
        with engine.connect() as conn:
            row = conn.execute(
                text("SELECT id FROM accounts WHERE name_key=:key"), {"key": name.casefold()}
            ).first()
        return bool(row) and row[0] != excluding


class ProxyStore(RecordStore):
    def _before_delete(self, conn, record_id: str) -> None:
        for (raw,) in conn.execute(text("SELECT record_json FROM accounts")).fetchall():
            if json.loads(raw).get("proxy_id") == record_id:
                raise AppError("PROXY_IN_USE")


accounts = AccountStore("accounts", "NODESEEK_NAME_CONFLICT")
proxies = ProxyStore("proxies", "PROXY_NAME_CONFLICT")
bots = RecordStore("bots")
