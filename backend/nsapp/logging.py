"""Structured, secret-free logging.

Call sites may only pass identifiers, counters, status codes and timings; the
allow-list below drops anything else, and error codes that are not plain
``UPPER_SNAKE`` identifiers are replaced so upstream text can never leak.
"""
from __future__ import annotations

import json
import logging
import re
import time
from contextvars import ContextVar

correlation_id: ContextVar[str] = ContextVar("correlation_id", default="")

logger = logging.getLogger("nsapp")
logger.setLevel(logging.INFO)
_handler = logging.StreamHandler()
_handler.setFormatter(logging.Formatter("%(message)s"))
logger.addHandler(_handler)
logger.propagate = False

# httpx would otherwise log Telegram URLs that contain bot tokens.
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)

_ALLOWED = {
    "job_id", "account_id", "kind", "status", "attempts", "elapsed_ms", "error_code",
    "method", "route", "status_code", "version", "count", "concurrency",
}
_CODE = re.compile(r"[A-Z][A-Z0-9_]{1,100}")


def event(name: str, **fields: object) -> None:
    safe = {key: value for key, value in fields.items() if key in _ALLOWED}
    if safe.get("error_code") and not _CODE.fullmatch(str(safe["error_code"])):
        safe["error_code"] = "BUSINESS_REQUEST_FAILED"
    record = {
        "time": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "event": name,
        "correlation_id": correlation_id.get(),
        **safe,
    }
    logger.info(json.dumps(record, ensure_ascii=False))
