"""Business error codes.

Every expected failure is an ``AppError`` whose message is a stable upper-case
code. The API turns it into ``{"detail": CODE}`` with the HTTP status from
``STATUS_BY_CODE`` (400 when unlisted); the frontend maps codes to Chinese text.
``AppError`` stays a ``ValueError`` so callers that guard broadly keep working.
"""
from __future__ import annotations

STATUS_BY_CODE: dict[str, int] = {
    "NODESEEK_ACCOUNT_NOT_FOUND": 404,
    "PROXY_NOT_FOUND": 404,
    "BOT_NOT_FOUND": 404,
    "NODESEEK_NAME_CONFLICT": 409,
    "PROXY_NAME_CONFLICT": 409,
    "PROXY_IN_USE": 409,
    "NODESEEK_ACCOUNT_BUSY": 409,
    "INVALID_USERNAME_OR_PASSWORD": 401,
    "RATE_LIMITED": 429,
    "WORKER_UNAVAILABLE": 503,
    "TASK_QUEUE_FULL": 503,
}


class AppError(ValueError):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code

    @property
    def status(self) -> int:
        return STATUS_BY_CODE.get(self.code, 400)
