"""Proxy lines used by accounts: parsing, storage and health tests."""
from __future__ import annotations

import base64
import binascii
import secrets
from urllib.parse import parse_qsl, quote, unquote, urlsplit

from nsapp.errors import AppError
from nsapp.integrations import proxy_probe
from nsapp.repositories import records
from nsapp.settings import decrypt_secret, encrypt_secret
from nsapp.timeutil import iso_z

SUPPORTED_SCHEMES = {"http", "socks4", "socks5"}
_TEST_FIELDS = ("last_test_success", "last_test_latency_ms", "last_tested_at", "last_test_code")


def _expand_shorthand(value: str) -> str:
    """Accept ``host:port``, ``host:port:user``, ``host:port:user:pass`` and ``user:pass@host:port``."""
    if "://" in value:
        return value
    if "@" not in value:
        parts = value.split(":")
        if len(parts) == 3:
            host, port, user = parts
            return f"socks5://{user}@{host}:{port}"
        if len(parts) == 4:
            host, port, user, password = parts
            return f"socks5://{quote(user)}:{quote(password)}@{host}:{port}"
    return "socks5://" + value


def _from_socks_uri(parsed, value: str) -> str:
    """``socks://base64(user:pass)@host:port`` (v2ray style) -> ``socks5://user:pass@host:port``."""
    if parsed.query:
        for key, option in parse_qsl(parsed.query, keep_blank_values=True):
            if key.lower() != "udp" or option.lower() not in {"0", "1", "true", "false"}:
                raise AppError("PROXY_URL_INVALID")
    token = unquote(parsed.username or "")
    if parsed.username and not parsed.password:
        padded = token + "=" * (-len(token) % 4)
        try:
            user, password = base64.b64decode(padded, altchars=b"-_", validate=True).decode().split(":", 1)
        except (binascii.Error, UnicodeDecodeError, ValueError):
            raise AppError("PROXY_URL_INVALID") from None
        return f"socks5://{quote(user)}:{quote(password)}@{parsed.hostname}:{parsed.port}"
    return parsed._replace(scheme="socks5", query="", fragment="").geturl()


def normalize(raw: str) -> tuple[str, dict]:
    """Return the canonical URL and ``{protocol, host, port}``."""
    value = _expand_shorthand(raw.strip())
    parsed = urlsplit(value)
    if parsed.scheme.lower() == "socks":
        value = _from_socks_uri(parsed, value)
        parsed = urlsplit(value)
    scheme = parsed.scheme.lower()
    if scheme not in SUPPORTED_SCHEMES or not parsed.hostname or not parsed.port:
        raise AppError("PROXY_URL_INVALID")
    if parsed.path not in ("", "/") or parsed.query:
        raise AppError("PROXY_URL_INVALID")
    return parsed._replace(fragment="").geturl(), {"protocol": scheme, "host": parsed.hostname, "port": parsed.port}


def _summary(proxy_id: str, record: dict) -> dict:
    _, meta = normalize(decrypt_secret(record["proxy_url"]))
    return {
        "id": proxy_id, "name": record["name"], **meta,
        "assigned_count": 0,
        "remark": record.get("remark", ""),
        "last_test_success": record.get("last_test_success"),
        "last_test_latency_ms": record.get("last_test_latency_ms"),
        "last_tested_at": record.get("last_tested_at"),
        "last_test_code": record.get("last_test_code"),
        "created_at": record.get("created_at"),
        "updated_at": record.get("updated_at"),
    }


def list_proxies() -> dict:
    users: dict[str, int] = {}
    for account in records.accounts.all().values():
        if account.get("proxy_id"):
            users[account["proxy_id"]] = users.get(account["proxy_id"], 0) + 1
    items = []
    for proxy_id, record in records.proxies.all().items():
        item = _summary(proxy_id, record)
        item["assigned_count"] = users.get(proxy_id, 0)
        items.append(item)
    items.sort(key=lambda item: (item["name"].casefold(), item["id"]))
    return {"items": items, "total": len(items)}


def exists(proxy_id: str) -> bool:
    return records.proxies.get(proxy_id) is not None


def url_for(proxy_id: str | None) -> str | None:
    """Decrypted proxy URL, or None for a direct connection / unknown id."""
    record = records.proxies.get(proxy_id) if proxy_id else None
    return decrypt_secret(record["proxy_url"]) if record else None


def create(name: str | None, remark: str, proxy_url: str) -> dict:
    normalized, _ = normalize(proxy_url)
    label = (name or "").strip()
    if not label:
        parsed = urlsplit(normalized)
        label = f"{parsed.hostname}:{parsed.port}"
    proxy_id = "px_" + secrets.token_hex(8)
    now = iso_z()
    record = {
        "name": label[:64], "remark": (remark or "").strip()[:240],
        "proxy_url": encrypt_secret(normalized), "created_at": now, "updated_at": now,
    }
    records.proxies.patch(proxy_id, record, create=True)
    return _summary(proxy_id, record)


def update(proxy_id: str, name: str | None, remark: str | None, proxy_url: str | None) -> dict:
    if records.proxies.get(proxy_id) is None:
        raise AppError("PROXY_NOT_FOUND")
    fields: dict = {"updated_at": iso_z()}
    if name is not None:
        label = name.strip()
        if not label:
            raise AppError("PROXY_NAME_INVALID")
        fields["name"] = label[:64]
    if remark is not None:
        fields["remark"] = remark.strip()[:240]
    drop: tuple[str, ...] = ()
    if proxy_url is not None:
        fields["proxy_url"] = encrypt_secret(normalize(proxy_url)[0])
        drop = _TEST_FIELDS  # a new URL invalidates the previous test result
    records.proxies.patch(proxy_id, fields, drop=drop)
    return _summary(proxy_id, records.proxies.get(proxy_id))


def delete(proxy_id: str) -> dict:
    if records.proxies.get(proxy_id) is None:
        raise AppError("PROXY_NOT_FOUND")
    records.proxies.delete(proxy_id)
    return {"success": True, "proxy_id": proxy_id}


async def test(proxy_id: str) -> dict:
    url = url_for(proxy_id)
    if not url:
        raise AppError("PROXY_NOT_FOUND")
    result = await proxy_probe.probe(url)
    records.proxies.patch(proxy_id, {
        "last_test_success": result["success"],
        "last_test_latency_ms": result["latency_ms"],
        "last_tested_at": iso_z(),
        "last_test_code": result["code"],
    })
    return result
