from __future__ import annotations

from fastapi import Header, HTTPException, status

from nsapp.services import auth


def bearer_token(authorization: str | None) -> str | None:
    if authorization and authorization.lower().startswith("bearer "):
        return authorization[7:].strip() or None
    return None


def require_user(authorization: str | None = Header(default=None)) -> str:
    user = auth.current_user(bearer_token(authorization))
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="UNAUTHORIZED")
    return user
