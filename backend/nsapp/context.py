"""Per-task execution context shared by the Worker and everything it calls."""
from __future__ import annotations

from contextvars import ContextVar

# The job row currently being executed in this asyncio task (None outside the Worker).
# Repositories use it to refuse writes from a Worker whose lease has been taken over.
current_job: ContextVar[dict | None] = ContextVar("current_job", default=None)
