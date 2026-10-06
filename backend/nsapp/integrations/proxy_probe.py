"""Proxy health probe."""
from __future__ import annotations

import time

import httpx

PROBE_URL = "https://api.telegram.org"


async def probe(proxy_url: str) -> dict:
    """Open a request through the proxy; any upstream < 500 counts as a working exit."""
    started = time.monotonic()
    try:
        async with httpx.AsyncClient(proxy=proxy_url, timeout=5, follow_redirects=True) as client:
            response = await client.get(PROBE_URL)
        if response.status_code >= 500:
            raise OSError("proxy upstream failed")
    except Exception:
        return {"success": False, "latency_ms": None, "message": "代理连接失败", "code": "PROXY_CONNECT_FAILED"}
    return {
        "success": True,
        "latency_ms": max(0, int((time.monotonic() - started) * 1000)),
        "message": "代理出口连接正常",
        "code": "OK",
    }
