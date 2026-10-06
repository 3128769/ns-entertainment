from __future__ import annotations

import unicodedata
from typing import Any


def clean(value: Any, limit: int = 240) -> str:
    """Collapse whitespace and cap the length."""
    return " ".join(str(value or "").split())[:limit]


def folded(value: Any) -> str:
    """Case-insensitive, width-insensitive form used for keyword matching and name keys."""
    text = unicodedata.normalize("NFKC", str(value or ""))
    return "".join(ch for ch in text if unicodedata.category(ch) != "Cf").casefold()
